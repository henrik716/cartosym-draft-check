"""Evaluator for the canonical expression tree (CQL2-JSON-like).

Both CartoSym-CSS text (via cscss_parse.py) and CartoSym-JSON / CQL2-JSON input
are reduced to the same tree shape: dicts with "op" and "args", {"property": name},
{"sysId": name}, {"$ref": "#/$variables/name"}, Python lists for arrays, and
Python scalars for literals (None is NULL).
"""
import math
import random
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP


class EvalErr(Exception):
    """The expression cannot be evaluated (reported as {"error": ...})."""


class Ctx:
    def __init__(self, props=None, system=None, defs=None, overrides=None):
        self.props = props or {}
        self.system = system or {}
        self.defs = defs or {}
        self.overrides = overrides or {}
        self.stack = []


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_bool(v):
    return isinstance(v, bool)


def is_text(v):
    return isinstance(v, str)


def is_arr(v):
    return isinstance(v, list)


def as_list(args):
    if isinstance(args, list):
        return args
    return [args]


# ---------------------------------------------------------------- comparisons

def cmp(op, a, b):
    """Relational operators. NULL on either side gives NULL; incompatible types give NULL."""
    if a is None or b is None:
        return None
    if is_num(a) and is_num(b):
        x, y = a, b
    elif is_text(a) and is_text(b):
        x, y = a, b
    elif is_bool(a) and is_bool(b):
        if op == "=":
            return a == b
        if op == "<>":
            return a != b
        return None
    else:
        return None
    if op == "=":
        return x == y
    if op == "<>":
        return x != y
    if op == "<":
        return x < y
    if op == "<=":
        return x <= y
    if op == ">":
        return x > y
    if op == ">=":
        return x >= y
    raise EvalErr("unknown comparison " + op)


def kleene_and(vals):
    saw_null = False
    for v in vals:
        if v is False:
            return False
        if v is None or not is_bool(v):
            saw_null = True
    return None if saw_null else True


def kleene_or(vals):
    saw_null = False
    for v in vals:
        if v is True:
            return True
        if v is None or not is_bool(v):
            saw_null = True
    return None if saw_null else False


def like_regex(pattern):
    out = []
    for ch in pattern:
        if ch == "%":
            out.append(".*")
        elif ch == "_":
            out.append(".")
        else:
            out.append(re.escape(ch))
    return re.compile("".join(out), re.DOTALL)


# ---------------------------------------------------------------- arithmetic

def arith(op, a, b):
    if a is None or b is None:
        return None
    if not (is_num(a) and is_num(b)):
        return None
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            return None
        return a / b
    if op == "intDiv":
        if b == 0:
            return None
        if isinstance(a, int) and isinstance(b, int):
            q = abs(a) // abs(b)
            return q if (a < 0) == (b < 0) else -q
        return int(math.trunc(a / b))
    if op == "mod":
        if b == 0:
            return None
        if isinstance(a, int) and isinstance(b, int):
            r = abs(a) % abs(b)
            return r if a >= 0 else -r
        return math.fmod(a, b)
    if op == "^":
        try:
            r = a ** b
        except (OverflowError, ZeroDivisionError):
            return None
        if isinstance(r, complex):
            return None
        if isinstance(a, int) and isinstance(b, int) and b >= 0:
            return int(r)
        return float(r)
    raise EvalErr("unknown arithmetic operator " + op)


# ---------------------------------------------------------------- standard functions

def _eq_elem(x, y):
    if is_num(x) and is_num(y):
        return x == y
    if is_text(x) and is_text(y):
        return x == y
    if is_bool(x) and is_bool(y):
        return x == y
    return False


def _in_list(e, lst):
    return any(_eq_elem(e, x) for x in lst)


