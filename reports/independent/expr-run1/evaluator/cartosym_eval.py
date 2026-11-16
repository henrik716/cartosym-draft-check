"""Expression evaluator and CartoSym-CSS checker written from spec/1-core only.

Expression trees use the CQL2-JSON shape (as in spec/1-core/schemas/CartoSym-JSON.schema.json):
literals are JSON scalars / arrays, {"property": n}, {"sysId": n}, {"$ref": "#/$variables/n"},
{"op": name, "args": [...]}. The CartoSym-CSS parser produces the same shape.
"""
import math
import random as _random
import re
import unicodedata

NULL = None


class EvalError(Exception):
    pass


# ---------------------------------------------------------------- values

def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def is_num(v):
    return (isinstance(v, (int, float))) and not isinstance(v, bool)


def is_text(v):
    return isinstance(v, str)


# ---------------------------------------------------------------- context

# viz / sd abbreviations: used in the text's examples and the JSON schema enum,
# but never defined (see notes.md).
SYS_ALIASES = {
    "viz": "visualization",
    "sd": "scaleDenominator",
    "id": "identifier",
}


def canonical_sysid(name):
    parts = name.split(".")
    out = []
    for i, p in enumerate(parts):
        if i == 0 and p == "viz":
            out.append("visualization")
        elif i == 1 and out and out[0] == "visualization" and p == "sd":
            out.append("scaleDenominator")
        elif i == 1 and out and out[0] == "dataLayer" and p == "id":
            out.append("identifier")
        else:
            out.append(p)
    return ".".join(out)


SYSTEM_ROOTS = {"visualization", "viz", "dataLayer", "capabilities", "feature"}


class Context:
    def __init__(self, properties=None, system=None, definitions=None, variables=None):
        self.properties = properties or {}
        self.system = {}
        for k, v in (system or {}).items():
            self.system[canonical_sysid(k)] = v
        self.definitions = definitions or {}
        self.variables = variables or {}  # run-time overrides
        self._var_stack = []

    def sysid(self, name):
        c = canonical_sysid(name)
        if c in self.system:
            return self.system[c]
        raise EvalError("system identifier '%s' has no value in this context" % name)

    def prop(self, name):
        if name in self.properties:
            return self.properties[name]
        # Not specified by the text: an unknown property resolves to NULL here.
        return NULL

    def var(self, name):
        if name in self.variables:
            return self.variables[name]
        if name in self.definitions:
            if name in self._var_stack:
                raise EvalError("recursive variable definition '%s'" % name)
            self._var_stack.append(name)
            try:
                return evaluate(self.definitions[name], self)
            finally:
                self._var_stack.pop()
        raise EvalError("undefined variable '%s'" % name)


# ---------------------------------------------------------------- functions

D = "double"
S = "string"
A = "array"


def _match(args, params):
    """Apply the conversions of /req/functions/call-expressions; None if no match."""
    if len(args) != len(params):
        return None
    out = []
    for a, p in zip(args, params):
        if p == D:
            if is_int(a):
                out.append(float(a))
            elif isinstance(a, float):
                out.append(a)
            else:
                return None
        elif p == S:
            if is_text(a):
                out.append(a)
            else:
                return None
        elif p == A:
            if isinstance(a, list):
                out.append(a)
            else:
                return None
        else:
            out.append(a)
    return out


def _round_half_away(x):
    if math.isnan(x) or math.isinf(x):
        return NULL
    r = math.floor(abs(x) + 0.5)
    return int(-r if x < 0 else r)


def _safe(f):
    def g(*a):
        try:
            return f(*a)
        except (ValueError, OverflowError, ZeroDivisionError):
            return NULL
    return g


def _values_equal(a, b):
    if is_num(a) and is_num(b):
        return a == b
    if type(a) is not type(b):
        return False
    return a == b


def _a_containedBy(a, b):
    return all(any(_values_equal(x, y) for y in b) for x in a)


def _a_equals(a, b):
    return len(a) == len(b) and all(_values_equal(x, y) for x, y in zip(a, b))


def _a_overlaps(a, b):
    return any(any(_values_equal(x, y) for y in b) for x in a)


