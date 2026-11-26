"""CQL2-JSON-based expression evaluation for CartoSym-JSON (clause 7, clause 17).

Null handling: three-valued (Kleene) logic, as SQL / CQL2 (see notes.md, N-EXPR-NULL).
"""
import math
import re

EXPR_KEYS = ("op", "property", "sysId", "$ref")


def is_expression(v):
    return isinstance(v, dict) and any(k in v for k in EXPR_KEYS)


class Context:
    def __init__(self, props, sysids, variables=None):
        self.props = props
        self.sysids = sysids
        self.variables = variables or {}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _eq(a, b):
    if a is None or b is None:
        return None
    if _num(a) and _num(b):
        return float(a) == float(b)
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_eq(x, y) is True for x, y in zip(a, b))
    return False  # different types: not equal (no coercion)


def _cmp(a, b):
    if a is None or b is None:
        return None
    if _num(a) and _num(b):
        return (float(a) > float(b)) - (float(a) < float(b))
    if isinstance(a, str) and isinstance(b, str):
        return (a > b) - (a < b)
    return None  # not comparable -> unknown


def _like(s, pat):
    if s is None or pat is None:
        return None
    rx = ""
    i = 0
    while i < len(pat):
        c = pat[i]
        if c == "\\" and i + 1 < len(pat):
            rx += re.escape(pat[i + 1])
            i += 2
            continue
        rx += ".*" if c == "%" else "." if c == "_" else re.escape(c)
        i += 1
    return re.fullmatch(rx, s, re.S) is not None


def evaluate(e, ctx):
    if e is None or isinstance(e, (bool, int, float, str)):
        return e
    if isinstance(e, list):
        return [evaluate(x, ctx) for x in e]
    if not isinstance(e, dict):
        return e
    if "property" in e:
        return ctx.props.get(e["property"])  # by name, exactly as in the data
    if "sysId" in e:
        return ctx.sysids.get(e["sysId"])
    if "$ref" in e:
        name = e["$ref"].split("/")[-1]
        return evaluate(ctx.variables.get(name), ctx)
    if "op" not in e:
        return e  # an instance literal (e.g. a Color object): returned as is
    op = e["op"]
    args = e.get("args", [])
    if op in ("and", "or"):
        vals = [evaluate(a, ctx) for a in args]
        vals = [v if isinstance(v, bool) or v is None else None for v in vals]
        if op == "and":
            if any(v is False for v in vals):
                return False
            return None if any(v is None for v in vals) else True
        if any(v is True for v in vals):
            return True
        return None if any(v is None for v in vals) else False
    if op == "not":
        v = evaluate(args[0], ctx)
        return None if not isinstance(v, bool) else (not v)
    if op == "?:":
        c = evaluate(args[0], ctx)
        return evaluate(args[1] if c is True else args[2], ctx)
    if op == "isNull":
        return evaluate(args[0], ctx) is None
    a = [evaluate(x, ctx) for x in args]
    if op == "=":
        return _eq(a[0], a[1])
    if op == "<>":
        r = _eq(a[0], a[1])
        return None if r is None else (not r)
    if op in ("<", ">", "<=", ">="):
        c = _cmp(a[0], a[1])
        if c is None:
            return None
        return {"<": c < 0, ">": c > 0, "<=": c <= 0, ">=": c >= 0}[op]
    if op == "between":
        lo, hi = _cmp(a[0], a[1]), _cmp(a[0], a[2])
        if lo is None or hi is None:
            return None
        return lo >= 0 and hi <= 0
    if op == "in":
        v, lst = a[0], a[1]
        if v is None or lst is None:
            return None
        if not isinstance(lst, list):
            lst = [lst]
        res = [_eq(v, x) for x in lst]
        if any(r is True for r in res):
            return True
        return None if any(r is None for r in res) else False
    if op == "like":
        return _like(a[0], a[1])
    # arithmetic and functions
    if any(x is None for x in a):
        return None
    try:
        if op == "abs":
            return abs(a[0])
        if op == "+":
            return a[0] + a[1]
        if op == "-":
            return -a[0] if len(a) == 1 else a[0] - a[1]
        if op == "*":
            return a[0] * a[1]
        if op == "/":
            return a[0] / a[1] if a[1] != 0 else None
        if op == "%":
            return math.fmod(a[0], a[1]) if a[1] != 0 else None
        if op == "div":
            return int(a[0] // a[1]) if a[1] != 0 else None
        if op == "^":
            return a[0] ** a[1]
        if op in ("round", "floor", "ceil"):
            f = {"round": lambda x: math.floor(x + 0.5), "floor": math.floor, "ceil": math.ceil}[op]
            return int(f(a[0])) if math.isfinite(a[0]) else None
        if op == "min":
            return min(a)
        if op == "max":
            return max(a)
        if op == "sqrt":
            return math.sqrt(a[0])
        if op == "concatenate":
            return "".join(str(x) for x in a)
        if op == "upperCase":
            return a[0].upper()
        if op == "lowerCase":
            return a[0].lower()
    except Exception:
        return None
    return None  # unknown function: null


def references_vendor_sysid(e):
    """True if a vendor System Identifier (not a capabilities.vendor.* one) is used (clause 7, Vendor Extensions)."""
    if isinstance(e, dict):
        s = e.get("sysId")
        if isinstance(s, str) and "vendor." in s and not s.startswith("capabilities."):
            return True
        return any(references_vendor_sysid(v) for v in e.values())
    if isinstance(e, list):
        return any(references_vendor_sysid(v) for v in e)
    return False


def collect_pass_values(style, sysnames):
    """Literal integers compared for equality (or `in`) with a pass System Identifier anywhere in the selectors."""
    found = set()

    def walk(e):
        if isinstance(e, dict):
            if e.get("op") in ("=", "in") and len(e.get("args", [])) == 2:
                x, y = e["args"]
                for s, lit in ((x, y), (y, x)):
                    if isinstance(s, dict) and s.get("sysId") in sysnames:
                        vals = lit if isinstance(lit, list) else [lit]
                        for v in vals:
                            if _num(v) and float(v).is_integer():
                                found.add(int(v))
            for v in e.values():
                walk(v)
        elif isinstance(e, list):
            for v in e:
                walk(v)

    def walk_rules(rules):
        for r in rules:
            if "selector" in r:
                walk(r["selector"])
            walk_rules(r.get("nestedRules", []))

    walk_rules(style.get("stylingRules", []))
    return found