def round_half_away(x):
    if isinstance(x, int):
        return x
    return int(Decimal(repr(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


_ACCENT_MAP = {"Ø": "O", "ø": "o", "Ł": "L", "ł": "l"}


def accent_fold(s):
    s2 = "".join(_ACCENT_MAP.get(c, c) for c in s)
    decomposed = unicodedata.normalize("NFD", s2)
    kept = "".join(
        c for c in decomposed
        if not (unicodedata.category(c) == "Mn" and c not in ("゙", "゚"))
    )
    return unicodedata.normalize("NFC", kept)


_PRINTF_RE = re.compile(
    r"%(?P<flags>[-+ #0]*)(?P<width>\*|\d+)?(?:\.(?P<prec>\*|\d*))?"
    r"(?P<len>hh|h|ll|l|L|q|j|z|t)?(?P<conv>[diouxXeEfFgGaAcspn])"
)


def printf_format(f, *args):
    stripped = f.replace("%%", "")
    if stripped.count("%") != len(list(_PRINTF_RE.finditer(stripped))):
        raise EvalErr("invalid format string")
    convs = [m.group("conv") for m in _PRINTF_RE.finditer(stripped)]
    if len(convs) != len(args):
        return None
    for c, a in zip(convs, args):
        if c in "diouxX":
            if not (is_num(a) and isinstance(a, int)):
                return None
        elif c == "c":
            if not ((is_num(a) and isinstance(a, int)) or (is_text(a) and len(a) == 1)):
                return None
        elif c in "eEfFgGaA":
            if not is_num(a):
                return None
        elif c == "s":
            if not is_text(a):
                return None
        else:
            return None
    return f % tuple(args)


def _substitute(s, a, b):
    if a == "":
        return s
    return s.replace(a, b)


# name -> (arity or None for variadic, parameter kinds, implementation)
# kinds: "n" numeric (int or real), "s" text, "a" array
FUNCS = {
    "abs": (1, ["n"], lambda x: abs(x)),
    "acos": (1, ["n"], math.acos),
    "asin": (1, ["n"], math.asin),
    "atan": (1, ["n"], math.atan),
    "atan2": (2, ["n", "n"], lambda y, x: math.atan2(y, x)),
    "ceil": (1, ["n"], lambda x: float(math.ceil(x))),
    "cos": (1, ["n"], math.cos),
    "cosh": (1, ["n"], math.cosh),
    "exp": (1, ["n"], math.exp),
    "floor": (1, ["n"], lambda x: float(math.floor(x))),
    "log": (1, ["n"], math.log),
    "log10": (1, ["n"], math.log10),
    "max": (2, ["n", "n"], lambda x, y: max(x, y)),
    "min": (2, ["n", "n"], lambda x, y: min(x, y)),
    "pow": (2, ["n", "n"], lambda x, y: math.pow(x, y)),
    "random": (0, [], lambda: random.random()),
    "round": (1, ["n"], round_half_away),
    "sin": (1, ["n"], math.sin),
    "sinh": (1, ["n"], math.sinh),
    "sqrt": (1, ["n"], math.sqrt),
    "tan": (1, ["n"], math.tan),
    "tanh": (1, ["n"], math.tanh),
    "a_containedBy": (2, ["a", "a"], lambda a, b: all(_in_list(e, b) for e in a)),
    "a_contains": (2, ["a", "a"], lambda a, b: all(_in_list(e, a) for e in b)),
    "a_equals": (2, ["a", "a"], lambda a, b: len(a) == len(b) and all(_eq_elem(x, y) for x, y in zip(a, b))),
    "a_overlaps": (2, ["a", "a"], lambda a, b: any(_in_list(e, b) for e in a)),
    "contains": (2, ["s", "s"], lambda a, b: b in a),
    "startsWith": (2, ["s", "s"], lambda a, b: a.startswith(b)),
    "endsWith": (2, ["s", "s"], lambda a, b: a.endswith(b)),
    "caseInsensitize": (1, ["s"], lambda s: s.casefold()),
    "accentInsensitize": (1, ["s"], accent_fold),
    "lowerCase": (1, ["s"], lambda s: s.lower()),
    "upperCase": (1, ["s"], lambda s: s.upper()),
    "concatenate": (2, ["s", "s"], lambda a, b: a + b),
    "substitute": (3, ["s", "s", "s"], _substitute),
    "format": (None, ["s"], printf_format),
}

# Names used in the CQL2 / JSON encodings for the same functions.
ALIASES = {"casei": "caseInsensitize", "accenti": "accentInsensitize"}


def call_function(name, arg_nodes, ctx):
    canon = ALIASES.get(name, name)
    if canon not in FUNCS:
        raise EvalErr("unknown function " + name)
    arity, kinds, impl = FUNCS[canon]
    vals = [ev(a, ctx) for a in arg_nodes]
    if any(v is None for v in vals):
        return None
    if arity is not None and len(vals) != arity:
        return None
    if canon == "format":
        if not kinds or not is_text(vals[0]):
            return None
        try:
            return impl(*vals)
        except (TypeError, ValueError):
            return None
    for v, k in zip(vals, kinds):
        if k == "n" and not is_num(v):
            return None
        if k == "s" and not is_text(v):
            return None
        if k == "a" and not is_arr(v):
            return None
    try:
        return impl(*vals)
    except (ValueError, OverflowError, ZeroDivisionError, TypeError):
        return None


# ---------------------------------------------------------------- evaluation

def ev_ref(ref, ctx):
    prefix = "#/$variables/"
    if not ref.startswith(prefix):
        raise EvalErr("unsupported reference " + ref)
    name = ref[len(prefix):]
    if name in ctx.overrides:
        return ctx.overrides[name]
    if name not in ctx.defs:
        raise EvalErr("undefined variable " + name)
    if name in ctx.stack:
        raise EvalErr("cyclic variable definition " + name)
    ctx.stack.append(name)
    try:
        return ev(ctx.defs[name], ctx)
    finally:
        ctx.stack.pop()


def ev_op(op, args, ctx):
    args = as_list(args)
    if op == "$unsupported":
        raise EvalErr("not evaluable: " + str(args[0]))
    if op == "?:":
        if len(args) != 3:
            raise EvalErr("conditional needs 3 operands")
        c = ev(args[0], ctx)
        if c is True:
            return ev(args[1], ctx)
        return ev(args[2], ctx)
    if op == "and":
        return kleene_and([ev(a, ctx) for a in args])
    if op == "or":
        return kleene_or([ev(a, ctx) for a in args])
    if op == "not":
        v = ev(args[0], ctx)
        if is_bool(v):
            return not v
        return None
    if op in ("=", "<>", "<", "<=", ">", ">="):
        return cmp(op, ev(args[0], ctx), ev(args[1], ctx))
    if op == "between":
        x, lo, hi = (ev(a, ctx) for a in args)
        a = cmp(">=", x, lo)
        b = cmp("<=", x, hi)
        if a is None or b is None:
            return None
        return a and b
    if op == "in":
        x = ev(args[0], ctx)
        arr = ev(args[1], ctx)
        if x is None or not is_arr(arr):
            return None
        null_seen = False
        for e in arr:
            c = cmp("=", x, e)
            if c is True:
                return True
            if c is None:
                null_seen = True
        return None if null_seen else False
    if op == "isNull":
        if len(args) != 1:
            raise EvalErr("isNull needs one operand")
        return ev(args[0], ctx) is None
    if op == "like":
        s, p = ev(args[0], ctx), ev(args[1], ctx)
        if s is None or p is None or not is_text(s) or not is_text(p):
            return None
        return like_regex(p).fullmatch(s) is not None
    if op in ("+", "-") and len(args) == 1:
        v = ev(args[0], ctx)
        if v is None or not is_num(v):
            return None
        return v if op == "+" else -v
    if op in ("+", "-", "*", "/", "^", "intDiv", "mod"):
        if len(args) != 2:
            raise EvalErr("operator " + op + " needs two operands")
        return arith(op, ev(args[0], ctx), ev(args[1], ctx))
    return call_function(op, args, ctx)


def ev(node, ctx):
    if node is None or isinstance(node, (bool, int, float, str)):
        return node
    if isinstance(node, list):
        return [ev(x, ctx) for x in node]
    if isinstance(node, dict):
        if "property" in node:
            return ctx.props.get(node["property"])
        if "sysId" in node:
            return ctx.system.get(node["sysId"])
        if "$ref" in node:
            return ev_ref(node["$ref"], ctx)
        if "op" in node:
            return ev_op(node["op"], node.get("args", []), ctx)
    raise EvalErr("cannot evaluate node " + repr(node))


def to_result(v):
    """Make the value JSON-representable; non-finite numbers are not a result."""
    if isinstance(v, float) and not math.isfinite(v):
        raise EvalErr("non-finite number")
    if isinstance(v, list):
        return [to_result(x) for x in v]
    return v
