"""Expression evaluation for CartoSym-JSON (CQL2-JSON based) expressions.

Written from spec/1-core only. Values may be Python scalars or numpy arrays
(for coverage cells); None is the null value.
"""
import datetime as _dt
import re

import numpy as np

EXPR_KEYS = ("op", "property", "sysId", "date", "timestamp", "interval", "$ref")

# Aliases between the System Identifier names of clause 7 / 8 and the
# names enumerated in the JSON schema (see notes.md, N-SYSID).
SYSID_ALIASES = {
    "visualization": "viz",
    "visualization.scaleDenominator": "viz.sd",
    "viz.scaleDenominator": "viz.sd",
    "dataLayer.identifier": "dataLayer.id",
    "feature.identifier": "feature.id",
    "feature.geometryDimension": "feature.geometryDimensions",
    "dataLayer.featuresGeometryDimension": "dataLayer.featuresGeometryDimensions",
}


def is_expr(v):
    return isinstance(v, dict) and any(k in v for k in EXPR_KEYS)


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")


def _parse_temporal(s):
    if isinstance(s, str):
        if _DATE_RE.match(s):
            return _dt.date.fromisoformat(s)
        if _TS_RE.match(s):
            return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return s


def _coerce_pair(a, b):
    """Coerce a text value to a date/time when compared with a temporal value
    (validDate is a text property holding an ISO date)."""
    temporal = (_dt.date, _dt.datetime)
    if isinstance(a, temporal) and isinstance(b, str):
        b = _parse_temporal(b)
    elif isinstance(b, temporal) and isinstance(a, str):
        a = _parse_temporal(a)
    if isinstance(a, _dt.datetime) and type(b) is _dt.date:
        b = _dt.datetime(b.year, b.month, b.day)
    elif isinstance(b, _dt.datetime) and type(a) is _dt.date:
        a = _dt.datetime(a.year, a.month, a.day)
    return a, b


def _is_num(v):
    return isinstance(v, (int, float, np.ndarray, np.number)) and not isinstance(v, bool)


class Context:
    def __init__(self, props=None, sys=None):
        self.props = props or {}
        self.sys = sys or {}

    def sysid(self, name):
        name = SYSID_ALIASES.get(name, name)
        if name.startswith("visualization."):
            name = "viz." + name[len("visualization."):]
        if name in self.sys:
            return self.sys[name]
        if name.startswith("capabilities."):
            return self.sys.get("capabilities", {}).get(name[len("capabilities."):], False)
        # walk sub-members (e.g. viz.timeInterval.start.date)
        parts = name.split(".")
        for i in range(len(parts) - 1, 0, -1):
            head = ".".join(parts[:i])
            if head in self.sys:
                v = self.sys[head]
                for p in parts[i:]:
                    v = _member(v, p)
                return v
        return None


def _member(v, p):
    if v is None:
        return None
    if isinstance(v, dict):
        return v.get(p)
    if isinstance(v, _dt.datetime):
        return {"date": v.date(), "time": v.time(), "year": v.year, "month": v.month,
                "day": v.day, "hour": v.hour, "minutes": v.minute, "seconds": v.second}.get(p)
    if isinstance(v, _dt.date):
        return {"year": v.year, "month": v.month, "day": v.day}.get(p)
    if isinstance(v, _dt.time):
        return {"hour": v.hour, "minutes": v.minute, "seconds": v.second}.get(p)
    return None


def _and(a, b):
    # three-valued logic (CQL2): false wins over null, null over true
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        return np.logical_and(a, b)
    if a is False or b is False:
        return False
    if a is None or b is None:
        return None
    return bool(a) and bool(b)


def _or(a, b):
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        return np.logical_or(a, b)
    if a is True or b is True:
        return True
    if a is None or b is None:
        return None
    return bool(a) or bool(b)


def _cmp(op, a, b):
    if a is None or b is None:
        return None
    a, b = _coerce_pair(a, b)
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        return {"=": np.equal, "<>": np.not_equal, "<": np.less, ">": np.greater,
                "<=": np.less_equal, ">=": np.greater_equal}[op](a, b)
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
        # incomparable types (e.g. text vs number): not equal, ordering unknown
        if op == "=":
            return False
        if op == "<>":
            return True
        return None
    raise ValueError(op)


def evaluate(e, ctx):
    """Evaluate an expression (or literal) to a value."""
    if e is None or isinstance(e, (bool, int, float, str)):
        return e
    if isinstance(e, list):
        return [evaluate(x, ctx) for x in e]
    if not isinstance(e, dict):
        return e
    if "property" in e and "op" not in e:
        return ctx.props.get(e["property"])
    if "sysId" in e:
        return ctx.sysid(e["sysId"])
    if "date" in e and "op" not in e:
        return _dt.date.fromisoformat(e["date"])
    if "timestamp" in e and "op" not in e:
        return _dt.datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
    if "op" in e:
        op = e["op"]
        args = e.get("args", [])
        if op == "and":
            r = True
            for a in args:
                r = _and(r, evaluate(a, ctx))
            return r
        if op == "or":
            r = False
            for a in args:
                r = _or(r, evaluate(a, ctx))
            return r
        if op == "not":
            v = evaluate(args[0], ctx)
            if v is None:
                return None
            return np.logical_not(v) if isinstance(v, np.ndarray) else (not v)
        if op in ("=", "<>", "<", ">", "<=", ">="):
            return _cmp(op, evaluate(args[0], ctx), evaluate(args[1], ctx))
        if op == "isNull":
            return evaluate(args[0], ctx) is None
        if op == "between":
            v, lo, hi = (evaluate(a, ctx) for a in args)
            return _and(_cmp(">=", v, lo), _cmp("<=", v, hi))
        if op == "in":
            v = evaluate(args[0], ctx)
            lst = evaluate(args[1], ctx)
            if v is None:
                return None
            return any(_cmp("=", v, x) is True for x in lst)
        if op in ("+", "-", "*", "/", "^", "%", "div"):
            a = evaluate(args[0], ctx)
            b = evaluate(args[1], ctx)
            if a is None or b is None:
                return None
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                # /req/arithmetic/div: real-valued quotient
                return np.divide(a, b) if isinstance(a, np.ndarray) or isinstance(b, np.ndarray) else (
                    (float(a) / float(b)) if b != 0 else None)
            if op == "^":
                return a ** b
            if op == "div":
                return int(a / b)
            if op == "%":
                return a - b * int(a / b)
        if op == "?:":
            c = evaluate(args[0], ctx)
            if isinstance(c, np.ndarray):
                return np.where(c, evaluate(args[1], ctx), evaluate(args[2], ctx))
            return evaluate(args[1], ctx) if c is True else evaluate(args[2], ctx)
        if op in ("lowerCase", "upperCase"):
            v = evaluate(args[0], ctx)
            return None if v is None else (v.lower() if op == "lowerCase" else v.upper())
        if op == "concatenate":
            vals = [evaluate(a, ctx) for a in args]
            return "".join("" if v is None else to_text(v) for v in vals)
        if op == "casei":
            v = evaluate(args[0], ctx)
            return None if v is None else str(v).lower()
        if op == "like":
            v = evaluate(args[0], ctx)
            pat = evaluate(args[1], ctx)
            if v is None or pat is None:
                return None
            rx = "^" + re.escape(pat).replace("%", ".*").replace("_", ".") + "$"
            return re.match(rx, v) is not None
        raise NotImplementedError("operator %r" % op)
    # an instance literal (object): evaluate members lazily by caller
    return e


def to_text(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)