# Letters folded although Unicode does not decompose them (NOTE under
# /req/text-manipulation/accent-insensitize names Ø -> O and Ł -> L).
EXTRA_FOLD = {
    "Ø": "O", "ø": "o", "Ł": "L", "ł": "l", "Đ": "D", "đ": "d", "Ħ": "H", "ħ": "h",
    "Ŧ": "T", "ŧ": "t", "ı": "i", "Ŀ": "L", "ŀ": "l", "Ɨ": "I", "ɨ": "i", "Ƶ": "Z", "ƶ": "z",
}
DAKUTEN = {"゙", "゚"}


def accent_insensitize(s):
    out = []
    for ch in s:
        if ch in EXTRA_FOLD:
            out.append(EXTRA_FOLD[ch])
            continue
        d = unicodedata.normalize("NFD", ch)
        kept = [c for c in d if not (unicodedata.combining(c) and c not in DAKUTEN)]
        out.append(unicodedata.normalize("NFC", "".join(kept)))
    return "".join(out)


def case_insensitize(s):
    return s.casefold()


_FMT_RE = re.compile(r"%(?P<flags>[-+ #0]*)(?P<width>\*|\d+)?(?:\.(?P<prec>\*|\d+))?(?P<len>hh|h|ll|l|L|z|j|t)?(?P<conv>[diouxXeEfFgGaAcspn%])")


def printf_format(args):
    """C printf conversions; returns NULL if the arguments do not match the specifiers."""
    if not args or not is_text(args[0]):
        return NULL
    f, rest = args[0], list(args[1:])
    out = []
    pos = 0
    for m in _FMT_RE.finditer(f):
        out.append(f[pos:m.start()])
        pos = m.end()
        conv = m.group("conv")
        if conv == "%":
            out.append("%")
            continue
        if conv in "np" or m.group("width") == "*" or m.group("prec") == "*":
            return NULL  # not supported / not meaningful here
        if not rest:
            return NULL
        a = rest.pop(0)
        spec = "%" + (m.group("flags") or "") + (m.group("width") or "") + \
            ("." + m.group("prec") if m.group("prec") is not None else "")
        if conv in "diouxXc":
            if not is_int(a):
                return NULL
            c = "d" if conv in "iu" else conv
            if conv == "c":
                out.append((spec + "c") % chr(a))
            else:
                out.append((spec + c) % a)
        elif conv in "eEfFgGaA":
            if not is_num(a):
                return NULL
            if conv in "aA":
                out.append(float(a).hex())
            else:
                out.append((spec + conv) % float(a))
        elif conv == "s":
            if not is_text(a):
                return NULL
            out.append((spec + "s") % a)
    out.append(f[pos:])
    if rest:
        return NULL  # extra arguments do not match any specifier
    return "".join(out)


# name -> (params or None for custom matching, impl)
FUNCTIONS = {
    # Math (UML: all double except round -> long)
    "abs": ([D], lambda x: abs(x)),
    "acos": ([D], _safe(math.acos)),
    "asin": ([D], _safe(math.asin)),
    "atan": ([D], math.atan),
    "atan2": ([D, D], math.atan2),
    "ceil": ([D], lambda x: float(math.ceil(x))),
    "cos": ([D], _safe(math.cos)),
    "cosh": ([D], _safe(math.cosh)),
    "exp": ([D], _safe(math.exp)),
    "floor": ([D], lambda x: float(math.floor(x))),
    "log": ([D], _safe(math.log)),
    "log10": ([D], _safe(math.log10)),
    "max": ([D, D], lambda x, y: max(x, y)),
    "min": ([D, D], lambda x, y: min(x, y)),
    "pow": ([D, D], _safe(lambda x, y: math.pow(x, y))),
    "random": ([], lambda: _random.random()),
    "round": ([D], _round_half_away),
    "sin": ([D], _safe(math.sin)),
    "sinh": ([D], _safe(math.sinh)),
    "sqrt": ([D], _safe(math.sqrt)),
    "tan": ([D], _safe(math.tan)),
    "tanh": ([D], math.tanh),
    # Text relation
    "contains": ([S, S], lambda a, b: b in a),
    "startsWith": ([S, S], lambda a, b: a.startswith(b)),
    "endsWith": ([S, S], lambda a, b: a.endswith(b)),
    # Array relations
    "a_containedBy": ([A, A], _a_containedBy),
    "a_contains": ([A, A], lambda a, b: _a_containedBy(b, a)),
    "a_equals": ([A, A], _a_equals),
    "a_overlaps": ([A, A], _a_overlaps),
    # Text manipulation
    "caseInsensitize": ([S], case_insensitize),
    "accentInsensitize": ([S], accent_insensitize),
    "lowerCase": ([S], lambda s: s.lower()),
    "upperCase": ([S], lambda s: s.upper()),
    "concatenate": ([S, S], lambda a, b: a + b),
    "substitute": ([S, S, S], lambda s, a, b: s.replace(a, b) if a else s),
    "format": (None, printf_format),
}
# CQL2 names used by the JSON schema (casei / accenti), see notes.md
FUNCTIONS["casei"] = FUNCTIONS["caseInsensitize"]
FUNCTIONS["accenti"] = FUNCTIONS["accentInsensitize"]


