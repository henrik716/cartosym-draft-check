"""Evaluate CartoSym-JSON / CQL2-JSON expressions.

NULL is Python None.  An expression the text calls invalid raises EvalError.
"""
import math
import random as _rnd
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING, ROUND_FLOOR

INT_MIN, INT_MAX = -(2 ** 63), 2 ** 63 - 1


class EvalError(Exception):
    pass


class Context:
    def __init__(self, properties=None, system=None, definitions=None, variables=None):
        self.properties = properties or {}
        self.system = system or {}
        self.definitions = definitions or {}
        self.variables = variables or {}
        self._resolving = set()


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


# -- system identifiers
_ALIASES = {"viz": "visualization", "sd": "scaleDenominator", "id": "identifier"}


def _canon(name):
    parts = name.split(".")
    return ".".join(_ALIASES.get(p, p) if i < 2 else p for i, p in enumerate(parts))


def sys_value(name, ctx):
    if name in ctx.system:
        return ctx.system[name]
    c = _canon(name)
    for k, v in ctx.system.items():
        if _canon(k) == c:
            return v
    raise EvalError(f"no value for system identifier {name}")


# -- main
def evaluate(e, ctx):
    if e is None or isinstance(e, (bool, int, float, str)):
        return e
    if isinstance(e, list):
        return [evaluate(x, ctx) for x in e]
    if not isinstance(e, dict):
        raise EvalError(f"not an expression: {e!r}")
    if "property" in e:
        # A property the feature does not have resolves to NULL (see notes.md).
        return ctx.properties.get(e["property"])
    if "sysId" in e:
        return sys_value(e["sysId"], ctx)
    if "$ref" in e:
        return var_value(e["$ref"], ctx)
    if "op" in e:
        return operation(e["op"], e.get("args", []), ctx)
    if "date" in e or "timestamp" in e or "interval" in e:
        raise EvalError("temporal literals are not implemented")
    raise EvalError(f"unknown expression object {e!r}")


def var_value(ref, ctx):
    m = re.match(r"^[^#]*#/\$variables/([^/]+)$", ref)
    if not m:
        raise EvalError(f"bad variable reference {ref}")
    name = m.group(1)
    if name in ctx.variables:  # value set by the application at run time
        return ctx.variables[name]
    if name not in ctx.definitions:
        raise EvalError(f"undefined variable {name}")
    if name in ctx._resolving:
        raise EvalError(f"variable {name} is defined in terms of itself")
    ctx._resolving.add(name)
    try:
        return evaluate(ctx.definitions[name], ctx)
    finally:
        ctx._resolving.discard(name)


# -- three-valued logic (clause 7: "follow CQL2")
def _truth(v, op):
    if v is None or isinstance(v, bool):
        return v
    raise EvalError(f"operand of {op} is not a boolean: {v!r}")


def op_and(vals):
    vals = [_truth(v, "and") for v in vals]
    if any(v is False for v in vals):
        return False
    if any(v is None for v in vals):
        return None
    return True


def op_or(vals):
    vals = [_truth(v, "or") for v in vals]
    if any(v is True for v in vals):
        return True
    if any(v is None for v in vals):
        return None
    return False


def compare(op, a, b):
    if a is None or b is None:
        return None
    if is_num(a) and is_num(b):
        pass
    elif isinstance(a, str) and isinstance(b, str):
        pass
    elif isinstance(a, bool) and isinstance(b, bool):
        if op not in ("=", "<>"):
            raise EvalError("booleans can only be compared with = and <>")
    elif isinstance(a, list) and isinstance(b, list) and op in ("=", "<>"):
        return {"=": a == b, "<>": a != b}[op]
    else:
        raise EvalError(f"cannot compare {type(a).__name__} with {type(b).__name__}")
    return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]


def equal_or_null(a, b):
    """= with NULL giving NULL, mismatched types giving False."""
    if a is None or b is None:
        return None
    try:
        return compare("=", a, b)
    except EvalError:
        return False


def op_in(x, arr):
    if not isinstance(arr, list):
        raise EvalError("the second operand of in is not an array")
    if len(arr) == 0:
        return False  # /req/core/relational: empty array -> false, even for NULL
    if x is None:
        return None
    saw_null = False
    for el in arr:
        r = equal_or_null(x, el)
        if r is True:
            return True
        if r is None:
            saw_null = True
    return None if saw_null else False


