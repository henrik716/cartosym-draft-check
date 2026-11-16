"""Renderer for OGC Cartographic Symbology 2.0 Part 1 (draft), written from the
requirement text in ../spec only.  Choices where the text is open are marked
with  # CHOICE n  and listed in ../notes.md.

Run:  uv run --no-project --with numpy --with pillow --with pycairo --with shapely \
          python renderer/render.py [case ...]
"""
import copy
import datetime as dt
import json
import math
import os
import re
import sys

import cairo
import numpy as np
from PIL import Image
from shapely.geometry import shape as shp_shape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "cases")
OUT = os.path.join(ROOT, "out")
SPEC = os.path.join(ROOT, "spec", "1-core")

# ---------------------------------------------------------------- colours
def load_web_colors():
    """Named web colour table of clause 17 (read from the spec text itself)."""
    table = {}
    path = os.path.join(SPEC, "sections", "clause_17_cscss.adoc")
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^\s*\|?\s*([A-Za-z]+)\s*\|\s*`0x([0-9a-fA-F]{6})`", line)
            if m:
                h = m.group(2)
                table[m.group(1).lower()] = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return table


WEB_COLORS = load_web_colors()

# ---------------------------------------------------------------- expressions
EXPR_KEYS = {"op", "property", "sysId", "date", "timestamp", "interval", "function", "$ref"}


def is_expr(v):
    return isinstance(v, dict) and any(k in v for k in EXPR_KEYS)


ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _coerce_pair(a, b):
    # A date compared with an ISO date string: compare as dates.
    if isinstance(a, dt.date) and isinstance(b, str) and ISO_DATE.match(b):
        b = dt.date.fromisoformat(b)
    if isinstance(b, dt.date) and isinstance(a, str) and ISO_DATE.match(a):
        a = dt.date.fromisoformat(a)
    return a, b


class Ctx:
    def __init__(self, view, layer_id, layer_type, props=None, geom_dim=None):
        self.view = view
        self.layer_id = layer_id
        self.layer_type = layer_type
        self.props = props or {}
        self.geom_dim = geom_dim

    def prop(self, name):
        return self.props.get(name)  # missing property -> null

    def sys(self, name):
        v = self.view
        name = re.sub(r"^visualization\.", "viz.", name)
        name = name.replace("viz.scaleDenominator", "viz.sd")
        name = name.replace("dataLayer.identifier", "dataLayer.id")
        name = name.replace("feature.identifier", "feature.id")
        if name == "dataLayer.id":
            return self.layer_id
        if name == "dataLayer.type":
            return self.layer_type
        if name == "viz.sd":
            return float(v["scaleDenominator"])
        if name.startswith("capabilities."):
            return name.split(".", 1)[1] in CAPABILITIES
        if name in ("feature.geometryDimensions", "feature.geometryDimension"):
            return self.geom_dim
        vz = v.get("visualization", {})
        if name.startswith("viz.timeInterval"):
            ti = vz.get("timeInterval", {})
            parts = name.split(".")[2:]
            if not parts:
                return (_instant(ti.get("start")), _instant(ti.get("end")))
            inst = _instant(ti.get(parts[0]))
            return _member(inst, parts[1:])
        if name.startswith("viz.date") and not name.startswith("viz.dateTime"):
            d = _instant(vz.get("date"))
            return _member(d, ["date"] + name.split(".")[2:])
        if name.startswith("viz.dateTime"):
            d = _instant(vz.get("dateTime") or vz.get("date"))
            return _member(d, name.split(".")[2:])
        if name.startswith("viz.timeOfDay"):
            d = _instant(vz.get("dateTime") or vz.get("date"))
            return _member(d, ["time"] + name.split(".")[2:])
        raise KeyError("unknown system identifier " + name)


CAPABILITIES = {"vector", "coverage", "labels", "hillshading", "fontoutlines", "hatches",
                "stipples", "dashes", "casing", "parametervalues", "arithmetic"}


def _instant(s):
    if s is None:
        return None
    if isinstance(s, str):
        if "T" in s:
            return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.datetime.fromisoformat(s + "T00:00:00")
    return s


def _member(inst, parts):
    if inst is None:
        return None
    cur = inst
    for p in parts:
        if p == "date":
            cur = cur.date() if isinstance(cur, dt.datetime) else cur
        elif p == "time":
            cur = cur.time() if isinstance(cur, dt.datetime) else None
        elif p == "year":
            cur = cur.year
        elif p == "month":
            cur = cur.month
        elif p == "day":
            cur = cur.day
        elif p == "hour":
            cur = cur.hour
        elif p == "minutes":
            cur = cur.minute
        elif p == "seconds":
            cur = cur.second
    return cur


def ev(e, ctx):
    """Evaluate an expression (CQL2-JSON based)."""
    if e is None or isinstance(e, (bool, int, float, str)):
        return e
    if isinstance(e, list):
        return [ev(x, ctx) for x in e]
    if not isinstance(e, dict):
        return e
    if "property" in e:
        return ctx.prop(e["property"])
    if "sysId" in e:
        return ctx.sys(e["sysId"])
    if "date" in e and len(e) == 1:
        return dt.date.fromisoformat(e["date"])
    if "timestamp" in e and len(e) == 1:
        return _instant(e["timestamp"])
    if "op" in e:
        return ev_op(e["op"], e.get("args", []), ctx)
    return e  # an object instance: members are evaluated where they are read


