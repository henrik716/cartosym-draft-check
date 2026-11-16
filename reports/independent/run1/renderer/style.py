"""Style cascade (rules, nested rules, alter / index updates) and typed resolution
of Parameter Values, written from spec/1-core clauses 7, 8, 13 and 16."""
import copy

import numpy as np

from colors import NAMED
from expr import evaluate, is_expression

# Default class member values (clause 7, "Default class member values")
DEFAULT_STROKE = {"color": "black", "width": {"px": 1}, "opacity": 1}
DEFAULT_FILL = {"color": "white", "opacity": 1}
DEFAULT_DOT = {"type": "Dot", "size": {"px": 10}, "color": "white"}
DEFAULT_MARKER = {"elements": [DEFAULT_DOT]}
DEFAULT_OBJECTS = {"stroke": DEFAULT_STROKE, "fill": DEFAULT_FILL, "marker": DEFAULT_MARKER}


class Unsupported(Exception):
    pass


# ---------------------------------------------------------------- cascade

def _color_to_obj(c):
    rgb = resolve_color(c, None)
    if rgb is None:
        rgb = (0, 0, 0)
    return {"r": round(rgb[0] * 255), "g": round(rgb[1] * 255), "b": round(rgb[2] * 255)}


def _merge(acc, new, path):
    """Merge symbolizer object `new` into dict `acc` (in place)."""
    is_dot = acc.get("type") == "Dot" or new.get("type") == "Dot"
    for k, v in new.items():
        if k in ("alter", "$comment"):
            continue
        sub = path + (k,)
        if isinstance(v, dict) and v.get("alter") is True:
            base = acc.get(k)
            if base is None or not isinstance(base, dict) or is_expression(base):
                if k.endswith("olor") and base is not None and not is_expression(base):
                    base = _color_to_obj(base)
                elif len(sub) == 1 and k in DEFAULT_OBJECTS:
                    base = copy.deepcopy(DEFAULT_OBJECTS[k])
                elif k == "stroke" and is_dot:
                    base = {}
                else:
                    base = {}
            else:
                base = copy.deepcopy(base)
            _merge(base, v, sub)
            acc[k] = base
        elif isinstance(v, dict) and "index" in v and "value" in v and set(v) <= {"index", "value", "$comment"}:
            base = acc.get(k)
            if base is None and len(path) == 1 and path[0] == "marker" and k == "elements":
                base = copy.deepcopy(DEFAULT_MARKER["elements"])
            base = list(copy.deepcopy(base) if isinstance(base, list) else [])
            idx = v["index"]
            while len(base) <= idx:
                base.append(None)
            val = v["value"]
            if isinstance(val, dict) and val.get("alter") is True and isinstance(base[idx], dict):
                el = copy.deepcopy(base[idx])
                _merge(el, val, sub)
                base[idx] = el
            else:
                base[idx] = copy.deepcopy(val)
            acc[k] = base
        else:
            acc[k] = copy.deepcopy(v)
        # Dot: size <-> stroke.width, color <-> stroke.color; the value set last applies
        if is_dot:
            if k == "size" and isinstance(acc.get("stroke"), dict):
                acc["stroke"].pop("width", None)
            if k == "color" and isinstance(acc.get("stroke"), dict):
                acc["stroke"].pop("color", None)
            if k == "stroke" and isinstance(v, dict):
                if "width" in v:
                    acc.pop("size", None)
                if "color" in v:
                    acc.pop("color", None)


def resolve_symbolizer(rules, ctx, coverage=False):
    acc = {}

    def visit(rs):
        for r in rs:
            sel = r.get("selector")
            if sel is not None:
                v = evaluate(sel, ctx)
                if isinstance(v, np.ndarray):
                    if v.all():
                        v = True
                    elif not v.any():
                        v = False
                    else:
                        raise Unsupported("per-cell selector on a coverage")
                if v is not True:
                    continue
            if r.get("symbolizer"):
                _merge(acc, r["symbolizer"], ())
            visit(r.get("nestedRules", []) or [])

    visit(rules)
    return acc


# ---------------------------------------------------------------- typed resolvers

def _ev(raw, ctx):
    if ctx is None:
        return raw
    return evaluate(raw, ctx)


def resolve_number(raw, ctx, default=None):
    if raw is None:
        return default
    v = _ev(raw, ctx)
    if v is None:
        return 0.0  # /req/parameter-values/null
    if isinstance(v, np.ndarray):
        return v
    if isinstance(v, bool):
        return float(v)
    return float(v)


def resolve_bool(raw, ctx, default):
    if raw is None:
        return default
    v = _ev(raw, ctx)
    if v is None:
        return False
    return bool(v)


def resolve_text(raw, ctx):
    if raw is None:
        return ""
    v = _ev(raw, ctx)
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _hex(s):
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    n = int(s, 16)
    return ((n >> 16) & 255) / 255.0, ((n >> 8) & 255) / 255.0, (n & 255) / 255.0


_NAMED_LC = {k.lower(): v for k, v in NAMED.items()}


