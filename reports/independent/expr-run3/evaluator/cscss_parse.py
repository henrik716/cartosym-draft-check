"""CartoSym-CSS tokenizer, expression parser and style-sheet checker.

Written from schemas/CartoSym-CSS-Lexer.g4 and schemas/CartoSym-CSS-Grammar.g4.
Expressions are returned as the canonical tree used by cql2_eval.py.
Constructs the grammar accepts but this evaluator does not evaluate (instances,
tuples, colours, units, indexing) become {"op": "$unsupported"} nodes.
"""
import re

KEYWORDS = {"and", "or", "not", "in", "is", "like", "between", "div"}
UNITS = {"px", "m", "ft", "pc", "pt", "em", "inch", "cm", "mm"}

_START = [
    (0x5F, 0x5F), (0x41, 0x5A), (0x61, 0x7A), (0xC0, 0xD6), (0xD8, 0xF6),
    (0xF8, 0x2FF), (0x370, 0x37D), (0x37F, 0x1FFE), (0x200C, 0x200D),
    (0x2070, 0x218F), (0x2C00, 0x2FEF), (0x3001, 0xD7FF), (0xF900, 0xFDCF),
    (0xFDF0, 0xFFFD),
]

NUM_RE = re.compile(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
HEX_RE = re.compile(r"#[0-9a-fA-F]+")
PUNCT = ["<>", "<=", ">=", "(", ")", "[", "]", "{", "}", ",", ".", ";", "?", ":",
         "=", "<", ">", "*", "/", "%", "^", "-", "+"]

# Names that the JSON schema (sysId enum) or the CSCSS system identifier tables define.
SYSTEM_TABLE_NAMES = {
    "visualization", "visualization.scaleDenominator", "visualization.dateTime",
    "visualization.date", "visualization.timeOfDay", "visualization.timeInterval",
    "visualization.pass", "dataLayer", "dataLayer.identifier", "dataLayer.type",
}


SYSTEM_IDS = set(SYSTEM_TABLE_NAMES)  # run.py adds the JSON schema sysId enum


def is_system(name):
    return name in SYSTEM_IDS or name.startswith("capabilities.")


class SyntaxErr(Exception):
    pass


def _is_start(c):
    o = ord(c)
    return any(a <= o <= b for a, b in _START)


def _is_part(c):
    o = ord(c)
    return _is_start(c) or ("0" <= c <= "9") or (0x300 <= o <= 0x36F) or (0x203F <= o <= 0x2040)


def tokenize(s):
    toks = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r\n":
            i += 1
            continue
        if s.startswith("/*", i):
            j = s.find("*/", i + 2)
            if j < 0:
                raise SyntaxErr("unterminated comment")
            i = j + 2
            continue
        if s.startswith("//", i):
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "'":
            buf = []
            p = i + 1
            while True:
                if p >= n:
                    raise SyntaxErr("unterminated text literal")
                if s[p] == "'":
                    if p + 1 < n and s[p + 1] == "'":
                        buf.append("'")
                        p += 2
                        continue
                    p += 1
                    break
                if s[p] == "\\" and p + 1 < n and s[p + 1] == "'":
                    buf.append("'")
                    p += 2
                    continue
                buf.append(s[p])
                p += 1
            toks.append(("STR", "".join(buf)))
            i = p
            continue
        if c == '"':
            j = s.find('"', i + 1)
            if j < 0:
                raise SyntaxErr("unterminated quoted identifier")
            toks.append(("QID", s[i + 1:j]))
            i = j + 1
            continue
        if "0" <= c <= "9" or (c == "." and i + 1 < n and "0" <= s[i + 1] <= "9"):
            m = NUM_RE.match(s, i)
            toks.append(("NUM", m.group()))
            i = m.end()
            continue
        if c == "#":
            m = HEX_RE.match(s, i)
            if not m:
                raise SyntaxErr("bad hex literal")
            toks.append(("HEX", m.group()))
            i = m.end()
            continue
        if _is_start(c):
            j = i + 1
            while j < n and _is_part(s[j]):
                j += 1
            word = s[i:j]
            i = j
            lw = word.lower()
            if lw in KEYWORDS:
                toks.append(("KW", lw))
            elif word in UNITS:
                toks.append(("UNIT", word))
            else:
                toks.append(("ID", word))
            continue
        if c == "@":
            toks.append(("AT", "@"))
            i += 1
            continue
        for p in PUNCT:
            if s.startswith(p, i):
                toks.append(("P", p))
                i += len(p)
                break
        else:
            raise SyntaxErr("unexpected character %r" % c)
    toks.append(("EOF", None))
    return toks


def unsupported(what):
    return {"op": "$unsupported", "args": [what]}


class Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    # token helpers
    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def next(self):
        tok = self.t[self.i]
        if tok[0] != "EOF":
            self.i += 1
        return tok

    def is_p(self, val, k=0):
        tok = self.peek(k)
        return tok[0] == "P" and tok[1] == val

    def is_kw(self, val, k=0):
        tok = self.peek(k)
        return tok[0] == "KW" and tok[1] == val

    def expect_p(self, val):
        if not self.is_p(val):
            raise SyntaxErr("expected %r, found %r" % (val, self.peek()))
        self.next()

    def expect_kw(self, val):
        if not self.is_kw(val):
            raise SyntaxErr("expected %r" % val)
        self.next()

    def at_name(self, k=0):
        return self.peek(k)[0] in ("ID", "QID")

    # binary operators: (kind, binding power)
    def binop(self):
        t = self.peek()
        if t[0] == "P":
            if t[1] in ("=", "<>", "<", "<=", ">", ">="):
                return ("rel", 5)
            if t[1] in ("+", "-"):
                return ("add", 6)
            if t[1] in ("*", "/", "%"):
                return ("mul", 7)
            if t[1] == "^":
                return ("pow", 8)
            if t[1] == "?":
                return ("cond", 1)
            return None
        if t[0] == "KW":
            if t[1] == "or":
                return ("or", 2)
            if t[1] == "and":
                return ("and", 3)
            if t[1] in ("in", "is", "like", "between"):
                return ("kwrel", 5)
            if t[1] == "not" and self.peek(1)[0] == "KW" and self.peek(1)[1] in ("in", "like", "between"):
                return ("kwrel", 5)
            if t[1] == "div":
                return ("mul", 7)
        return None

    def parse_expr(self, min_bp=0):
        left = self.prefix()
        while True:
            b = self.binop()
            if b is None or b[1] < min_bp:
                break
            kind, bp = b
            t = self.next() if kind not in ("kwrel",) else self.peek()
            if kind == "cond":
                then = self.parse_expr(0)
                self.expect_p(":")
                els = self.parse_expr(1)
                left = {"op": "?:", "args": [left, then, els]}
                continue
            if kind in ("rel", "add", "mul", "pow", "and", "or"):
                op = {"div": "intDiv", "%": "mod"}.get(t[1], t[1])
                if kind == "mul" and t[0] == "KW":
                    op = "intDiv"
                right = self.parse_expr(bp + 1)
                left = {"op": op, "args": [left, right]}
                continue
            # keyword relations: [not] in / like / between / is [not] null
            negated = False
            if self.is_kw("not"):
                self.next()
                negated = True
            kw = self.next()[1]
            if kw == "is":
                if self.is_kw("not"):
                    self.next()
                    negated = not negated
                right = self.parse_expr(6)
                if right is None:
                    node = {"op": "isNull", "args": [left]}
                else:
                    node = unsupported("IS is only defined with NULL")
            elif kw == "in":
                right = self.parse_expr(6)
                node = {"op": "in", "args": [left, right]}
            elif kw == "like":
                right = self.parse_expr(6)
                node = {"op": "like", "args": [left, right]}
            elif kw == "between":
                lo = self.parse_expr(6)
                self.expect_kw("and")
                hi = self.parse_expr(6)
                node = {"op": "between", "args": [left, lo, hi]}
            else:
                raise SyntaxErr("unexpected keyword " + kw)
            if negated:
                node = {"op": "not", "args": [node]}
            left = node
        return left

    def prefix(self):
        kind, val = self.next()
        if kind == "NUM":
            if self.peek()[0] == "UNIT":
                self.next()
                node = unsupported("number with unit of measure")
            else:
                node = float(val) if ("." in val or "e" in val or "E" in val) else int(val)
            return self.tuple_tail(node)
        if kind == "STR":
            return val
        if kind == "HEX":
            return self.tuple_tail(unsupported("colour literal " + val))
        if kind in ("ID", "QID"):
            if kind == "ID" and val in ("true", "false", "null") and not self.is_p("("):
                node = {"true": True, "false": False, "null": None}[val]
                return self.tuple_tail(node)
            if self.is_p("("):
                self.next()
                if (self.at_name() and self.is_p(":", 1)):
                    self.parse_instance_items(")")
                    return unsupported("instance " + val)
                if self.is_p(")"):
                    raise SyntaxErr("call needs at least one argument (grammar)")
                args = [self.parse_expr(0)]
                while self.is_p(","):
                    self.next()
                    args.append(self.parse_expr(0))
                self.expect_p(")")
                return {"op": val, "args": args}
            if self.is_p("{"):
                self.next()
                self.parse_instance_items("}")
                return unsupported("instance " + val)
            name = val
            while self.is_p(".") and self.at_name(1):
                self.next()
                name += "." + self.next()[1]
            if is_system(name):
                node = {"sysId": name}
            else:
                node = {"property": name}
            return self.tuple_tail(node)
        if kind == "AT":
            if self.peek()[0] != "ID":
                raise SyntaxErr("expected variable name")
            name = self.next()[1]
            return {"$ref": "#/$variables/" + name}
        if kind == "P":
            if val == "(":
                if self.is_p(")"):
                    self.next()
                    return []
                e = self.parse_expr(0)
                if self.is_p(","):
                    elems = [e]
                    while self.is_p(","):
                        self.next()
                        elems.append(self.parse_expr(0))
                    self.expect_p(")")
                    return elems
                self.expect_p(")")
                return e
            if val == "[":
                elems = []
                if not self.is_p("]"):
                    elems.append(self.parse_expr(0))
                    while self.is_p(","):
                        self.next()
                        elems.append(self.parse_expr(0))
                self.expect_p("]")
                return elems
            if val == "{":
                self.parse_instance_items("}")
                return unsupported("instance")
            if val == "-":
                return {"op": "-", "args": [self.parse_expr(9)]}
            if val == "+":
                return {"op": "+", "args": [self.parse_expr(9)]}
        if kind == "KW" and val == "not":
            return {"op": "not", "args": [self.parse_expr(4)]}
        raise SyntaxErr("unexpected token %r" % (val,))

    def tuple_tail(self, node):
        """Juxtaposed idOrConstant tokens form a tuple (grammar: tuple)."""
        collected = False
        while self.peek()[0] in ("ID", "QID", "NUM", "HEX"):
            self.next()
            collected = True
        if collected:
            return unsupported("tuple")
        return node

    def lhv_ahead(self, k=0):
        """Absolute token index just after an lhValue starting at offset k, or None."""
        if not self.at_name(k):
            return None
        j = k + 1
        while True:
            if self.is_p(".", j) and self.at_name(j + 1):
                j += 2
            elif self.is_p("[", j) and self.peek(j + 1)[0] == "NUM" and self.is_p("]", j + 2):
                j += 3
            else:
                return self.i + j

    def is_assignment(self):
        j = self.lhv_ahead(0)
        return j is not None and self.t[min(j, len(self.t) - 1)] == ("P", ":")

    def parse_instance_items(self, close):
        while not self.is_p(close):
            if self.is_assignment():
                j = self.lhv_ahead(0)
                self.i = j + 1
                self.parse_expr(0)
            else:
                self.parse_expr(0)
            if self.is_p(";") or self.is_p(","):
                self.next()
                continue
            break
        if self.is_p(";"):
            self.next()
        self.expect_p(close)


def parse_expression(src):
    """Parse a CQL2-Text / CartoSym-CSS expression into the canonical tree."""
    p = Parser(tokenize(src))
    tree = p.parse_expr(0)
    if p.peek()[0] != "EOF":
        raise SyntaxErr("trailing input at %r" % (p.peek(),))
    return tree


# ---------------------------------------------------------------- style sheets

def _style_rule(p):
    selectors = 0
    while True:
        if p.at_name() and not p.is_assignment():
            p.next()
            selectors += 1
        elif p.is_p("["):
            p.next()
            p.parse_expr(0)
            p.expect_p("]")
            selectors += 1
        else:
            break
    p.expect_p("{")
    if p.is_p("."):
        p.next()
        if not p.at_name():
            raise SyntaxErr("expected rule name")
        p.next()
        if p.peek()[0] != "STR":
            raise SyntaxErr("expected quoted rule name")
        p.next()
    while p.is_assignment():
        p.i = p.lhv_ahead(0)
        p.expect_p(":")
        p.parse_expr(0)
        p.expect_p(";")
    while not p.is_p("}"):
        if p.is_assignment():
            raise SyntaxErr("symbolizer property after nested rule")
        if p.peek()[0] == "EOF":
            raise SyntaxErr("missing }")
        _style_rule(p)
    p.expect_p("}")


def check_style(src):
    """Return 'valid' or 'invalid' for a CartoSym-CSS style sheet (grammar only)."""
    try:
        p = Parser(tokenize(src))
        while p.is_p(".") and p.at_name(1) and p.peek(2)[0] == "STR":
            p.next()
            p.next()
            p.next()
        while p.peek()[0] == "AT":
            p.next()
            if not p.at_name():
                raise SyntaxErr("expected variable name")
            p.next()
            p.expect_p("=")
            p.parse_expr(0)
            p.expect_p(";")
        if p.peek()[0] == "EOF":
            return "valid"
        while p.peek()[0] != "EOF":
            _style_rule(p)
        return "valid"
    except SyntaxErr:
        return "invalid"
