"""Style model for the CartoSym-JSON encoding: colours, units, expressions,
rule cascading and symbolizer resolution.

Written only from the text in ../spec.  Choices where the text is open are
marked with "CHOICE" and listed in ../notes.md.
"""
import copy
import datetime as dt
import math
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "..", "spec", "1-core")

# ---------------------------------------------------------------- colours

def _load_web_colors():
    """Named web colour table of clause 17 (CartoSym-CSS 'Colors')."""
    path = os.path.join(SPEC, "sections", "clause_17_cscss.adoc")
    table = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*\|?\s*([A-Za-z]+)\s*\|\s*`0x([0-9a-fA-F]{6})`", line)
            if m:
                h = m.group(2)
                table[m.group(1).lower()] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return table

WEB_COLORS = _load_web_colors()


def parse_color(v, default=(0, 0, 0)):
    """Return (r, g, b) floats 0..1 from a CartoSym-JSON Color (components 0..255).
    NULL resolves to black (/req/parameter-values/null)."""
    if v is None:
        return (0.0, 0.0, 0.0)
    if isinstance(v, str):
        s = v.strip().strip("'")
        if s.startswith("#") and len(s) == 7:
            return tuple(int(s[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        c = WEB_COLORS.get(s.lower())
        if c is None and s.lower() == "fuchsia":
            c = WEB_COLORS.get("fuschia")
        if c is None:
            return tuple(x / 255.0 for x in default) if max(default) > 1 else default
        return tuple(x / 255.0 for x in c)
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        return tuple(float(num(x)) / 255.0 for x in v[:3])
    if isinstance(v, dict):
        return tuple(float(num(v.get(k, 0))) / 255.0 for k in ("r", "g", "b"))
    return (0.0, 0.0, 0.0)


# ---------------------------------------------------------------- units

class View:
    def __init__(self, vj):
        self.minx, self.miny, self.maxx, self.maxy = vj["bbox"]
        self.width = int(vj["width"])
        self.height = int(vj["height"])
        self.sd = float(vj["scaleDenominator"])
        self.pixel_mm = float(vj.get("pixelSize_mm", 0.28))
        self.resx = (self.maxx - self.minx) / self.width
        self.resy = (self.maxy - self.miny) / self.height
        self.layers = vj["layers"]
        self.background = vj.get("background", "white")
        viz = vj.get("visualization", {})
        self.date = _date(viz.get("date"))
        ti = viz.get("timeInterval") or {}
        self.t_start = _date(ti.get("start"))
        self.t_end = _date(ti.get("end"))

    def to_pixel(self, x, y):
        return ((x - self.minx) / self.resx, (self.maxy - y) / self.resy)


UNIT_KEYS = ("px", "mm", "cm", "in", "pt", "em", "pc", "m", "ft")


def is_unit_value(v):
    return isinstance(v, dict) and len([k for k in v if k in UNIT_KEYS]) == 1 and \
        all(k in UNIT_KEYS or k == "alter" for k in v)


def to_px(v, view, default=0.0, font_px=None):
    """Convert a uom-qualified value to output pixels.
    A bare number is in pixels (clause 8: "pixel is the default unit")."""
    if v is None:
        return 0.0  # NULL -> 0 (/req/parameter-values/null)
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if is_unit_value(v):
        (k, x), = [(k, x) for k, x in v.items() if k in UNIT_KEYS]
        x = num(x)
        if x is None:
            return 0.0
        mmpp = view.pixel_mm
        if k == "px":
            return x
        if k == "mm":
            return x / mmpp
        if k == "cm":
            return x * 10.0 / mmpp
        if k == "in":
            return x * 25.4 / mmpp
        if k == "pt":
            return x * (25.4 / 72.0) / mmpp
        if k == "em":
            return x * (font_px if font_px else 10 * (25.4 / 72.0) / mmpp)
        if k == "m":
            # CHOICE: ground metres at the map scale (scale denominator x pixel size)
            return x * 1000.0 / (view.sd * mmpp)
        if k == "ft":
            return x * 0.3048 * 1000.0 / (view.sd * mmpp)
        if k == "pc":
            return None  # percent: context dependent, handled by caller
    return default


def num(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------- expressions

def _date(s):
    if s is None:
        return None
    if isinstance(s, dt.date):
        return s
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


class Ctx:
    def __init__(self, view, layer_id, layer_type, props=None, feature_id=None, geom_dim=None,
                 variables=None, layer_dim=None):
        self.view = view
        self.layer_id = layer_id
        self.layer_type = layer_type
        self.props = props or {}
        self.feature_id = feature_id
        self.geom_dim = geom_dim
        self.layer_dim = layer_dim
        self.variables = variables or {}

    def sysid(self, name):
        n = name
        for a, b in (("visualization.", "viz."), ("scaleDenominator", "sd"), ("dataLayer.identifier", "dataLayer.id"),
                     ("feature.identifier", "feature.id")):
            n = n.replace(a, b)
        if n == "visualization":
            n = "viz"
        v = self.view
        if n == "viz.sd":
            return v.sd
        if n in ("viz.date", "viz.dateTime.date", "viz.dateTime"):
            return v.date
        if n.startswith("viz.date."):
            part = n.split(".")[-1]
            return getattr(v.date, part if part != "month" else "month", None) if v.date else None
        if n == "viz.timeInterval.start" or n == "viz.timeInterval.start.date":
            return v.t_start
        if n == "viz.timeInterval.end" or n == "viz.timeInterval.end.date":
            return v.t_end
        if n.startswith("viz.timeInterval.start.date."):
            return getattr(v.t_start, n.split(".")[-1], None) if v.t_start else None
        if n.startswith("viz.timeInterval.end.date."):
            return getattr(v.t_end, n.split(".")[-1], None) if v.t_end else None
        if n == "viz.pass":
            return 0
        if n == "dataLayer.id":
            return self.layer_id
        if n == "dataLayer.type":
            return self.layer_type
        if n in ("dataLayer.featuresGeometryDimensions", "dataLayer.featuresGeometryDimension"):
            return self.layer_dim
        if n == "feature.id":
            return self.feature_id
        if n in ("feature.geometryDimensions", "feature.geometryDimension"):
            return self.geom_dim
        if n == "feature.pass":
            return 0
        if n.startswith("capabilities"):
            return n.split(".")[-1] in CAPABILITIES
        return None


CAPABILITIES = {"vector", "coverage", "labels", "hillshading", "fontoutlines", "hatches", "stipples", "dashes",
                "casing", "parametervalues", "functions", "math", "arithmetic", "conditional", "textrelation",
                "righthand", "textmanipulation", "arrayrelations", "variables", "capabilities"}

EXPR_KEYS = ("op", "property", "sysId", "$ref", "date", "timestamp", "interval")


def is_expression(v):
    return isinstance(v, dict) and any(k in v for k in EXPR_KEYS)


def _cmp_coerce(a, b):
    # CHOICE: a text value compared with a Date is read as an ISO date
    if isinstance(a, dt.date) and isinstance(b, str):
        b = _date(b)
    elif isinstance(b, dt.date) and isinstance(a, str):
        a = _date(a)
    return a, b


def _is_array(x):
    return isinstance(x, np.ndarray)


def evaluate(e, ctx):
    """Evaluate a CQL2-JSON based expression. Returns Python value; None is NULL."""
    if e is None or isinstance(e, (bool, int, float, str)):
        return e
    if isinstance(e, np.ndarray):
        return e
    if isinstance(e, list):
        return [evaluate(x, ctx) for x in e]
    if not isinstance(e, dict):
        return e
    if "property" in e and "op" not in e:
        return ctx.props.get(e["property"])
    if "sysId" in e:
        return ctx.sysid(e["sysId"])
    if "$ref" in e:
        name = e["$ref"].split("/")[-1]
        return evaluate(ctx.variables.get(name), ctx)
    if "date" in e and len(e) == 1:
        return _date(evaluate(e["date"], ctx))
    if "timestamp" in e and len(e) == 1:
        return _date(evaluate(e["timestamp"], ctx))
    if "op" not in e:
        return {k: evaluate(v, ctx) for k, v in e.items()}
    op = e["op"]
    args = e.get("args", [])
    if op == "and":
        vals = [evaluate(a, ctx) for a in args]
        if any(v is False for v in vals):
            return False
        if any(v is None for v in vals):
            return None
        return all(bool(v) for v in vals)
    if op == "or":
        vals = [evaluate(a, ctx) for a in args]
        if any(v is True for v in vals):
            return True
        if any(v is None for v in vals):
            return None
        return False
    if op == "not":
        v = evaluate(args[0], ctx)
        return None if v is None else (not v)
    if op == "?:":
        c = evaluate(args[0], ctx)
        return evaluate(args[1] if c is True else args[2], ctx)
    vals = [evaluate(a, ctx) for a in args]
    if op in ("=", "<>", "<", ">", "<=", ">="):
        a, b = vals
        if a is None or b is None:
            return None
        a, b = _cmp_coerce(a, b)
        if a is None or b is None:
            return None
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
    if op == "between":
        a, lo, hi = vals
        if None in (a, lo, hi):
            return None
        return lo <= a <= hi
    if op == "in":
        a, arr = vals
        if a is None:
            return None
        return a in arr
    if op == "isNull":
        return vals[0] is None
    if op in ("like", "notLike"):
        a, p = vals
        if a is None or p is None:
            return None
        rx = "^" + "".join(".*" if c == "%" else "." if c == "_" else re.escape(c) for c in p) + "$"
        r = re.match(rx, a, re.S) is not None
        return r if op == "like" else not r
    if op in ("+", "-", "*", "/", "^", "%", "div", "mod", "intDiv"):
        if any(v is None for v in vals):
            return None
        if len(vals) == 1 and op == "-":
            return -vals[0]
        a, b = vals
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if _is_array(b) or _is_array(a):
                with np.errstate(divide="ignore", invalid="ignore"):
                    return np.asarray(a, dtype=float) / b
            return None if b == 0 else a / b
        if op == "^":
            return a ** b
        if op in ("%", "mod"):
            return math.fmod(a, b) if b != 0 else None
        if op in ("div", "intDiv"):
            return int(a / b) if b != 0 else None
    # functions
    f = op
    try:
        if f in ("casei", "caseInsensitize"):
            return None if vals[0] is None else str(vals[0]).casefold()
        if f in ("lowerCase", "lower"):
            return None if vals[0] is None else str(vals[0]).lower()
        if f in ("upperCase", "upper"):
            return None if vals[0] is None else str(vals[0]).upper()
        if f in ("concatenate", "concat"):
            return None if None in vals else "".join(str(v) for v in vals)
        if f == "substitute":
            return None if None in vals else str(vals[0]).replace(vals[1], vals[2])
        if f == "contains":
            return None if None in vals else vals[1] in vals[0]
        if f == "startsWith":
            return None if None in vals else vals[0].startswith(vals[1])
        if f == "endsWith":
            return None if None in vals else vals[0].endswith(vals[1])
        if f in ("abs", "ceil", "floor", "sqrt", "sin", "cos", "tan", "exp", "log", "log10", "acos", "asin", "atan",
                 "sinh", "cosh", "tanh"):
            return None if vals[0] is None else getattr(np if _is_array(vals[0]) else math, f)(vals[0])
        if f == "round":
            x = vals[0]
            return None if x is None else int(math.floor(abs(x) + 0.5)) * (1 if x >= 0 else -1)
        if f == "min":
            return None if None in vals else min(vals)
        if f == "max":
            return None if None in vals else max(vals)
        if f == "pow":
            return None if None in vals else vals[0] ** vals[1]
        if f == "atan2":
            return None if None in vals else math.atan2(vals[0], vals[1])
        if f == "format":
            return None if None in vals else (vals[0] % tuple(vals[1:]))
    except Exception:
        return None
    return None


def resolve_value(v, ctx):
    """Evaluate every Parameter Value expression inside a symbolizer value."""
    if is_expression(v):
        return evaluate(v, ctx)
    if isinstance(v, dict):
        return {k: resolve_value(x, ctx) for k, x in v.items() if k != "$comment"}
    if isinstance(v, list):
        return [resolve_value(x, ctx) for x in v]
    return v


# ---------------------------------------------------------------- defaults (clause 7 "Default class member values")

def default_of(key):
    if key == "stroke":
        return {"color": "black", "width": {"px": 1}, "opacity": 1}
    if key == "fill":
        return {"color": "white", "opacity": 1}
    if key == "marker":
        return {"elements": [{"type": "Dot", "size": {"px": 10}, "color": "white"}]}
    if key == "visibility":
        return True
    if key == "opacity":
        return 1
    if key == "zOrder":
        return 1
    if key == "alphaChannel":
        return 1
    return None


# ---------------------------------------------------------------- cascading

def _merge_value(old, new, key=None):
    """Apply one symbolizer member assignment (JSON partial updates, /req/json/partial-update,
    /req/json/array-element-update)."""
    if isinstance(new, dict) and new.get("alter") is True and not is_expression(new):
        base = copy.deepcopy(old) if isinstance(old, dict) else (copy.deepcopy(default_of(key)) or {})
        if not isinstance(base, dict):
            base = {}
        for k, v in new.items():
            if k == "alter":
                continue
            base[k] = _merge_value(base.get(k), v, k)
        return base
    if isinstance(new, dict) and "index" in new and "value" in new and len(new) == 2:
        arr = list(copy.deepcopy(old)) if isinstance(old, list) else []
        i = int(new["index"])
        while len(arr) <= i:
            arr.append(None)
        arr[i] = _merge_value(arr[i], new["value"])
        return arr
    return copy.deepcopy(new)


def merge_symbolizer(acc, sym):
    for k, v in sym.items():
        if k == "$comment":
            continue
        acc[k] = _merge_value(acc.get(k), v, k)


def cascade(rules, ctx, acc=None, selected=None):
    """Consider rules in order; nested rules only when the parent is selected."""
    if acc is None:
        acc = {}
    if selected is None:
        selected = [False]
    for r in rules:
        sel = r.get("selector")
        if sel is not None:
            if evaluate(sel, ctx) is not True:
                continue
        selected[0] = True
        if r.get("symbolizer"):
            merge_symbolizer(acc, r["symbolizer"])
        if r.get("nestedRules"):
            cascade(r["nestedRules"], ctx, acc, selected)
    return acc, selected[0]


def load_style(path):
    import json
    with open(path, encoding="utf-8") as f:
        st = json.load(f)
    rules = []
    inc = st.get("$include")
    if inc:
        for p in ([inc] if isinstance(inc, str) else inc):
            sub = load_style(os.path.join(os.path.dirname(path), p))
            rules.extend(sub["stylingRules"])
            st.setdefault("$variables", {}).update(sub.get("$variables", {}))
    rules.extend(st.get("stylingRules", []))
    st["stylingRules"] = rules
    return st


# ---------------------------------------------------------------- typed accessors with NULL table

def get_num(d, k, default):
    if not isinstance(d, dict) or k not in d:
        return default
    v = d[k]
    if v is None:
        return 0.0
    n = num(v)
    return default if n is None else n


def get_bool(d, k, default):
    if not isinstance(d, dict) or k not in d:
        return default
    v = d[k]
    if v is None:
        return False
    return bool(v)


def to_text(v):
    """CHOICE: numbers are written without a fractional part when integral."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)