def like(s, pat):
    if s is None or pat is None:
        return None
    if not isinstance(s, str) or not isinstance(pat, str):
        raise EvalError("like takes text operands")
    rx = []
    i = 0
    while i < len(pat):
        c = pat[i]
        if c == "\\":
            if i + 1 >= len(pat):
                raise EvalError("pattern ends with an escape character")
            rx.append(re.escape(pat[i + 1]))
            i += 2
            continue
        if c == "%":
            rx.append(".*")
        elif c == "_":
            rx.append(".")
        else:
            rx.append(re.escape(c))
        i += 1
    return re.fullmatch("".join(rx), s, re.S) is not None


# -- arithmetic (rc-arithmetic)
def arith(op, a, b):
    if a is None or b is None:
        return None
    if not (is_num(a) and is_num(b)):
        raise EvalError(f"operator {op} takes numeric operands")
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            return None
        return a / b  # real-valued quotient even for two integers
    if op == "div":
        if b == 0:
            return None
        if is_int(a) and is_int(b):
            q = abs(a) // abs(b)
            return q if (a >= 0) == (b >= 0) else -q
        return _to_int(math.trunc(a / b))
    if op == "%":
        if b == 0:
            return None
        if is_int(a) and is_int(b):
            q = abs(a) // abs(b)
            q = q if (a >= 0) == (b >= 0) else -q
            return a - b * q
        return math.fmod(a, b)
    if op == "^":
        return power(a, b)
    raise EvalError(f"unknown operator {op}")


def _is_integer_value(y):
    return is_int(y) or (isinstance(y, float) and y.is_integer())


def power(x, y):
    if x is None or y is None:
        return None
    if not (is_num(x) and is_num(y)):
        raise _Mismatch()
    if x == 0 and y < 0:
        return None
    if x < 0 and not _is_integer_value(y):
        return None
    if is_int(x) and is_int(y) and y >= 0:
        return x ** y
    try:
        r = float(x) ** float(y)
    except OverflowError:
        return None
    return r


def _to_int(v):
    if v is None:
        return None
    if v < INT_MIN or v > INT_MAX:
        return None
    return int(v)


class _Mismatch(Exception):
    """Arguments not matching the parameters -> NULL (/req/functions/call-expressions)."""


def _num_args(args, n=None, at_least=None):
    if n is not None and len(args) != n:
        raise _Mismatch()
    if at_least is not None and len(args) < at_least:
        raise _Mismatch()
    for a in args:
        if a is None:
            continue
        if not is_num(a):
            raise _Mismatch()
    return args


def _f1(fn, domain=None):
    def f(args):
        (x,) = _num_args(args, 1)
        if x is None:
            return None
        if domain and not domain(x):
            return None
        try:
            return fn(x)
        except (ValueError, OverflowError):
            return None
    return f


def _rounding(mode):
    def f(args):
        (x,) = _num_args(args, 1)
        if x is None:
            return None
        if is_int(x):
            return x
        if math.isnan(x) or math.isinf(x):
            return None
        return _to_int(int(Decimal(x).to_integral_value(rounding=mode)))
    return f


def _abs(args):
    (x,) = _num_args(args, 1)
    return None if x is None else abs(x)


def _atan2(args):
    y, x = _num_args(args, 2)
    if x is None or y is None:
        return None
    return math.atan2(y, x)


def _minmax(fn):
    def f(args):
        _num_args(args, at_least=1)
        if any(a is None for a in args):
            return None
        return fn(args)
    return f


def _pow(args):
    x, y = _num_args(args, 2)
    return power(x, y)


def _random(args):
    if args:
        raise _Mismatch()
    return _rnd.random()


# -- text
def _str_args(args, n=None, at_least=None):
    if n is not None and len(args) != n:
        raise _Mismatch()
    if at_least is not None and len(args) < at_least:
        raise _Mismatch()
    for a in args:
        if a is not None and not isinstance(a, str):
            raise _Mismatch()
    return args


def _text_rel(fn):
    def f(args):
        a, b = _str_args(args, 2)
        if a is None or b is None:
            return None
        return fn(a, b)
    return f


def _casei(args):
    (s,) = _str_args(args, 1)
    return None if s is None else s.casefold()