def ev_op(op, args, ctx):
    op = op.lower() if isinstance(op, str) else op
    if op == "and":
        vals = [ev(a, ctx) for a in args]
        if any(v is False for v in vals):
            return False
        if any(v is None for v in vals):
            return None
        return True
    if op == "or":
        vals = [ev(a, ctx) for a in args]
        if any(v is True for v in vals):
            return True
        if any(v is None for v in vals):
            return None
        return False
    if op == "not":
        v = ev(args[0], ctx)
        return None if v is None else (not v)
    if op in ("isnull",):
        return ev(args[0], ctx) is None
    if op in ("=", "<>", "<", ">", "<=", ">="):
        a, b = ev(args[0], ctx), ev(args[1], ctx)
        if a is None or b is None:
            return None
        a, b = _coerce_pair(a, b)
        if isinstance(a, str) and isinstance(b, str):
            pass
        try:
            return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b,
                    "<=": a <= b, ">=": a >= b}[op]
        except TypeError:
            return None
    if op == "between":
        a, lo, hi = (ev(x, ctx) for x in args)
        if None in (a, lo, hi):
            return None
        return lo <= a <= hi
    if op == "in":
        a = ev(args[0], ctx)
        lst = ev(args[1], ctx)
        if a is None:
            return None
        return a in lst
    if op in ("+", "-", "*", "/", "%", "div", "^", "add", "sub", "mul", "mod", "pow", "intdiv"):
        a, b = ev(args[0], ctx), ev(args[1], ctx)
        if a is None or b is None:
            return None
        if op in ("+", "add"):
            return a + b
        if op in ("-", "sub"):
            return a - b
        if op in ("*", "mul"):
            return a * b
        if op == "/":
            return float(a) / float(b) if b != 0 else None
        if op in ("div", "intdiv"):
            return int(a / b) if b != 0 else None
        if op in ("%", "mod"):
            return math.fmod(a, b) if b != 0 else None
        if op in ("^", "pow"):
            return a ** b
    if op == "?:" or op == "if":
        c = ev(args[0], ctx)
        return ev(args[1], ctx) if c is True else ev(args[2], ctx)
    raise ValueError("unsupported operator " + str(op))


# ---------------------------------------------------------------- symbolizer resolution
DEFAULT_DOT = {"type": "Dot", "size": {"px": 10}, "color": "white"}
DEFAULT_SYMBOLIZER = {
    "visibility": True,
    "opacity": 1.0,
    "zOrder": 1,
    "fill": {"color": "white", "opacity": 1.0},
    "stroke": {"color": "black", "width": {"px": 1.0}, "opacity": 1.0},
    "marker": {"elements": [DEFAULT_DOT]},
    "alphaChannel": 1.0,
}


def normalize_dot(obj):
    """Dot size/color are the width/color of its stroke (/req/vector/dot)."""
    if isinstance(obj, dict) and obj.get("type") == "Dot":
        obj = dict(obj)
        st = obj.get("stroke")
        if isinstance(st, dict) and not is_expr(st):
            st = dict(st)
            if "width" in st:
                obj["size"] = st.pop("width")
            if "color" in st:
                obj["color"] = st.pop("color")
            obj["stroke"] = st
    return obj


def merge(base, new):
    """Apply a value from a later rule over the value accumulated so far."""
    if isinstance(new, dict) and not is_expr(new):
        new = normalize_dot(new)
        if "index" in new and "value" in new and len([k for k in new if k != "$comment"]) == 2:
            lst = list(base) if isinstance(base, list) else []
            i = int(new["index"])
            while len(lst) <= i:
                lst.append(None)
            lst[i] = merge(lst[i], new["value"])
            return lst
        if new.get("alter"):
            out = copy.deepcopy(base) if isinstance(base, dict) else {}
            for k, v in new.items():
                if k in ("alter", "$comment"):
                    continue
                out[k] = merge(out.get(k), v)
            return out
        return {k: (merge(None, v) if isinstance(v, dict) else copy.deepcopy(v))
                for k, v in new.items() if k != "$comment"}
    if isinstance(new, list):
        return [merge(None, x) if isinstance(x, dict) else copy.deepcopy(x) for x in new]
    return copy.deepcopy(new)


def resolve_symbolizer(rules, ctx, acc=None):
    """Walk the rules in order; a selected rule's symbolizer overrides earlier ones;
    nested rules only when the parent is selected.  Returns (symbolizer, selected_any)."""
    if acc is None:
        acc = copy.deepcopy(DEFAULT_SYMBOLIZER)
    selected_any = False
    for r in rules:
        sel = r.get("selector")
        if sel is not None and ev(sel, ctx) is not True:
            continue
        selected_any = True
        for k, v in (r.get("symbolizer") or {}).items():
            if k == "$comment":
                continue
            acc[k] = merge(acc.get(k), v)
        if r.get("nestedRules"):
            acc, _ = resolve_symbolizer(r["nestedRules"], ctx, acc)
    return acc, selected_any


# ---------------------------------------------------------------- value readers
class Units:
    def __init__(self, view):
        bb = view["bbox"]
        self.m_per_px = (bb[2] - bb[0]) / view["width"]
        self.mm_per_px = view.get("pixelSize_mm", 0.28)
        self.font_pt_px = (25.4 / 72.0) / self.mm_per_px

    def px(self, v, ctx, em=None):
        """uom-qualified distance -> pixels.  A bare number is in pixels."""
        if v is None:
            return None
        if isinstance(v, dict) and not is_expr(v) and len(v) == 1:
            (u, x), = v.items()
            x = ev(x, ctx)
            if x is None:
                return 0.0  # /req/parameter-values/null: numbers -> 0
            x = float(x)
            if u == "px":
                return x
            if u == "mm":
                return x / self.mm_per_px
            if u == "cm":
                return 10 * x / self.mm_per_px
            if u == "in":
                return 25.4 * x / self.mm_per_px
            if u == "pt":
                return x * self.font_pt_px
            if u == "m":
                return x / self.m_per_px
            if u == "ft":
                return 0.3048 * x / self.m_per_px
            if u == "em":
                return x * (em if em is not None else 10 * self.font_pt_px)
            raise ValueError("unit %s not usable here" % u)
        x = ev(v, ctx)
        return 0.0 if x is None else float(x)