def call_function(name, args):
    if name not in FUNCTIONS:
        raise EvalError("unknown function '%s'" % name)
    params, impl = FUNCTIONS[name]
    if params is None:
        return impl(args)
    conv = _match(args, params)
    if conv is None:
        return NULL  # /req/functions/call-expressions, last part
    return impl(*conv)


# ---------------------------------------------------------------- operators

def _like(text, pattern):
    # Only % and _ are special (/req/text-relation/like); no escape character.
    rx = []
    for ch in pattern:
        if ch == "%":
            rx.append(".*")
        elif ch == "_":
            rx.append(".")
        else:
            rx.append(re.escape(ch))
    return re.fullmatch("".join(rx), text, flags=re.S) is not None


def _compare(op, a, b):
    if a is NULL or b is NULL:
        return NULL
    if is_num(a) and is_num(b):
        pass
    elif is_text(a) and is_text(b):
        pass
    elif isinstance(a, bool) and isinstance(b, bool):
        if op not in ("=", "<>"):
            return NULL
    elif isinstance(a, list) and isinstance(b, list):
        if op not in ("=", "<>"):
            return NULL
        e = _a_equals(a, b)
        return e if op == "=" else not e
    else:
        # different types: not specified; treat = / <> as unequal, others NULL
        if op == "=":
            return False
        if op == "<>":
            return True
        return NULL
    return {
        "=": lambda: a == b, "<>": lambda: a != b, "<": lambda: a < b,
        ">": lambda: a > b, "<=": lambda: a <= b, ">=": lambda: a >= b,
    }[op]()


def _arith(op, a, b):
    if a is NULL or b is NULL:
        return NULL
    if not (is_num(a) and is_num(b)):
        return NULL
    try:
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                return NULL
            return float(a) / float(b)
        if op in ("div", "intDiv"):
            if b == 0:
                return NULL
            q = a / b
            return int(math.trunc(q)) if is_int(a) and is_int(b) else int(math.trunc(q))
        if op in ("%", "mod"):
            if b == 0:
                return NULL
            return math.fmod(a, b) if not (is_int(a) and is_int(b)) else int(math.fmod(a, b))
        if op == "^":
            if is_int(a) and is_int(b) and b >= 0:
                return a ** b
            return math.pow(a, b)
    except (OverflowError, ValueError):
        return NULL
    raise EvalError("unknown arithmetic operator " + op)


def _and(vals):
    if any(v is False for v in vals):
        return False
    if any(v is NULL for v in vals):
        return NULL
    if all(v is True for v in vals):
        return True
    return NULL


def _or(vals):
    if any(v is True for v in vals):
        return True
    if any(v is NULL for v in vals):
        return NULL
    if all(v is False for v in vals):
        return False
    return NULL