def resolve_color(raw, ctx, scale=255.0):
    """Returns (r, g, b) in 0..1. `scale` is the range of numeric components
    (255 for CartoSym-JSON `color`, 1 for `colorChannels`)."""
    if raw is None:
        return None
    v = _ev(raw, ctx)
    if v is None:
        return (0.0, 0.0, 0.0)  # null -> black
    if isinstance(v, str):
        if v.startswith("#"):
            return _hex(v)
        n = NAMED.get(v)
        if n is None:
            n = _NAMED_LC.get(v.lower())
        if n is None:
            raise ValueError("unknown color %r" % v)
        return ((n >> 16) & 255) / 255.0, ((n >> 8) & 255) / 255.0, (n & 255) / 255.0
    if isinstance(v, list):
        comps = [resolve_number(c, ctx, 0.0) for c in v[:3]]
        return tuple(c / scale for c in comps)
    if isinstance(v, dict):
        comps = [resolve_number(v.get(c), ctx, 0.0) for c in ("r", "g", "b")]
        return tuple(c / scale for c in comps)
    raise ValueError("bad color %r" % (v,))


UNIT_KEYS = ("px", "mm", "cm", "in", "pt", "em", "pc", "m", "ft")


class Units:
    """Conversion of uom-qualified values to pixels (clause 8 Graphical Units,
    clause 17 units table)."""

    def __init__(self, pixel_mm, ground_m_per_px):
        self.pixel_mm = pixel_mm
        self.gres = ground_m_per_px

    def to_px(self, value, unit, em_px=None, pc_base=None):
        if unit == "px":
            return value
        if unit == "mm":
            return value / self.pixel_mm
        if unit == "cm":
            return value * 10.0 / self.pixel_mm
        if unit == "in":
            return value * 25.4 / self.pixel_mm
        if unit == "pt":
            return value * (25.4 / 72.0) / self.pixel_mm
        if unit == "m":
            return value / self.gres
        if unit == "ft":
            return value * 0.3048 / self.gres
        if unit == "em":
            base = em_px if em_px is not None else self.to_px(12, "pt")
            return value * base
        if unit == "pc":
            if pc_base is None:
                raise Unsupported("percent unit without a reference")
            return value / 100.0 * pc_base
        raise ValueError(unit)


def split_unit(raw, ctx):
    """Returns (number, unit) for a unitValue; a bare number has unit None."""
    if raw is None:
        return None, None
    if isinstance(raw, dict) and not is_expression(raw):
        for u in UNIT_KEYS:
            if u in raw:
                return resolve_number(raw[u], ctx, 0.0), u
    return resolve_number(raw, ctx, 0.0), None


def resolve_length(raw, ctx, units, default_unit="px", pc_base=None, em_px=None):
    v, u = split_unit(raw, ctx)
    if v is None:
        return None
    return units.to_px(v, u or default_unit, em_px=em_px, pc_base=pc_base)


def resolve_point(raw, ctx):
    """UnitPoint -> ((x, ux), (y, uy))."""
    if raw is None:
        return None
    v = raw
    if is_expression(v):
        v = evaluate(v, ctx)
    if isinstance(v, list):
        return split_unit(v[0], ctx), split_unit(v[1], ctx)
    if isinstance(v, dict):
        return split_unit(v.get("x", 0), ctx), split_unit(v.get("y", 0), ctx)
    raise ValueError("bad point %r" % (raw,))


def resolve_alignment(raw, ctx):
    h, v = "center", "middle"  # no default defined in spec: assumed
    if raw is None:
        return h, v
    a = raw
    if is_expression(a):
        a = evaluate(a, ctx)
    if isinstance(a, list):
        h, v = resolve_text(a[0], ctx) or h, resolve_text(a[1], ctx) or v
    elif isinstance(a, dict):
        hh = a.get("hAlignment", a.get("horzAlignment", a.get("horizontal")))
        vv = a.get("vAlignment", a.get("vertAlignment", a.get("vertical")))
        if hh is not None:
            h = resolve_text(hh, ctx)
        if vv is not None:
            v = resolve_text(vv, ctx)
    return h, v


def resolve_value_map(raw, ctx, kind):
    """colorMap / opacityMap -> (values array, outputs array) sorted by value."""
    if raw is None:
        return None
    m = raw
    if is_expression(m):
        m = evaluate(m, ctx)
    vals, outs = [], []
    for entry in m:
        if isinstance(entry, dict):
            val = entry.get("value")
            out = entry.get("color") if kind == "color" else entry.get("opacity")
        else:
            val, out = entry[0], entry[1]
        vals.append(resolve_number(val, ctx, 0.0))
        if kind == "color":
            outs.append(resolve_color(out, ctx))
        else:
            outs.append(resolve_number(out, ctx, 1.0))
    order = np.argsort(np.asarray(vals, dtype=float), kind="stable")
    vals = np.asarray(vals, dtype=float)[order]
    outs = np.asarray(outs, dtype=float)[order]
    return vals, outs


def apply_map(m, x):
    """Linear interpolation; values outside the range take the first/last entry."""
    vals, outs = m
    if outs.ndim == 1:
        return np.interp(x, vals, outs)
    return np.stack([np.interp(x, vals, outs[:, i]) for i in range(outs.shape[1])], axis=-1)


def resolve_angle(raw, ctx, default):
    if raw is None:
        return default
    if isinstance(raw, dict) and not is_expression(raw):
        if "deg" in raw:
            return resolve_number(raw["deg"], ctx, default)
        if "rad" in raw:
            return np.degrees(resolve_number(raw["rad"], ctx, 0.0))
    return resolve_number(raw, ctx, default)