def num(v, ctx, default=None):
    if v is None:
        return default
    x = ev(v, ctx)
    if isinstance(x, dict) and len(x) == 1:  # e.g. {"deg": 45}
        k, x = next(iter(x.items()))
        x = ev(x, ctx)
        if k == "rad":
            x = math.degrees(x)
    return 0.0 if x is None else float(x)


def color(v, ctx, default=(0, 0, 0)):
    """Colour -> (r, g, b) in 0..1.  JSON objects/arrays are 0..255 (schema)."""
    if v is None:
        return default
    x = ev(v, ctx)
    if x is None:
        return (0.0, 0.0, 0.0)  # null colour -> black
    if isinstance(x, str):
        s = x.strip()
        if s.startswith("#"):
            h = s[1:]
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        return WEB_COLORS[s.lower()]
    if isinstance(x, list):
        return tuple(float(ev(c, ctx)) / 255.0 for c in x[:3])
    if isinstance(x, dict):
        return tuple(float(ev(x.get(k, 0), ctx)) / 255.0 for k in "rgb")
    raise ValueError("bad colour %r" % (x,))


def text_value(v, ctx):
    x = ev(v, ctx)
    if x is None:
        return ""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, float) and x.is_integer():
        return str(int(x))  # CHOICE: integral reals printed without decimals
    return str(x)


def unit_point(v, ctx, units):
    """Graphic position -> (dx, dy) in pixels, +y upward on the map."""
    if v is None:
        return (0.0, 0.0)
    x = ev(v, ctx)
    if isinstance(x, list):
        a, b = x[0], x[1]
    elif isinstance(x, dict):
        a, b = x.get("x", 0), x.get("y", 0)
    else:
        return (0.0, 0.0)
    return (units.px(a, ctx), units.px(b, ctx))


# ---------------------------------------------------------------- drawing helpers
def set_rgba(cr, rgb, a):
    cr.set_source_rgba(rgb[0], rgb[1], rgb[2], a)


class View:
    def __init__(self, view):
        self.v = view
        self.bb = view["bbox"]
        self.W = view["width"]
        self.H = view["height"]
        self.sx = self.W / (self.bb[2] - self.bb[0])
        self.sy = self.H / (self.bb[3] - self.bb[1])

    def px(self, x, y):
        return ((x - self.bb[0]) * self.sx, (self.bb[3] - y) * self.sy)


def path_line(cr, vw, coords):
    for i, (x, y) in enumerate(coords):
        p = vw.px(x, y)
        if i == 0:
            cr.move_to(*p)
        else:
            cr.line_to(*p)


def path_polygon(cr, vw, rings):
    for ring in rings:
        path_line(cr, vw, ring)
        cr.close_path()


def geom_lines(g):
    """Paths to stroke: list of (coords, closed)."""
    t = g["type"]
    c = g["coordinates"]
    if t == "LineString":
        return [(c, False)]
    if t == "MultiLineString":
        return [(l, False) for l in c]
    if t == "Polygon":
        return [(r, True) for r in c]
    if t == "MultiPolygon":
        return [(r, True) for p in c for r in p]
    return []


def geom_polys(g):
    t = g["type"]
    if t == "Polygon":
        return [g["coordinates"]]
    if t == "MultiPolygon":
        return g["coordinates"]
    return []


def geom_dim(g):
    t = g["type"]
    return 0 if "Point" in t else (1 if "Line" in t else 2)


def marker_points(g):
    """Where a marker is drawn: points; each vertex of lines; polygon centroid."""
    t = g["type"]
    c = g["coordinates"]
    if t == "Point":
        return [c]
    if t == "MultiPoint":
        return list(c)
    if t == "LineString":
        return list(c)
    if t == "MultiLineString":
        return [p for l in c for p in l]
    if t in ("Polygon", "MultiPolygon"):
        ce = shp_shape(g).centroid
        return [(ce.x, ce.y)]
    return []