def evaluate(node, ctx):
    if node is None or isinstance(node, (bool, int, float, str)):
        return node
    if isinstance(node, list):
        return [evaluate(e, ctx) for e in node]
    if not isinstance(node, dict):
        raise EvalError("unsupported node %r" % (node,))
    if "property" in node:
        return ctx.prop(node["property"])
    if "sysId" in node:
        return ctx.sysid(node["sysId"])
    if "$ref" in node:
        ref = node["$ref"]
        m = re.fullmatch(r"#/\$variables/(.+)", ref)
        if not m:
            raise EvalError("unsupported $ref " + ref)
        return ctx.var(m.group(1))
    if "op" not in node:
        raise EvalError("unsupported object %r" % (node,))
    op = node["op"]
    args = node.get("args", [])
    if op == "?:":
        if len(args) != 3:
            raise EvalError("conditional needs 3 args")
        c = evaluate(args[0], ctx)
        return evaluate(args[1] if c is True else args[2], ctx)
    if op in ("and", "or"):
        vals = [evaluate(a, ctx) for a in args]
        for v in vals:
            if v is not NULL and not isinstance(v, bool):
                return NULL
        return _and(vals) if op == "and" else _or(vals)
    if op == "not":
        v = evaluate(args[0], ctx)
        if v is NULL or not isinstance(v, bool):
            return NULL
        return not v
    if op in ("=", "<>", "<", ">", "<=", ">="):
        return _compare(op, evaluate(args[0], ctx), evaluate(args[1], ctx))
    if op in ("like", "notLike"):
        a, p = evaluate(args[0], ctx), evaluate(args[1], ctx)
        if a is NULL or p is NULL:
            return NULL
        if not (is_text(a) and is_text(p)):
            return NULL
        r = _like(a, p)
        return r if op == "like" else not r
    if op in ("between", "notBetween"):
        v, lo, hi = (evaluate(a, ctx) for a in args)
        if NULL in (v, lo, hi):
            return NULL
        r = _and([_compare(">=", v, lo), _compare("<=", v, hi)])
        if r is NULL:
            return NULL
        return r if op == "between" else not r
    if op in ("in", "notIn"):
        v = evaluate(args[0], ctx)
        lst = evaluate(args[1], ctx)
        if v is NULL or lst is NULL:
            return NULL
        if not isinstance(lst, list):
            raise EvalError("in: right operand is not an array")
        res = [_compare("=", v, e) for e in lst]
        r = _or(res) if res else False
        if r is NULL:
            return NULL
        return r if op == "in" else not r
    if op in ("isNull", "isNotNull"):
        v = evaluate(args[0], ctx)
        return (v is NULL) if op == "isNull" else (v is not NULL)
    if op in ("+", "-", "*", "/", "^", "div", "intDiv", "%", "mod"):
        if len(args) == 1 and op in ("+", "-"):
            v = evaluate(args[0], ctx)
            if v is NULL:
                return NULL
            if not is_num(v):
                return NULL
            return -v if op == "-" else v
        if len(args) != 2:
            raise EvalError("arithmetic operator needs 2 operands")
        return _arith(op, evaluate(args[0], ctx), evaluate(args[1], ctx))
    # function call
    vals = [evaluate(a, ctx) for a in args]
    return call_function(op, vals)


# ---------------------------------------------------------------- CartoSym-CSS lexer

KEYWORDS = {"in": "IN", "not": "NOT", "is": "IS", "like": "LIKE", "between": "BETWEEN",
            "and": "AND", "or": "OR", "div": "IDIV"}
UNITS = ["px", "m", "ft", "pc", "pt", "em", "inch", "cm", "mm"]
WS_CHARS = set("\u0009\u000A\u000B\u000C\u000D \u0085      "
               "           　")
PUNCT = [("<>", "NEQ"), ("<=", "LTEQ"), (">=", "GTEQ"), ("{", "LCBR"), ("}", "RCBR"),
         (".", "DOT"), (";", "SEMI"), ("[", "LSBR"), ("]", "RSBR"), ("(", "LPAR"),
         (")", "RPAR"), (",", "COMMA"), ("=", "EQ"), ("<", "LT"), (">", "GT"),
         ("?", "QUESTION"), (":", "COLON"), ("*", "MUL"), ("/", "DIV"), ("%", "MOD"),
         ("^", "POW"), ("-", "MINUS"), ("+", "PLUS"), ("@", "AT_SIGN")]


