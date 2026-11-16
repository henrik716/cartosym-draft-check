"""Expression evaluation for CartoSym-JSON (CQL2-JSON based) expressions.

Written from spec/1-core only (clause 7 Expressions, clause 14 arithmetic,
clause 16 / schema for the JSON shapes).
"""
import datetime as _dt
import math
import re

import numpy as np

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$")


def parse_instant(s):
    if isinstance(s, (_dt.date, _dt.datetime)):
        return s
    if isinstance(s, str):
        if _DATE_RE.match(s):
            return _dt.date.fromisoformat(s)
        if _TS_RE.match(s):
            t = s.replace("Z", "+00:00")
            return _dt.datetime.fromisoformat(t)
    return None


def _is_arr(v):
    return isinstance(v, np.ndarray)


def _coerce_pair(a, b):
    """Make two operands comparable (dates vs ISO strings)."""
    if isinstance(a, (_dt.date, _dt.datetime)) and isinstance(b, str):
        pb = parse_instant(b)
        if pb is not None:
            b = pb
    elif isinstance(b, (_dt.date, _dt.datetime)) and isinstance(a, str):
        pa = parse_instant(a)
        if pa is not None:
            a = pa
    # date vs datetime: compare on date
    if isinstance(a, _dt.datetime) and type(b) is _dt.date:
        a = a.date()
    elif isinstance(b, _dt.datetime) and type(a) is _dt.date:
        b = b.date()
    return a, b


def _cmp(op, a, b):
    if a is None or b is None:
        return None
    if not (_is_arr(a) or _is_arr(b)):
        a, b = _coerce_pair(a, b)
        # bool vs number: only equality is meaningful
        try:
            if op == "=":
                return a == b
            if op == "<>":
                return a != b
            if op == "<":
                return a < b
            if op == ">":
                return a > b
            if op == "<=":
                return a <= b
            if op == ">=":
                return a >= b
        except TypeError:
            return None
    else:
        return {"=": np.equal, "<>": np.not_equal, "<": np.less, ">": np.greater,
                "<=": np.less_equal, ">=": np.greater_equal}[op](a, b)
    raise ValueError(op)


def _and(vals):
    # Kleene three-valued logic
    if any(_is_arr(v) for v in vals):
        r = None
        for v in vals:
            v = np.asarray(v, dtype=bool) if v is not None else False
            r = v if r is None else np.logical_and(r, v)
        return r
    if any(v is False for v in vals):
        return False
    if any(v is None for v in vals):
        return None
    return True


def _or(vals):
    if any(_is_arr(v) for v in vals):
        r = None
        for v in vals:
            v = np.asarray(v, dtype=bool) if v is not None else False
            r = v if r is None else np.logical_or(r, v)
        return r
    if any(v is True for v in vals):
        return True
    if any(v is None for v in vals):
        return None
    return False


def _arith(op, a, b):
    if a is None or b is None:
        return None
    if isinstance(a, bool) or isinstance(b, bool):
        return None
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if _is_arr(a) or _is_arr(b):
            with np.errstate(divide="ignore", invalid="ignore"):
                return np.true_divide(a, b)
        if b == 0:
            return None
        return a / b
    if op in ("div", "intDiv"):
        if b == 0:
            return None
        return int(math.trunc(a / b))
    if op in ("%", "mod"):
        if b == 0:
            return None
        return math.fmod(a, b)
    if op == "^":
        return a ** b
    raise ValueError(op)


ARITH_OPS = {"+", "-", "*", "/", "^", "div", "intDiv", "%", "mod"}
CMP_OPS = {"=", "<>", "<", ">", "<=", ">="}


def is_expression(e):
    return isinstance(e, dict) and ("op" in e or "property" in e or "sysId" in e)


def evaluate(e, ctx):
    """Evaluate an expression. Plain objects that are not expressions (instances,
    unit-qualified values) are returned as-is for typed resolution later."""
    if e is None or isinstance(e, (bool, int, float, str)):
        return e
    if isinstance(e, list):
        return [evaluate(x, ctx) for x in e]
    if not isinstance(e, dict):
        return e
    if "property" in e and len([k for k in e if k != "$comment"]) == 1:
        return ctx.prop(e["property"])
    if "sysId" in e:
        return ctx.sys(e["sysId"])
    if "date" in e and len(e) == 1:
        return parse_instant(e["date"])
    if "timestamp" in e and len(e) == 1:
        return parse_instant(e["timestamp"])
    if "op" in e:
        op = e["op"]
        args = e.get("args", [])
        if op == "and":
            return _and([evaluate(a, ctx) for a in args])
        if op == "or":
            return _or([evaluate(a, ctx) for a in args])
        if op == "not":
            v = evaluate(args[0], ctx)
            if v is None:
                return None
            if _is_arr(v):
                return np.logical_not(v)
            return not v
        if op in CMP_OPS:
            return _cmp(op, evaluate(args[0], ctx), evaluate(args[1], ctx))
        if op == "isNull":
            v = evaluate(args[0], ctx) if isinstance(args, list) else evaluate(args, ctx)
            return v is None
        if op == "between":
            v, lo, hi = (evaluate(a, ctx) for a in args)
            return _and([_cmp(">=", v, lo), _cmp("<=", v, hi)])
        if op == "in":
            v = evaluate(args[0], ctx)
            lst = evaluate(args[1], ctx)
            if v is None:
                return None
            return any(_cmp("=", v, x) is True for x in lst)
        if op in ARITH_OPS:
            return _arith(op, evaluate(args[0], ctx), evaluate(args[1], ctx))
        if op == "?:":
            c = evaluate(args[0], ctx)
            if _is_arr(c):
                return np.where(c, evaluate(args[1], ctx), evaluate(args[2], ctx))
            return evaluate(args[1], ctx) if c is True else evaluate(args[2], ctx)
        raise NotImplementedError("operator %r" % op)
    # instance / unit object: leave for typed resolution
    return e