_KEEP_MARKS = {"゙", "゚"}  # Japanese dakuten / handakuten are not removed


def _fold_letter(ch):
    """Fold a letter that Unicode does not decompose to its base letter when its
    name is '<base letter name> WITH <modifier>' and the base letter exists
    (e.g. LATIN CAPITAL LETTER O WITH STROKE -> O)."""
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return ch
    if " WITH " not in name or "LETTER" not in name:
        return ch
    base = name.split(" WITH ")[0]
    try:
        b = unicodedata.lookup(base)
    except KeyError:
        return ch
    return b


def accenti(s):
    out = []
    for ch in unicodedata.normalize("NFD", s):
        if unicodedata.category(ch) == "Mn" and ch not in _KEEP_MARKS:
            continue
        out.append(ch)
    s2 = unicodedata.normalize("NFC", "".join(out))
    return "".join(_fold_letter(c) for c in s2)


def _accenti(args):
    (s,) = _str_args(args, 1)
    return None if s is None else accenti(s)


def _lower(args):
    (s,) = _str_args(args, 1)
    return None if s is None else s.lower()


def _upper(args):
    (s,) = _str_args(args, 1)
    return None if s is None else s.upper()


def _concat(args):
    _str_args(args, at_least=2)
    if any(a is None for a in args):
        return None
    return "".join(args)


def _substitute(args):
    s, a, b = _str_args(args, 3)
    if s is None or a is None or b is None:
        return None
    if a == "":
        return s
    return s.replace(a, b)  # every occurrence (see notes.md)


_SPEC = re.compile(r"%(?P<flags>[-+ #0]*)(?P<width>\d+|\*)?(?:\.(?P<prec>\d+|\*))?(?P<len>hh|h|ll|l|L|z|j|t)?(?P<conv>[diouxXeEfFgGcs%aA])")


def _format(args):
    if len(args) < 1 or not (args[0] is None or isinstance(args[0], str)):
        raise _Mismatch()
    f = args[0]
    if f is None:
        return None
    rest = list(args[1:])
    out = []
    pos = 0
    for m in _SPEC.finditer(f):
        out.append(f[pos:m.start()])
        pos = m.end()
        conv = m.group("conv")
        if conv == "%":
            out.append("%")
            continue
        if m.group("width") == "*" or m.group("prec") == "*":
            raise _Mismatch()
        if not rest:
            raise _Mismatch()
        v = rest.pop(0)
        if v is None:
            return None
        spec = "%" + m.group("flags") + (m.group("width") or "") + ("." + m.group("prec") if m.group("prec") else "")
        if conv in "diouxXc":
            if not is_int(v):
                raise _Mismatch()
            pyconv = {"i": "d", "u": "d"}.get(conv, conv)
            out.append((spec + pyconv) % v)
        elif conv in "eEfFgGaA":
            if not is_num(v):
                raise _Mismatch()
            if conv in "aA":
                out.append(float(v).hex())
            else:
                out.append((spec + conv) % v)
        elif conv == "s":
            if not isinstance(v, str):
                raise _Mismatch()
            out.append((spec + "s") % v)
    out.append(f[pos:])
    if rest:
        raise _Mismatch()
    return "".join(out)


# -- arrays
def _arr_args(args):
    if len(args) != 2:
        raise _Mismatch()
    a, b = args
    if a is None or b is None:
        return None
    if not isinstance(a, list) or not isinstance(b, list):
        raise _Mismatch()
    return a, b


def _member(x, arr):
    return any(equal_or_null(x, y) is True for y in arr)


def _a_contained_by(args):
    ab = _arr_args(args)
    if ab is None:
        return None
    a, b = ab
    return all(_member(x, b) for x in a)


def _a_contains(args):
    ab = _arr_args(args)
    if ab is None:
        return None
    a, b = ab
    return all(_member(x, a) for x in b)


def _a_equals(args):
    ab = _arr_args(args)
    if ab is None:
        return None
    a, b = ab
    # same number of elements, equal at the same position (ordered; see notes.md)
    return len(a) == len(b) and all(equal_or_null(x, y) is True for x, y in zip(a, b))


def _a_overlaps(args):
    ab = _arr_args(args)
    if ab is None:
        return None
    a, b = ab
    return any(_member(x, b) for x in a)