def _ident_start(c):
    o = ord(c)
    return (c == "_" or "A" <= c <= "Z" or "a" <= c <= "z" or 0xC0 <= o <= 0xD6 or 0xD8 <= o <= 0xF6
            or 0xF8 <= o <= 0x2FF or 0x370 <= o <= 0x37D or 0x37F <= o <= 0x1FFE or 0x200C <= o <= 0x200D
            or 0x2070 <= o <= 0x218F or 0x2C00 <= o <= 0x2FEF or 0x3001 <= o <= 0xD7FF
            or 0xF900 <= o <= 0xFDCF or 0xFDF0 <= o <= 0xFFFD)


def _ident_part(c):
    o = ord(c)
    return _ident_start(c) or "0" <= c <= "9" or 0x300 <= o <= 0x36F or 0x203F <= o <= 0x2040


_NUM_RE = re.compile(r"(?:[0-9]+(?:\.(?:[0-9]+)?)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_HEX_RE = re.compile(r"#[0-9a-fA-F]+")
_WS_RE = re.compile(r"[ \t\r\n]+")


class Tok:
    def __init__(self, type_, text, value=None, pos=0):
        self.type, self.text, self.value, self.pos = type_, text, value, pos

    def __repr__(self):
        return "%s(%r)" % (self.type, self.text)


class LexError(Exception):
    pass


def _char_literal_part(src, i):
    """src[i] == "'"; returns (end, value) of one quoted part, or raises."""
    j = i + 1
    val = []
    while j < len(src):
        c = src[j]
        if c == "'":
            if j + 1 < len(src) and src[j + 1] == "'":
                val.append("'")
                j += 2
                continue
            return j + 1, "".join(val)
        if c == "\\" and j + 1 < len(src) and src[j + 1] == "'":
            val.append("'")
            j += 2
            continue
        val.append(c)
        j += 1
    raise LexError("unterminated character literal at %d" % i)


def tokenize(src):
    """Longest match, earlier rule wins ties (ANTLR lexer semantics) for the rules in
    CartoSym-CSS-Lexer.g4. Whitespace and comments go to hidden channels (dropped)."""
    toks = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        cands = []  # (length, order, type, value)
        # comments
        if src.startswith("/*", i):
            e = src.find("*/", i + 2)
            if e < 0:
                raise LexError("unterminated comment")
            cands.append((e + 2 - i, 100, "COMMENT", None))
        if src.startswith("//", i):
            e = i
            while e < n and src[e] not in "\r\n":
                e += 1
            cands.append((e - i, 101, "LINE_COMMENT", None))
        m = _WS_RE.match(src, i)
        if m:
            cands.append((m.end() - i, 102, "WS", None))
        for order, (p, t) in enumerate(PUNCT):
            if src.startswith(p, i):
                cands.append((len(p), order, t, None))
        # keywords (case-insensitive)
        for order, (kw, t) in enumerate(KEYWORDS.items()):
            if src[i:i + len(kw)].lower() == kw:
                cands.append((len(kw), 30 + order, t, None))
        for u in UNITS:
            if src.startswith(u, i):
                cands.append((len(u), 50, "UNIT", u))
        m = _HEX_RE.match(src, i)
        if m:
            cands.append((m.end() - i, 51, "HEX_LITERAL", m.group(0)))
        m = _NUM_RE.match(src, i)
        if m:
            cands.append((m.end() - i, 52, "NUMERIC_LITERAL", m.group(0)))
        if c == "'":
            e, v = _char_literal_part(src, i)
            parts = [v]
            while True:
                m2 = _WS_RE.match(src, e)
                if m2 and m2.end() < n and src[m2.end()] == "'":
                    e2, v2 = _char_literal_part(src, m2.end())
                    parts.append(v2)
                    e = e2
                else:
                    break
            cands.append((e - i, 53, "CHARACTER_LITERAL", parts))
        if _ident_start(c):
            e = i + 1
            while e < n and _ident_part(src[e]):
                e += 1
            cands.append((e - i, 54, "IDENTIFIER", src[i:e]))
        if c == '"':
            e = i + 1
            while e < n and src[e] != '"' and src[e] != "'":
                e += 1
            if e < n and src[e] == '"':
                cands.append((e + 1 - i, 54, "IDENTIFIER", src[i + 1:e]))
        if not cands:
            raise LexError("unexpected character %r at %d" % (c, i))
        cands.sort(key=lambda x: (-x[0], x[1]))
        ln, _, t, v = cands[0]
        text = src[i:i + ln]
        if t not in ("COMMENT", "LINE_COMMENT", "WS"):
            toks.append(Tok(t, text, v, i))
        i += ln
    toks.append(Tok("EOF", "", None, n))
    return toks


# ---------------------------------------------------------------- CartoSym-CSS parser

class ParseError(Exception):
    pass


# binding powers, following the order of alternatives in CartoSym-CSS-Grammar.g4
BP_OR, BP_AND, BP_NOT, BP_BETWEEN, BP_REL, BP_ADD, BP_MUL, BP_POW, BP_UNARY, BP_POSTFIX = \
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11
BP_COND = 1

REL_OPS = {"EQ": "=", "NEQ": "<>", "LT": "<", "LTEQ": "<=", "GT": ">", "GTEQ": ">="}


class Parser:
    def __init__(self, toks, notes=None):
        self.t = toks
        self.i = 0
        self.notes = notes if notes is not None else []

    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def at(self, *types):
        return self.peek().type in types

    def eat(self, type_):
        tok = self.peek()
        if tok.type != type_:
            raise ParseError("expected %s, got %s %r at %d" % (type_, tok.type, tok.text, tok.pos))
        self.i += 1
        return tok

    # --- expressions
    def expression(self, min_bp=0):
        left = self.prefix()
        while True:
            tok = self.peek()
            tt = tok.type
            if tt == "DOT" and BP_POSTFIX >= min_bp:
                self.i += 1
                name = self.eat("IDENTIFIER").value
                left = self._member(left, name)
            elif tt == "LSBR" and BP_POSTFIX >= min_bp:
                self.i += 1
                c = self.constant()
                self.eat("RSBR")
                left = {"op": "[]", "args": [left, c]}
            elif tt == "POW" and BP_POW >= min_bp:
                self.i += 1
                left = {"op": "^", "args": [left, self.expression(BP_POW + 1)]}
            elif tt in ("MUL", "DIV", "IDIV", "MOD") and BP_MUL >= min_bp:
                self.i += 1
                op = {"MUL": "*", "DIV": "/", "IDIV": "div", "MOD": "%"}[tt]
                left = {"op": op, "args": [left, self.expression(BP_MUL + 1)]}
            elif tt in ("PLUS", "MINUS") and BP_ADD >= min_bp:
                self.i += 1
                op = "+" if tt == "PLUS" else "-"
                left = {"op": op, "args": [left, self.expression(BP_ADD + 1)]}
            elif BP_REL >= min_bp and self._rel_op() is not None:
                op, ln = self._rel_op()
                self.i += ln
                if op in ("isNull", "isNotNull"):
                    rhs = self.expression(BP_REL + 1)
                    if rhs is not None:
                        raise ParseError("'is' is only defined with the null literal as second operand")
                    left = {"op": op, "args": [left]}
                else:
                    left = {"op": op, "args": [left, self.expression(BP_REL + 1)]}
            elif BP_BETWEEN >= min_bp and (tt == "BETWEEN" or (tt == "NOT" and self.peek(1).type == "BETWEEN")):
                neg = tt == "NOT"
                self.i += 2 if neg else 1
                lo = self.expression(BP_ADD)  # betweenBound: arithmetic only
                self.eat("AND")
                hi = self.expression(BP_ADD)
                left = {"op": "notBetween" if neg else "between", "args": [left, lo, hi]}
            elif tt == "AND" and BP_AND >= min_bp:
                self.i += 1
                left = {"op": "and", "args": [left, self.expression(BP_AND + 1)]}
            elif tt == "OR" and BP_OR >= min_bp:
                self.i += 1
                left = {"op": "or", "args": [left, self.expression(BP_OR + 1)]}
            elif tt == "QUESTION" and BP_COND >= min_bp:
                self.i += 1
                then = self.expression(BP_COND)
                self.eat("COLON")
                els = self.expression(BP_COND)  # right associative
                left = {"op": "?:", "args": [left, then, els]}
            else:
                return left

    def _rel_op(self):
        tt = self.peek().type
        if tt in REL_OPS:
            return REL_OPS[tt], 1
        if tt == "IN":
            return "in", 1
        if tt == "LIKE":
            return "like", 1
        if tt == "IS":
            if self.peek(1).type == "NOT":
                return "isNotNull", 2
            return "isNull", 1
        if tt == "NOT" and self.peek(1).type == "IN":
            return "notIn", 2
        if tt == "NOT" and self.peek(1).type == "LIKE":
            return "notLike", 2
        return None

    def _member(self, left, name):
        # A dotted identifier path: system identifier or property path (see notes.md)
        if isinstance(left, dict) and left.get("_path"):
            return {"_path": left["_path"] + "." + name}
        return {"op": ".", "args": [left, name]}

    def constant(self):
        tok = self.peek()
        if tok.type == "NUMERIC_LITERAL":
            self.i += 1
            txt = tok.value
            v = float(txt) if any(ch in txt for ch in ".eE") else int(txt)
            if self.at("UNIT"):
                u = self.eat("UNIT").value
                return {"op": "unit", "args": [v, u]}
            return v
        if tok.type == "HEX_LITERAL":
            self.i += 1
            return {"op": "hex", "args": [tok.value]}
        raise ParseError("expected constant at %d" % tok.pos)

    def id_or_constant(self):
        tok = self.peek()
        if tok.type == "IDENTIFIER":
            self.i += 1
            return self._identifier(tok)
        return self.constant()

    def _identifier(self, tok):
        name = tok.value
        if not tok.text.startswith('"'):
            low = name.lower()
            if low == "true":
                return True
            if low == "false":
                return False
            if low == "null":
                return None
        return {"_path": name}

    def prefix(self):
        tok = self.peek()
        tt = tok.type
        if tt in ("PLUS", "MINUS"):
            self.i += 1
            operand = self.expression(BP_UNARY)
            if tt == "MINUS" and is_num(operand):
                return -operand
            return {"op": "+" if tt == "PLUS" else "-", "args": [operand]}
        if tt == "NOT":
            self.i += 1
            return {"op": "not", "args": [self.expression(BP_NOT)]}
        if tt == "AT_SIGN":
            self.i += 1
            name = self.eat("IDENTIFIER").value
            return {"$ref": "#/$variables/" + name}
        if tt == "CHARACTER_LITERAL":
            self.i += 1
            return "".join(tok.value)
        if tt == "LPAR":
            self.i += 1
            if self.at("RPAR"):
                self.i += 1
                return {"_array": []}
            first = self.expression()
            if self.at("RPAR"):
                self.i += 1
                return {"_paren": first}
            elems = [first]
            while self.at("COMMA"):
                self.i += 1
                elems.append(self.expression())
            self.eat("RPAR")
            return {"_array": elems}
        if tt == "LSBR":
            self.i += 1
            elems = []
            if not self.at("RSBR"):
                elems.append(self.expression())
                while self.at("COMMA"):
                    self.i += 1
                    elems.append(self.expression())
            self.eat("RSBR")
            return {"_array": elems}
        if tt == "LCBR":
            return self.instance(None)
        if tt == "IDENTIFIER" and self.peek(1).type == "LPAR":
            return self.call_or_instance()
        if tt == "IDENTIFIER" and self.peek(1).type == "LCBR":
            self.i += 1
            return self.instance(tok.value)
        if tt in ("IDENTIFIER", "NUMERIC_LITERAL", "HEX_LITERAL"):
            first = self.id_or_constant()
            items = [first]
            while self.at("IDENTIFIER", "NUMERIC_LITERAL", "HEX_LITERAL"):
                items.append(self.id_or_constant())
            if len(items) > 1:
                return {"_tuple": items}
            return first
        raise ParseError("unexpected %s %r at %d" % (tt, tok.text, tok.pos))

    def call_or_instance(self):
        name = self.eat("IDENTIFIER").value
        self.eat("LPAR")
        if self.at("RPAR"):
            self.i += 1
            # Grammar: expCall needs >= 1 argument; only expInstance matches NAME().
            self.notes.append("empty-call:" + name)
            return {"op": name, "args": [], "_empty_parens": True}
        items, named = self._assignment_list("RPAR")
        self.eat("RPAR")
        if named:
            return {"_instance": name, "members": items}
        return {"op": name, "args": items}

    def instance(self, cls):
        self.eat("LCBR")
        items, _ = ([], False) if self.at("RCBR") else self._assignment_list("RCBR")
        self.eat("RCBR")
        return {"_instance": cls, "members": items}

    def _assignment_list(self, closer):
        items = []
        named = False
        while True:
            if self.at("SEMI") and self.peek(1).type == closer:
                self.i += 1
                named = True
                break
            # propertyAssignment: lhValue ':' expression
            save = self.i
            if self.at("IDENTIFIER"):
                try:
                    self.lhvalue()
                    if self.at("COLON"):
                        self.i = save
                        lhs = self.lhvalue()
                        self.eat("COLON")
                        items.append({"_assign": lhs, "value": self.expression()})
                        named = True
                    else:
                        self.i = save
                        items.append(self.expression())
                except ParseError:
                    self.i = save
                    items.append(self.expression())
            else:
                items.append(self.expression())
            if self.at("SEMI"):
                named = True
                self.i += 1
                if self.at(closer):
                    break
                continue
            if self.at("COMMA"):
                self.i += 1
                continue
            break
        return items, named

    def lhvalue(self):
        parts = [self.eat("IDENTIFIER").value]
        while True:
            if self.at("DOT"):
                self.i += 1
                parts.append(self.eat("IDENTIFIER").value)
            elif self.at("LSBR"):
                self.i += 1
                parts.append(self.constant())
                self.eat("RSBR")
            else:
                return parts

    # --- style sheets
    def style_sheet(self):
        while self.at("DOT") and self.peek(1).type == "IDENTIFIER" and self.peek(2).type == "CHARACTER_LITERAL":
            self.i += 3
        while self.at("AT_SIGN"):
            self.i += 1
            self.eat("IDENTIFIER")
            self.eat("EQ")
            self.expression()
            self.eat("SEMI")
        while not self.at("EOF"):
            self.styling_rule()
        self.eat("EOF")

    def styling_rule(self):
        while True:
            if self.at("IDENTIFIER"):
                self.i += 1
            elif self.at("LSBR"):
                self.i += 1
                self.expression()
                self.eat("RSBR")
            else:
                break
        self.eat("LCBR")
        if self.at("DOT"):
            self.i += 1
            nm = self.eat("IDENTIFIER")
            if nm.value != "name":
                raise ParseError("only .name is valid inside a styling rule")
            self.eat("CHARACTER_LITERAL")
        if self._starts_assignment():
            self.property_assignment()
            while True:
                self.eat("SEMI")
                if self._starts_assignment():
                    self.property_assignment()
                else:
                    break
        while not self.at("RCBR"):
            self.styling_rule()
        self.eat("RCBR")

    def _starts_assignment(self):
        if not self.at("IDENTIFIER"):
            return False
        save = self.i
        try:
            self.lhvalue()
            return self.at("COLON")
        except ParseError:
            return False
        finally:
            self.i = save

    def property_assignment(self):
        self.lhvalue()
        self.eat("COLON")
        self.expression()


def finish(node, ctx_system_keys=()):
    """Turn parser-internal nodes into the CQL2-JSON shape."""
    if isinstance(node, list):
        return [finish(n, ctx_system_keys) for n in node]
    if not isinstance(node, dict):
        return node
    if "_paren" in node:
        return finish(node["_paren"], ctx_system_keys)
    if "_array" in node:
        return [finish(e, ctx_system_keys) for e in node["_array"]]
    if "_path" in node:
        path = node["_path"]
        root = path.split(".")[0]
        if root in SYSTEM_ROOTS or canonical_sysid(path) in ctx_system_keys:
            return {"sysId": path}
        return {"property": path}
    if "_tuple" in node:
        return {"op": "_tuple", "args": [finish(e, ctx_system_keys) for e in node["_tuple"]]}
    if "op" in node:
        return {"op": node["op"], "args": [finish(a, ctx_system_keys) for a in node.get("args", [])]}
    return node


def parse_expression(text, system_keys=(), notes=None):
    p = Parser(tokenize(text), notes)
    e = p.expression()
    p.eat("EOF")
    return finish(e, system_keys)


def check_style(text):
    try:
        p = Parser(tokenize(text))
        p.style_sheet()
        return "valid", None
    except (LexError, ParseError) as ex:
        return "invalid", str(ex)