# ---------------------------------------------------------------- the renderer
class Renderer:
    def __init__(self, case):
        self.case = case
        self.dir = os.path.join(CASES, case)
        with open(os.path.join(self.dir, "style.cs.json"), encoding="utf-8") as f:
            self.style = json.load(f)
        self.rules = self.style.get("stylingRules", [])
        self.image_cache = {}

    # ---------------- data
    def load_layer(self, lid):
        gj = os.path.join(self.dir, lid + ".geojson")
        if os.path.exists(gj):
            with open(gj, encoding="utf-8") as f:
                return ("vector", json.load(f)["features"])
        bands = {}
        for fn in sorted(os.listdir(self.dir)):
            if fn.startswith(lid + ".") and fn.endswith(".asc"):
                band = fn[len(lid) + 1:-4]
                bands[band] = read_asc(os.path.join(self.dir, fn))
        if bands:
            return ("coverage", bands)
        raise FileNotFoundError(lid)

    # ---------------- main
    def render(self, view_path, out_path):
        with open(view_path, encoding="utf-8") as f:
            view = json.load(f)
        vw = View(view)
        self.units = Units(view)
        W, H = vw.W, vw.H
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        cr = cairo.Context(surf)
        set_rgba(cr, color(view.get("background", "white"), None), 1.0)
        cr.paint()
        rng = np.random.default_rng(20261114)
        self.stipple_field = rng.random((H, W))  # CHOICE 5: fixed per-pixel random field

        items = []
        for li, lid in enumerate(view["layers"]):
            kind, data = self.load_layer(lid)
            if kind == "vector":
                for fi, feat in enumerate(data):
                    g = feat.get("geometry")
                    if not g:
                        continue
                    ctx = Ctx(view, lid, "vector", feat.get("properties") or {}, geom_dim(g))
                    sym, _ = resolve_symbolizer(self.rules, ctx)
                    if ev(sym.get("visibility"), ctx) is not True:
                        continue
                    z = num(sym.get("zOrder"), ctx, 1)
                    items.append((z, li, fi, "vector", feat, sym, ctx))
            else:
                ctx = Ctx(view, lid, "coverage", {})
                sym, _ = resolve_symbolizer(self.rules, ctx)
                if ev(sym.get("visibility"), ctx) is not True:
                    continue
                z = num(sym.get("zOrder"), ctx, 1)
                items.append((z, li, 0, "coverage", data, sym, ctx))
        items.sort(key=lambda t: (t[0], t[1], t[2]))

        # painter's algorithm per zOrder: casings, then features, then centre lines
        zs = sorted(set(t[0] for t in items))
        for z in zs:
            group = [t for t in items if t[0] == z]
            for t in group:
                if t[3] == "vector":
                    self.draw_stroke_part(cr, vw, t, "casing")
            for t in group:
                if t[3] == "vector":
                    self.draw_feature(cr, vw, t)
                else:
                    self.draw_coverage(cr, vw, t)
            for t in group:
                if t[3] == "vector":
                    self.draw_stroke_part(cr, vw, t, "center")

        # label pass on top of everything
        self.draw_labels(cr, vw, items)
        surf.flush()
        surf.write_to_png(out_path)
        # Convert to plain RGB PNG of exactly width x height
        im = Image.open(out_path).convert("RGB")
        assert im.size == (W, H)
        im.save(out_path)

    # ---------------- strokes
    def stroke_params(self, st, ctx):
        if st is None or is_expr(st) and ev(st, ctx) is None:
            return None
        w = self.units.px(st.get("width", {"px": 1.0}), ctx)
        col = color(st.get("color", "black"), ctx)
        op = num(st.get("opacity"), ctx, 1.0)
        return w, col, op

    def apply_dash(self, cr, st, ctx, width):
        dp = st.get("dashPattern")
        if dp:
            d = [self.units.px(x, ctx) for x in ev(dp, ctx)]
            if any(x > 0 for x in d):
                off = self.units.px(st.get("dashOffset"), ctx) if st.get("dashOffset") is not None else 0.0
                cr.set_dash(d, off)
                return
        cr.set_dash([])

    def stroke_geometry(self, cr, vw, g, width, rgb, alpha, st=None, ctx=None):
        if width <= 0 or alpha <= 0:
            return
        cr.new_path()
        for coords, closed in geom_lines(g):
            path_line(cr, vw, coords)
            if closed:
                cr.close_path()
        cr.set_line_width(width)
        cr.set_line_cap(cairo.LINE_CAP_BUTT)
        cr.set_line_join(cairo.LINE_JOIN_MITER)
        cr.set_miter_limit(4.0)  # CHOICE: SVG default miter limit
        if st is not None:
            self.apply_dash(cr, st, ctx, width)
        else:
            cr.set_dash([])
        set_rgba(cr, rgb, alpha)
        cr.stroke()
        cr.set_dash([])

    def draw_stroke_part(self, cr, vw, t, part):
        _, _, _, _, feat, sym, ctx = t
        g = feat["geometry"]
        if geom_dim(g) == 0:
            return
        st = sym.get("stroke")
        if not isinstance(st, dict):
            return
        sub = st.get(part)
        if sub is None and part == "center":
            sub = st.get("centerLine")
        if not isinstance(sub, dict):
            return
        main = self.stroke_params(st, ctx)
        p = self.stroke_params(sub, ctx)
        if p is None:
            return
        w, col, op = p
        if part == "casing":
            w = (main[0] if main else 0) + 2 * w
        opacity = num(sym.get("opacity"), ctx, 1.0)
        cr.push_group()
        self.stroke_geometry(cr, vw, g, w, col, op)
        cr.pop_group_to_source()
        cr.paint_with_alpha(opacity)

    # ---------------- features
    def draw_feature(self, cr, vw, t):
        _, _, _, _, feat, sym, ctx = t
        g = feat["geometry"]
        opacity = num(sym.get("opacity"), ctx, 1.0)
        if opacity <= 0:
            return
        cr.push_group()  # /rec/core/opacity-together
        dim = geom_dim(g)
        if dim == 2:
            self.draw_fill(cr, vw, g, sym.get("fill"), ctx)
        if dim >= 1:
            st = sym.get("stroke")
            if isinstance(st, dict) and not is_expr(st):
                w, col, op = self.stroke_params(st, ctx)
                self.stroke_geometry(cr, vw, g, w, col, op, st, ctx)
        mk = sym.get("marker")
        if isinstance(mk, dict):
            for (x, y) in marker_points(g):
                self.draw_multigraphic(cr, mk, ctx, vw.px(x, y))
        cr.pop_group_to_source()
        cr.paint_with_alpha(opacity)

    def draw_fill(self, cr, vw, g, fill, ctx):
        if not isinstance(fill, dict) or is_expr(fill):
            return
        rgb = color(fill.get("color", "white"), ctx)
        a = num(fill.get("opacity"), ctx, 1.0)
        polys = geom_polys(g)
        cr.new_path()
        for rings in polys:
            path_polygon(cr, vw, rings)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        hatch, dots, stip = fill.get("hatch"), fill.get("dotpattern"), fill.get("stipple")
        if not (hatch or dots or stip):
            set_rgba(cr, rgb, a)
            cr.fill()
            return
        ext = cr.fill_extents()
        cr.save()
        cr.clip()
        if hatch:
            self.draw_hatch(cr, hatch, ctx, ext, rgb, a)
        if dots:
            self.draw_dotpattern(cr, dots, ctx, ext, rgb, a)
        if stip:
            self.draw_stipple(cr, vw, g, stip, ctx, rgb, a)
        cr.restore()

    def draw_hatch(self, cr, hatch, ctx, ext, rgb, a):
        # Defaults from the figure caption: width 1 px, angle 45 deg, distance 10 px
        w = self.units.px(hatch.get("width", 1.0), ctx)
        ang = num(hatch.get("angle"), ctx, 45.0)
        d = self.units.px(hatch.get("distance", 10.0), ctx)
        if d <= 0 or w <= 0:
            return
        th = math.radians(ang)
        # direction on screen (y down), angles counter-clockwise as seen on the map
        ux, uy = math.cos(th), -math.sin(th)
        nx, ny = -uy, ux  # unit normal
        x0, y0, x1, y1 = ext
        corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
        ps = [nx * x + ny * y for x, y in corners]  # offsets relative to map corner (0,0)
        k0, k1 = math.floor(min(ps) / d) - 1, math.ceil(max(ps) / d) + 1
        L = math.hypot(x1 - x0, y1 - y0) + 10
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        tc = ux * cx + uy * cy
        cr.new_path()
        for k in range(k0, k1 + 1):
            # point on line k closest to the extent centre
            px, py = nx * k * d, ny * k * d
            s = tc - (ux * px + uy * py)
            bx, by = px + ux * s, py + uy * s
            cr.move_to(bx - ux * L, by - uy * L)
            cr.line_to(bx + ux * L, by + uy * L)
        cr.set_line_width(w)
        cr.set_line_cap(cairo.LINE_CAP_BUTT)
        cr.set_dash([])
        set_rgba(cr, rgb, a)
        cr.stroke()

    def draw_dotpattern(self, cr, dots, ctx, ext, rgb, a):
        dist = ev(dots.get("distance"), ctx) if isinstance(dots, dict) else None
        if isinstance(dist, list):
            h, v = self.units.px(dist[0], ctx), self.units.px(dist[1], ctx)
        elif isinstance(dist, dict):
            h = self.units.px(dist.get("horizontal", 10.0), ctx)
            v = self.units.px(dist.get("vertical", 10.0), ctx)
        else:
            h = v = 10.0  # CHOICE: no default given; 10 px
        if h <= 0 or v <= 0:
            return
        x0, y0, x1, y1 = ext
        i0, i1 = math.floor((x0 - h / 2) / h) - 1, math.ceil((x1 - h / 2) / h) + 1
        j0, j1 = math.floor((y0 - v / 2) / v) - 1, math.ceil((y1 - v / 2) / v) + 1
        cr.new_path()
        for j in range(j0, j1 + 1):
            y = v / 2 + j * v
            for i in range(i0, i1 + 1):
                x = h / 2 + i * h
                cr.new_sub_path()
                cr.arc(x, y, 1.0, 0, 2 * math.pi)  # 2 px diameter
        set_rgba(cr, rgb, a)
        cr.fill()

    def draw_stipple(self, cr, vw, g, stip, ctx, rgb, a):
        ratio = num(stip.get("ratio") if isinstance(stip, dict) else None, ctx, 0.5)
        ratio = max(0.0, min(1.0, ratio))
        H, W = self.stipple_field.shape
        # Mask of pixels whose centre lies inside the polygon
        ms = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
        mc = cairo.Context(ms)
        mc.set_antialias(cairo.ANTIALIAS_NONE)
        mc.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        for rings in geom_polys(g):
            path_polygon(mc, vw, rings)
        mc.fill()
        ms.flush()
        stride = ms.get_stride()
        mask = np.frombuffer(ms.get_data(), np.uint8).reshape(H, stride)[:, :W] > 0
        on = mask & (self.stipple_field < ratio)
        arr = np.zeros((H, W, 4), np.uint8)
        pa = a
        arr[on, 0] = round(rgb[2] * pa * 255)
        arr[on, 1] = round(rgb[1] * pa * 255)
        arr[on, 2] = round(rgb[0] * pa * 255)
        arr[on, 3] = round(pa * 255)
        src = cairo.ImageSurface.create_for_data(memoryview(arr), cairo.FORMAT_ARGB32, W, H, W * 4)
        cr.reset_clip()
        cr.set_source_surface(src, 0, 0)
        cr.paint()
        self._keep = (arr, src)

    # ---------------- graphics (markers, labels)
    def draw_multigraphic(self, cr, mg, ctx, anchor, measure_only=False):
        """Draw (or measure) the elements of a MultiGraphic at anchor (pixel coords).
        Returns the list of element boxes."""
        els = ev(mg.get("elements"), ctx) if isinstance(mg, dict) else None
        if not els:
            return []
        dx0, dy0 = unit_point(mg.get("position"), ctx, self.units)
        gop = num(mg.get("opacity"), ctx, 1.0)
        boxes = []
        for el in els:
            if not isinstance(el, dict):
                continue
            el = normalize_dot(el)
            dx, dy = unit_point(el.get("position"), ctx, self.units)
            ax = anchor[0] + dx0 + dx
            ay = anchor[1] - dy0 - dy  # CHOICE 1: +y is upward on the map
            op = gop * num(el.get("opacity"), ctx, 1.0)
            t = el.get("type")
            if t == "Dot":
                b = self.draw_dot(cr, el, ctx, (ax, ay), op, measure_only)
            elif t == "Image":
                b = self.draw_image(cr, el, ctx, (ax, ay), op, measure_only)
            elif t == "Text":
                b = self.draw_text(cr, el, ctx, (ax, ay), op, measure_only)
            elif "elements" in el:
                b = None
                bs = self.draw_multigraphic(cr, el, ctx, (ax, ay), measure_only)
                boxes.extend(bs)
            else:
                b = None
            if b:
                boxes.append(b)
        return boxes

    def draw_dot(self, cr, el, ctx, p, op, measure_only):
        size = self.units.px(el.get("size", {"px": 10}), ctx)
        if size <= 0:
            return None
        rgb = color(el.get("color", "white"), ctx)
        st = el.get("stroke") or {}
        sop = num(st.get("opacity"), ctx, 1.0) if isinstance(st, dict) else 1.0
        r = size / 2
        if not measure_only:
            cr.new_path()
            cr.arc(p[0], p[1], r, 0, 2 * math.pi)
            set_rgba(cr, rgb, op * sop)
            cr.fill()
        return (p[0] - r, p[1] - r, p[0] + r, p[1] + r)

    def load_image(self, res, ctx):
        res = ev(res, ctx)
        path = ev(res.get("path"), ctx) if isinstance(res, dict) else None
        if not path:
            raise FileNotFoundError("only local image paths are supported: %r" % (res,))
        full = os.path.normpath(os.path.join(self.dir, path))
        if full not in self.image_cache:
            self.image_cache[full] = np.asarray(Image.open(full).convert("RGBA")).astype(np.float64) / 255.0
        return self.image_cache[full]

    def draw_image(self, cr, el, ctx, p, op, measure_only):
        img = self.load_image(el.get("image"), ctx)
        h, w = img.shape[:2]
        # hotSpot: from top-left, x right, y down; bare number = fraction; pc = percent
        hs = ev(el.get("hotSpot"), ctx)
        if hs is None:
            hx, hy = 0.5 * w, 0.5 * h
        else:
            if isinstance(hs, dict):
                hs = [hs.get("x", 0.5), hs.get("y", 0.5)]
            hx = self.hotspot_coord(hs[0], ctx, w)
            hy = self.hotspot_coord(hs[1], ctx, h)
        # CHOICE: an Image is drawn at its native size, one image pixel per map pixel,
        # with its top-left corner snapped to the pixel grid.
        x0 = round(p[0] - hx)
        y0 = round(p[1] - hy)
        if measure_only:
            return (x0, y0, x0 + w, y0 + h)
        tint = np.array(color(el.get("tint", "white"), ctx))
        black = np.array(color(el.get("blackTint", "black"), ctx))
        rgb = img[..., :3] * tint + (1 - img[..., :3]) * black
        a = img[..., 3] * op
        arr = np.zeros((h, w, 4), np.uint8)
        arr[..., 0] = np.round(rgb[..., 2] * a * 255)
        arr[..., 1] = np.round(rgb[..., 1] * a * 255)
        arr[..., 2] = np.round(rgb[..., 0] * a * 255)
        arr[..., 3] = np.round(a * 255)
        src = cairo.ImageSurface.create_for_data(memoryview(arr), cairo.FORMAT_ARGB32, w, h, w * 4)
        cr.set_source_surface(src, x0, y0)
        cr.paint()
        self._keep = (arr, src)
        return (x0, y0, x0 + w, y0 + h)

    def hotspot_coord(self, v, ctx, size):
        if isinstance(v, dict) and not is_expr(v) and len(v) == 1:
            (u, x), = v.items()
            x = float(ev(x, ctx))
            if u == "pc":
                return x / 100.0 * size
            return self.units.px(v, ctx)
        return float(ev(v, ctx)) * size  # bare number: fraction of width/height

    def font_setup(self, cr, font, ctx):
        font = font if isinstance(font, dict) else {}
        face = ev(font.get("face"), ctx) or "Arial"  # CHOICE: no default face given
        size_pt = num(font.get("size"), ctx, 10.0)  # CHOICE: no default size given
        bold = ev(font.get("bold"), ctx) is True
        italic = ev(font.get("italic"), ctx) is True
        cr.select_font_face(face, cairo.FONT_SLANT_ITALIC if italic else cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size_pt * self.units.font_pt_px)  # size in points -> em in px
        return font

    def text_layout(self, cr, el, ctx, p):
        txt = text_value(el.get("text"), ctx)
        font = self.font_setup(cr, el.get("font"), ctx)
        asc, desc = cr.font_extents()[0], cr.font_extents()[1]
        adv = cr.text_extents(txt).x_advance
        al = ev(el.get("alignment"), ctx)
        hal, val = "center", "middle"
        if isinstance(al, list) and len(al) == 2:
            hal, val = al
        elif isinstance(al, dict):
            hal = al.get("hAlignment", al.get("horzAlignment", al.get("horizontal", hal)))
            val = al.get("vAlignment", al.get("vertAlignment", al.get("vertical", val)))
        x = {"left": p[0], "center": p[0] - adv / 2, "right": p[0] - adv}[hal]
        base = {"top": p[1] + asc, "bottom": p[1] - desc, "middle": p[1] + (asc - desc) / 2}[val]
        ol = font.get("outline")
        ow = 0.0
        if isinstance(ol, dict):
            ow = num(ol.get("size"), ctx, 1.0)
        return txt, font, x, base, asc, desc, adv, ol, ow

    def draw_text(self, cr, el, ctx, p, op, measure_only):
        cr.save()
        txt, font, x, base, asc, desc, adv, ol, ow = self.text_layout(cr, el, ctx, p)
        box = (x - ow, base - asc - ow, x + adv + ow, base + desc + ow)
        if not measure_only and txt:
            if isinstance(ol, dict) and ow > 0:
                cr.new_path()
                cr.move_to(x, base)
                cr.text_path(txt)
                cr.set_line_width(2 * ow)  # CHOICE 10: outline extends `size` px outward
                cr.set_line_join(cairo.LINE_JOIN_ROUND)
                cr.set_dash([])
                set_rgba(cr, color(ol.get("color", "white"), ctx),
                         op * num(ol.get("opacity"), ctx, 1.0))
                cr.stroke()
            cr.new_path()
            cr.move_to(x, base)
            cr.text_path(txt)
            set_rgba(cr, color(font.get("color", "black"), ctx), op * num(font.get("opacity"), ctx, 1.0))
            cr.fill()
        cr.restore()
        return box

    # ---------------- labels
    def draw_labels(self, cr, vw, items):
        cands = []  # (priority, order, sym, ctx, anchors, layer, content, minSpacing)
        order = 0
        for t in items:
            if t[3] != "vector":
                continue
            _, li, fi, _, feat, sym, ctx = t
            lab = sym.get("label")
            if not isinstance(lab, dict):
                continue
            pl = lab.get("placement") or {}
            pl = pl if isinstance(pl, dict) else {}
            pr = num(pl.get("priority"), ctx, 0.0)  # null -> 0; CHOICE: default 0
            mins = self.units.px(pl.get("minSpacing"), ctx) if pl.get("minSpacing") is not None else None
            content = tuple(text_value(e.get("text"), ctx) for e in (ev(lab.get("elements"), ctx) or [])
                            if isinstance(e, dict) and e.get("type") == "Text")
            cands.append((pr, order, lab, ctx, feat["geometry"], ctx.layer_id, content, mins))
            order += 1
        # higher priority first; ties in drawing order
        cands.sort(key=lambda c: (-c[0], c[1]))
        placed_boxes = []
        reps = {}
        W, H = vw.W, vw.H
        for pr, _, lab, ctx, g, lid, content, mins in cands:
            for anchor in self.label_anchors(vw, g, mins):
                boxes = self.draw_multigraphic(cr, lab, ctx, anchor, measure_only=True)
                if not boxes:
                    continue
                bx = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                      max(b[2] for b in boxes), max(b[3] for b in boxes))
                # /rec/labels/overlap: omit labels extending beyond the map edges
                if bx[0] < 0 or bx[1] < 0 or bx[2] > W or bx[3] > H:
                    continue
                if any(not (bx[2] <= o[0] or bx[0] >= o[2] or bx[3] <= o[1] or bx[1] >= o[3])
                       for o in placed_boxes):
                    continue
                key = (lid, content)
                if mins is not None and mins > 0:
                    if any(math.hypot(anchor[0] - q[0], anchor[1] - q[1]) < mins for q in reps.get(key, [])):
                        continue
                reps.setdefault(key, []).append(anchor)
                placed_boxes.append(bx)
                self.draw_multigraphic(cr, lab, ctx, anchor)
                if mins is None and geom_dim(g) == 1:
                    break

    def label_anchors(self, vw, g, mins):
        dim = geom_dim(g)
        if dim == 0:
            return [vw.px(*p[:2]) for p in marker_points(g)]
        if dim == 2:
            return [vw.px(*p[:2]) for p in marker_points(g)]
        # lines: candidates along the line
        out = []
        for coords, _ in geom_lines(g):
            pts = [vw.px(x, y) for x, y in coords]
            seglen = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
            total = sum(seglen)
            if total <= 0:
                continue
            if mins is None:
                ss = [total / 2]  # CHOICE: one label at mid-length when no spacing given
            else:
                step = 4.0
                ss = [i * step for i in range(int(total / step) + 1)]
            for s in ss:
                acc = 0.0
                for (a, b), L in zip(zip(pts, pts[1:]), seglen):
                    if acc + L >= s and L > 0:
                        f = (s - acc) / L
                        out.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])))
                        break
                    acc += L
        return out

    # ---------------- coverage
    def draw_coverage(self, cr, vw, t):
        _, _, _, _, bands, sym, ctx = t
        first = next(iter(bands.values()))
        ncols, nrows, xll, yll, cs = first["ncols"], first["nrows"], first["xll"], first["yll"], first["cs"]
        nod = first["nodata"]
        ytop = yll + nrows * cs
        W, H = vw.W, vw.H
        valid = np.ones((nrows, ncols), bool)
        for b in bands.values():
            valid &= b["data"] != b["nodata"]

        class CellCtx(Ctx):
            pass

        # Resolve per-cell channel expressions; only bare identifiers are supported here.
        def channel(expr):
            if expr is None:
                return None
            if isinstance(expr, dict) and "property" in expr:
                return bands[expr["property"]]["data"].astype(np.float64)
            if isinstance(expr, (int, float)):
                return np.full((nrows, ncols), float(expr))
            raise NotImplementedError("coverage expression %r" % (expr,))

        single = channel(sym.get("singleChannel"))
        if single is None and len(bands) == 1:
            single = next(iter(bands.values()))["data"].astype(np.float64)
        cm = ev(sym.get("colorMap"), ctx)
        om = ev(sym.get("opacityMap"), ctx)
        rgb = None
        if sym.get("colorChannels") is not None:
            cc = sym["colorChannels"]
            rgb = np.stack([channel(cc.get(k)) if isinstance(cc, dict) else channel(cc[i])
                            for i, k in enumerate("rgb")], -1)
        elif cm:
            rgb = apply_color_map(cm, single, ctx)
        elif single is not None:
            rgb = np.repeat(np.clip(single, 0, 1)[..., None], 3, -1)
        alpha = np.ones((nrows, ncols))
        ac = sym.get("alphaChannel")
        if ac is not None:
            alpha = alpha * channel(ac) if not isinstance(ac, (int, float)) else alpha * float(ac)
        if om:
            alpha = alpha * apply_opacity_map(om, single, ctx)
        hs = sym.get("hillShading")
        if isinstance(hs, dict):
            shade = self.hill_shade(single, cs, hs, ctx)
            hcm = ev(hs.get("colorMap"), ctx)
            hom = ev(hs.get("opacityMap"), ctx)
            if hcm:
                rgb = apply_color_map(hcm, shade, ctx)
            else:
                rgb = rgb * shade[..., None]
            if hom:
                alpha = alpha * apply_opacity_map(hom, shade, ctx)
        alpha = np.where(valid, np.clip(alpha, 0, 1), 0.0)
        rgb = np.clip(rgb, 0, 1)
        # pixel centre -> cell (/req/coverage/single-channel)
        bb = vw.bb
        xs = bb[0] + (np.arange(W) + 0.5) * (bb[2] - bb[0]) / W
        ys = bb[3] - (np.arange(H) + 0.5) * (bb[3] - bb[1]) / H
        ci = np.floor((xs - xll) / cs).astype(int)
        ri = np.floor((ytop - ys) / cs).astype(int)
        okx = (ci >= 0) & (ci < ncols)
        oky = (ri >= 0) & (ri < nrows)
        CI = np.clip(ci, 0, ncols - 1)[None, :].repeat(H, 0)
        RI = np.clip(ri, 0, nrows - 1)[:, None].repeat(W, 1)
        ok = oky[:, None] & okx[None, :]
        prgb = rgb[RI, CI]
        pa = np.where(ok, alpha[RI, CI], 0.0)
        arr = np.zeros((H, W, 4), np.uint8)
        arr[..., 0] = np.round(prgb[..., 2] * pa * 255)
        arr[..., 1] = np.round(prgb[..., 1] * pa * 255)
        arr[..., 2] = np.round(prgb[..., 0] * pa * 255)
        arr[..., 3] = np.round(pa * 255)
        src = cairo.ImageSurface.create_for_data(memoryview(arr), cairo.FORMAT_ARGB32, W, H, W * 4)
        cr.set_source_surface(src, 0, 0)
        cr.paint_with_alpha(num(sym.get("opacity"), ctx, 1.0))
        self._keep = (arr, src)

    def hill_shade(self, z, cs, hs, ctx):
        # map resolution as fine as the coverage's in all cases here: use the cells
        mpp = self.units.m_per_px
        if mpp > cs:
            raise NotImplementedError("coarser map resolution than coverage")
        f = num(hs.get("factor"), ctx, 1.0)
        sun = hs.get("sun") or {}
        az = math.radians(num(sun.get("azimuth"), ctx, 315.0))   # CHOICE: default 315
        el = math.radians(num(sun.get("elevation"), ctx, 45.0))  # CHOICE: default 45
        zp = np.pad(z, 1, mode="edge")
        dzdx = (zp[1:-1, 2:] - zp[1:-1, :-2]) / (2 * cs)   # east
        dzdy = (zp[:-2, 1:-1] - zp[2:, 1:-1]) / (2 * cs)   # north (row 0 is north)
        nx, ny, nz = -f * dzdx, -f * dzdy, np.ones_like(z)
        n = np.sqrt(nx * nx + ny * ny + nz * nz)
        sx, sy, sz = math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)
        return np.clip((nx * sx + ny * sy + nz * sz) / n, 0, 1)