FUNCTIONS = {
    "abs": _abs,
    "acos": _f1(math.acos, lambda x: -1 <= x <= 1),
    "asin": _f1(math.asin, lambda x: -1 <= x <= 1),
    "atan": _f1(math.atan),
    "atan2": _atan2,
    "ceil": _rounding(ROUND_CEILING),
    "cos": _f1(math.cos),
    "cosh": _f1(math.cosh),
    "exp": _f1(math.exp),
    "floor": _rounding(ROUND_FLOOR),
    "log": _f1(math.log, lambda x: x > 0),
    "log10": _f1(math.log10, lambda x: x > 0),
    "max": _minmax(max),
    "min": _minmax(min),
    "pow": _pow,
    "random": _random,
    "round": _rounding(ROUND_HALF_UP),  # Decimal ROUND_HALF_UP: ties away from zero
    "sin": _f1(math.sin),
    "sinh": _f1(math.sinh),
    "sqrt": _f1(math.sqrt, lambda x: x >= 0),
    "tan": _f1(math.tan),
    "tanh": _f1(math.tanh),
    "contains": _text_rel(lambda a, b: b in a),
    "startsWith": _text_rel(lambda a, b: a.startswith(b)),
    "endsWith": _text_rel(lambda a, b: a.endswith(b)),
    "casei": _casei,
    "accenti": _accenti,
    "lowerCase": _lower,
    "upperCase": _upper,
    "concatenate": _concat,
    "substitute": _substitute,
    "format": _format,
    "a_containedBy": _a_contained_by,
    "a_contains": _a_contains,
    "a_equals": _a_equals,
    "a_overlaps": _a_overlaps,
}


def operation(op, args, ctx):
    if not isinstance(args, list):
        raise EvalError("args is not an array")
    if op == "and":
        return op_and([evaluate(a, ctx) for a in args])
    if op == "or":
        return op_or([evaluate(a, ctx) for a in args])
    if op == "not":
        if len(args) != 1:
            raise EvalError("not takes one operand")
        v = _truth(evaluate(args[0], ctx), "not")
        return None if v is None else (not v)
    if op in ("=", "<>", "<", ">", "<=", ">="):
        if len(args) != 2:
            raise EvalError(f"{op} takes two operands")
        return compare(op, evaluate(args[0], ctx), evaluate(args[1], ctx))
    if op == "isNull":
        if len(args) != 1:
            raise EvalError("isNull takes one operand")
        return evaluate(args[0], ctx) is None
    if op == "in":
        if len(args) != 2:
            raise EvalError("in takes two operands")
        return op_in(evaluate(args[0], ctx), evaluate(args[1], ctx))
    if op == "between":
        if len(args) != 3:
            raise EvalError("between takes three operands")
        x, lo, hi = (evaluate(a, ctx) for a in args)
        return op_and([compare(">=", x, lo), compare("<=", x, hi)])
    if op == "like":
        if len(args) != 2:
            raise EvalError("like takes two operands")
        return like(evaluate(args[0], ctx), evaluate(args[1], ctx))
    if op == "?:":
        if len(args) != 3:
            raise EvalError("?: takes three operands")
        c = evaluate(args[0], ctx)
        if c is not None and not isinstance(c, bool):
            raise EvalError("the condition is not a boolean")
        return evaluate(args[1] if c is True else args[2], ctx)
    if op == "-" and len(args) == 1:  # unary minus (no CartoSym-JSON encoding)
        v = evaluate(args[0], ctx)
        if v is None:
            return None
        if not is_num(v):
            raise EvalError("unary - takes a numeric operand")
        return -v
    if op in ("+", "-", "*", "/", "^", "%", "div"):
        if len(args) != 2:
            raise EvalError(f"{op} takes two operands")
        a, b = evaluate(args[0], ctx), evaluate(args[1], ctx)
        try:
            return arith(op, a, b)
        except _Mismatch:
            raise EvalError(f"operator {op} takes numeric operands")
    fn = FUNCTIONS.get(op)
    if fn is None:
        raise EvalError(f"unknown function {op}")
    vals = [evaluate(a, ctx) for a in args]
    try:
        return fn(vals)
    except _Mismatch:
        return None  # /req/functions/call-expressions: arguments do not match -> NULL