def map_entries(m, ctx):
    out = []
    for e in m:
        if isinstance(e, dict):
            out.append((float(ev(e.get("value"), ctx)), e.get("color", e.get("opacity"))))
        else:
            out.append((float(ev(e[0], ctx)), e[1]))
    out.sort(key=lambda t: t[0])
    return out


def apply_color_map(m, v, ctx):
    ent = map_entries(m, ctx)
    xs = np.array([e[0] for e in ent])
    cols = np.array([color(e[1], ctx) for e in ent])
    # linear interpolation, clamped to first / last entry outside the range
    return np.stack([np.interp(v, xs, cols[:, i]) for i in range(3)], -1)


def apply_opacity_map(m, v, ctx):
    ent = map_entries(m, ctx)
    xs = np.array([e[0] for e in ent])
    ops = np.array([float(ev(e[1], ctx)) for e in ent])
    return np.interp(v, xs, ops)


def read_asc(path):
    hdr = {}
    with open(path, encoding="utf-8") as f:
        for _ in range(6):
            k, v = f.readline().split()
            hdr[k.lower()] = float(v)
        data = np.loadtxt(f)
    cs = hdr["cellsize"]
    xll = hdr.get("xllcorner", hdr.get("xllcenter", 0) - cs / 2)
    yll = hdr.get("yllcorner", hdr.get("yllcenter", 0) - cs / 2)
    return {"ncols": int(hdr["ncols"]), "nrows": int(hdr["nrows"]), "xll": xll, "yll": yll,
            "cs": cs, "nodata": hdr.get("nodata_value", -9999), "data": data}


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    cases = argv or sorted(c for c in os.listdir(CASES)
                           if os.path.isfile(os.path.join(CASES, c, "style.cs.json")))
    n = 0
    failed = []
    for case in cases:
        r = Renderer(case)
        views = sorted(f for f in os.listdir(r.dir) if re.match(r"view-\d+\.json$", f))
        for vf in views:
            N = re.match(r"view-(\d+)", vf).group(1)
            out = os.path.join(OUT, "%s-%s.png" % (case, N))
            try:
                r.render(os.path.join(r.dir, vf), out)
                n += 1
                print("ok  ", out)
            except Exception as e:  # noqa
                import traceback
                traceback.print_exc()
                failed.append((case, vf, repr(e)))
    print("rendered", n, "images; failed:", failed)


if __name__ == "__main__":
    main(sys.argv[1:])
