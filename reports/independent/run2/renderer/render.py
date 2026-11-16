"""Renderer for OGC Cartographic Symbology 2.0 Part 1 (draft), written from the
requirement text in spec/1-core only.

Usage:
  uv run --no-project --with numpy --with pillow --with skia-python \
      python renderer/render.py [case ...]

skia-python is used purely as a general 2D vector graphics library
(anti-aliased paths, strokes with butt caps / miter joins, dashes, clipping,
text from TrueType files).  All symbology logic is in this file and expr.py.
The numbered choices N-xx refer to notes.md.
"""
import copy
import datetime as dt
import json
import math
import os
import re
import sys

import numpy as np
import skia
from PIL import Image as PILImage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from expr import Context, evaluate, is_expr, to_text  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "spec", "1-core")
CASES = os.path.join(ROOT, "cases")
OUT = os.path.join(ROOT, "out")
FONTS = "C:/Windows/Fonts"

# --------------------------------------------------------------------------
# Named colours: parsed from the "Named web color enumeration" table of
# clause 17 (the JSON schema lists the names but gives no values; N-COLNAMES)
# --------------------------------------------------------------------------


def _load_named_colors():
    txt = open(os.path.join(SPEC, "sections", "clause_17_cscss.adoc"), encoding="utf-8").read()
    names = {}
    for m in re.finditer(r"(?m)^\|?\s*([A-Za-z]+)\s*\|\s*`0x([0-9a-fA-F]{6})`", txt):
        h = m.group(2)
        names[m.group(1)] = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return names


NAMED = _load_named_colors()

# --------------------------------------------------------------------------
# Defaults (clause 7, "Default class member values")
# --------------------------------------------------------------------------
DEFAULT_STROKE = {"color": "black", "width": {"px": 1}, "opacity": 1}
DEFAULT_FILL = {"color": "white", "opacity": 1}
DEFAULT_DOT = {"type": "Dot", "size": {"px": 10}, "color": "white"}
DEFAULT_MARKER = {"elements": [DEFAULT_DOT]}
DEFAULT_IMAGE = {"hotSpot": [0.5, 0.5], "tint": "white", "blackTint": "black", "alphaThreshold": 0}

CAPABILITIES = {k: True for k in (
    "vector", "coverage", "labels", "hillshading", "fontoutlines", "hatches", "stipples",
    "dashes", "casing", "parametervalues", "arithmetic", "conditional")}


def default_for(path):
    if path == ("fill",):
        return DEFAULT_FILL
    if path == ("stroke",):
        return DEFAULT_STROKE
    if path in (("marker",), ("label",)):
        return DEFAULT_MARKER if path == ("marker",) else {"elements": []}
    if path and path[-1] == "color":
        return "black"
    return {}


def color_to_dict(c):
    if isinstance(c, dict) and not is_expr(c):
        return c
    rgb = parse_color(c, None)
    if rgb is None:
        return {}
    return {"r": rgb[0] * 255, "g": rgb[1] * 255, "b": rgb[2] * 255}


def merge(old, new, path):
    """Apply a symbolizer property value `new` over `old` (N-ALTER)."""
    if isinstance(new, dict) and not is_expr(new) and new.get("alter") is True:
        if path and path[-1] in ("color", "tint", "blackTint"):
            base = color_to_dict(old if old is not None else default_for(path))
        elif isinstance(old, dict) and not is_expr(old):
            base = old
        else:
            base = default_for(path)
        out = copy.deepcopy(base)
        for k, v in new.items():
            if k == "alter":
                continue
            out[k] = merge(base.get(k), v, path + (k,))
        _dot_link(out, new)
        return out
    if isinstance(new, dict) and set(new.keys()) == {"index", "value"}:
        base = list(old) if isinstance(old, list) else list(copy.deepcopy(
            default_for(path[:-1]).get(path[-1], [])) if path else [])
        i = int(new["index"])
        while len(base) <= i:
            base.append(None)
        base[i] = merge(base[i], new["value"], path + ("[]",))
        return base
    return copy.deepcopy(new)


def _dot_link(out, new):
    """/req/vector/dot: size <-> stroke.width, color <-> stroke.color; the value set last applies."""
    if out.get("type") != "Dot":
        return
    st = out.get("stroke")
    if isinstance(st, dict):
        if "size" in new and "width" in st:
            st.pop("width")
        if "color" in new and "color" in st:
            st.pop("color")
        nst = new.get("stroke") if isinstance(new.get("stroke"), dict) else {}
        if "width" in nst:
            out.pop("size", None)
        if "color" in nst:
            out.pop("color", None)


def apply_symbolizer(acc, sym):
    for k, v in sym.items():
        if k == "$comment":
            continue
        acc[k] = merge(acc.get(k), v, (k,))


def truth(v):
    """Selector result: only true selects (null and false do not)."""
    if isinstance(v, np.ndarray):
        if v.size and v.all():
            return True
        if not v.any():
            return False
        raise NotImplementedError("selector varies between coverage cells")
    return v is True or (isinstance(v, (np.bool_,)) and bool(v))


def resolve(rules, ctx):
    acc = {}

    def visit(rule):
        sel = rule.get("selector")
        if sel is not None and not truth(evaluate(sel, ctx)):
            return
        apply_symbolizer(acc, rule.get("symbolizer") or {})
        for n in rule.get("nestedRules") or []:
            visit(n)

    for r in rules:
        visit(r)
    return acc


# --------------------------------------------------------------------------
# Value resolution helpers
# --------------------------------------------------------------------------


class View:
    def __init__(self, v):
        self.v = v
        self.minx, self.miny, self.maxx, self.maxy = v["bbox"]
        self.W, self.H = v["width"], v["height"]
        self.resx = (self.maxx - self.minx) / self.W
        self.resy = (self.maxy - self.miny) / self.H
        self.mm_px = v.get("pixelSize_mm", 0.28)
        self.sd = v["scaleDenominator"]

    def to_px(self, xy):
        a = np.asarray(xy, dtype=float)
        return np.column_stack(((a[:, 0] - self.minx) / self.resx, (self.maxy - a[:, 1]) / self.resy))

    def sys(self, layer_id, layer_type):
        viz = self.v.get("visualization", {})
        d = dt.date.fromisoformat(viz["date"]) if "date" in viz else None
        dtime = (dt.datetime.fromisoformat(viz["dateTime"]) if "dateTime" in viz
                 else (dt.datetime(d.year, d.month, d.day) if d else None))
        ti = viz.get("timeInterval")
        s = {
            "viz.sd": self.sd,
            "viz.date": d,
            "viz.dateTime": dtime,
            "viz.timeOfDay": dtime.time() if dtime else None,
            "viz.pass": 0,
            "dataLayer.id": layer_id,
            "dataLayer.type": layer_type,
            "capabilities": CAPABILITIES,
        }
        if ti:
            def inst(x):
                x = dt.datetime.fromisoformat(x) if "T" in x else dt.datetime.fromisoformat(x + "T00:00:00")
                return x
            st, en = inst(ti["start"]), inst(ti["end"])
            s["viz.timeInterval"] = {"start": st, "end": en}
            s["viz.timeInterval.start"] = st
            s["viz.timeInterval.end"] = en
        return s


UNIT_KEYS = ("px", "mm", "cm", "in", "pt", "em", "pc", "m", "ft")


def num(v, ctx, default=None):
    v = evaluate(v, ctx) if v is not None else None
    if v is None:
        return default
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    return v


def to_px(v, ctx, view, default=None, em_px=None, rel_to=None):
    """Convert a uom-qualified value to pixels (N-UNITS)."""
    if v is None:
        return default
    unit = "px"
    if isinstance(v, dict) and not is_expr(v):
        for k in UNIT_KEYS:
            if k in v:
                unit, v = k, v[k]
                break
    x = evaluate(v, ctx)
    if x is None:
        return 0.0  # /req/parameter-values/null: numbers -> 0
    x = float(x)
    mm = view.mm_px
    if unit == "px":
        return x
    if unit == "mm":
        return x / mm
    if unit == "cm":
        return x * 10 / mm
    if unit == "in":
        return x * 25.4 / mm
    if unit == "pt":
        return x * 25.4 / 72 / mm
    if unit == "em":
        return x * (em_px if em_px else 10 * 25.4 / 72 / mm)
    if unit == "m":
        return x / view.resx
    if unit == "ft":
        return x * 0.3048 / view.resx
    if unit == "pc":
        return x / 100.0 * (rel_to if rel_to is not None else 0.0)
    return x


def parse_color(c, ctx, scale255=True):
    """Return (r,g,b) in 0..1 or None."""
    if ctx is not None and is_expr(c):
        c = evaluate(c, ctx)
    if c is None:
        return None
    if isinstance(c, str):
        if c.startswith("#"):
            h = c[1:]
            if len(h) == 3:
                h = "".join(ch * 2 for ch in h)
            return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        if c in NAMED:
            return NAMED[c]
        lc = {k.lower(): v for k, v in NAMED.items()}
        if c.lower() in lc:
            return lc[c.lower()]
        raise ValueError("unknown colour %r" % c)
    div = 255.0 if scale255 else 1.0
    if isinstance(c, (list, tuple)):
        vals = [num(x, ctx, 0.0) for x in c[:3]]
        return tuple(float(x) / div for x in vals)
    if isinstance(c, dict):
        return tuple(float(num(c.get(k), ctx, 0.0)) / div for k in ("r", "g", "b"))
    raise ValueError("bad colour %r" % (c,))


def skcolor(rgb, a=1.0):
    return skia.Color4f(float(rgb[0]), float(rgb[1]), float(rgb[2]), float(max(0.0, min(1.0, a))))


def get_obj(sym, key, ctx, default=None):
    if key not in sym:
        return copy.deepcopy(default)
    v = sym[key]
    if is_expr(v):
        v = evaluate(v, ctx)
    return v


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------


def load_layer(case_dir, layer_id):
    gj = os.path.join(case_dir, layer_id + ".geojson")
    if os.path.exists(gj):
        return {"type": "vector", "id": layer_id, "data": json.load(open(gj, encoding="utf-8"))}
    bands = {}
    for fn in sorted(os.listdir(case_dir)):
        if fn.startswith(layer_id + ".") and fn.endswith(".asc"):
            band = fn[len(layer_id) + 1:-4]
            bands[band] = read_asc(os.path.join(case_dir, fn))
    if bands:
        return {"type": "coverage", "id": layer_id, "bands": bands}
    raise FileNotFoundError(layer_id)


def read_asc(path):
    hdr = {}
    with open(path) as f:
        for _ in range(6):
            k, v = f.readline().split()
            hdr[k.lower()] = float(v)
        arr = np.loadtxt(f, dtype=float)
    nd = hdr.get("nodata_value")
    arr = arr.reshape(int(hdr["nrows"]), int(hdr["ncols"]))
    if nd is not None:
        arr = np.where(arr == nd, np.nan, arr)
    return hdr, arr


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------


def geom_parts(g):
    t = g["type"]
    c = g["coordinates"]
    if t == "Point":
        return "point", [[c]]
    if t == "MultiPoint":
        return "point", [[p] for p in c]
    if t == "LineString":
        return "line", [c]
    if t == "MultiLineString":
        return "line", c
    if t == "Polygon":
        return "polygon", [c]
    if t == "MultiPolygon":
        return "polygon", c
    raise NotImplementedError(t)


def ring_centroid(r):
    r = np.asarray(r, dtype=float)
    x, y = r[:, 0], r[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y1 - x1 * y
    a = cross.sum() / 2
    if abs(a) < 1e-12:
        return 0.0, x.mean(), y.mean()
    cx = ((x + x1) * cross).sum() / (6 * a)
    cy = ((y + y1) * cross).sum() / (6 * a)
    return a, cx, cy


def polygon_centroid(polys):
    """Area-weighted centroid of all polygons (holes subtracted) (N-CENTROID)."""
    A = SX = SY = 0.0
    for rings in polys:
        for i, r in enumerate(rings):
            a, cx, cy = ring_centroid(r)
            a = abs(a) * (1 if i == 0 else -1)
            A += a
            SX += a * cx
            SY += a * cy
    if A == 0:
        p = np.asarray(polys[0][0], dtype=float)
        return p[:, 0].mean(), p[:, 1].mean()
    return SX / A, SY / A


def make_path(view, kind, parts):
    path = skia.Path()
    if kind == "line":
        for line in parts:
            p = view.to_px(line)
            path.moveTo(*p[0])
            for q in p[1:]:
                path.lineTo(*q)
    elif kind == "polygon":
        path.setFillType(skia.PathFillType.kEvenOdd)  # N-HOLES
        for rings in parts:
            for r in rings:
                p = view.to_px(r)
                path.moveTo(*p[0])
                for q in p[1:]:
                    path.lineTo(*q)
                path.close()
    return path


def marker_anchors(view, kind, parts):
    if kind == "point":
        return [tuple(view.to_px(pt)[0]) for pt in parts]
    if kind == "line":
        out = []
        for line in parts:
            out.extend(tuple(p) for p in view.to_px(line))
        return out
    cx, cy = polygon_centroid(parts)
    return [tuple(view.to_px([[cx, cy]])[0])]


# --------------------------------------------------------------------------
# Drawing primitives
# --------------------------------------------------------------------------


def stroke_paint(rgb, alpha, width):
    p = skia.Paint()
    p.setAntiAlias(True)
    p.setColor4f(skcolor(rgb, alpha))
    p.setStyle(skia.Paint.kStroke_Style)
    p.setStrokeWidth(width)
    p.setStrokeCap(skia.Paint.kButt_Cap)      # clause 8: butt caps
    p.setStrokeJoin(skia.Paint.kMiter_Join)   # clause 8: miter joins
    p.setStrokeMiter(4.0)                     # N-MITER
    return p


def fill_paint(rgb, alpha):
    p = skia.Paint()
    p.setAntiAlias(True)
    p.setColor4f(skcolor(rgb, alpha))
    p.setStyle(skia.Paint.kFill_Style)
    return p


def styling_values(st, ctx, view, defaults=DEFAULT_STROKE):
    """Resolve a StrokeStyling object to (rgb, opacity, width_px)."""
    if st is None:
        return None
    if is_expr(st):
        st = evaluate(st, ctx)
    if not isinstance(st, dict):
        return None
    c = parse_color(st.get("color", defaults.get("color", "black")), ctx)
    if c is None:
        c = (0, 0, 0)
    op = num(st.get("opacity", defaults.get("opacity", 1)), ctx, 0.0)
    w = to_px(st.get("width", defaults.get("width", {"px": 1})), ctx, view, 0.0)
    return c, op, w


def draw_stroke(canvas, path, stv, dash=None):
    rgb, op, w = stv
    if w <= 0 or op <= 0:  # N-ZEROWIDTH
        return
    p = stroke_paint(rgb, op, w)
    if dash:
        intervals, phase = dash
        p.setPathEffect(skia.DashPathEffect.Make(intervals, phase))
    canvas.drawPath(path, p)


def dash_of(stroke, ctx, view):
    if not isinstance(stroke, dict):
        return None
    dp = stroke.get("dashPattern")
    if dp is None:
        return None
    if is_expr(dp):
        dp = evaluate(dp, ctx)
    vals = [to_px(x, ctx, view, 0.0) for x in dp]
    if not vals or sum(vals) <= 0:
        return None
    if len(vals) % 2:
        vals = vals * 2  # odd count repeated (N-DASHODD)
    off = to_px(stroke.get("dashOffset"), ctx, view, 0.0) if stroke.get("dashOffset") is not None else 0.0
    period = sum(vals)
    # N-DASHOFFSET: the pattern is "preceded by an offset": it starts dashOffset
    # along the line, i.e. the pattern is shifted forward along the line.
    phase = (-off) % period
    return vals, phase


def draw_fill(canvas, path, fill, ctx, view):
    if fill is None:
        return
    if is_expr(fill):
        fill = evaluate(fill, ctx)
    if not isinstance(fill, dict):
        return
    rgb = parse_color(fill.get("color", "white"), ctx) or (0, 0, 0)
    op = num(fill.get("opacity", 1), ctx, 0.0)
    pattern = False
    if fill.get("hatch") is not None:
        pattern = True
        draw_hatch(canvas, path, fill["hatch"], rgb, op, ctx, view)
    if fill.get("dotpattern") is not None:
        pattern = True
        draw_dotpattern(canvas, path, fill["dotpattern"], rgb, op, ctx, view)
    if fill.get("stipple") is not None:
        pattern = True
        draw_stipple(canvas, path, fill["stipple"], rgb, op, ctx, view)
    if not pattern:  # N-PATTERNFILL: a pattern replaces the solid fill
        if op > 0:
            canvas.drawPath(path, fill_paint(rgb, op))


def draw_hatch(canvas, path, hatch, rgb, op, ctx, view):
    if is_expr(hatch):
        hatch = evaluate(hatch, ctx)
    w = to_px(hatch.get("width", {"px": 1}), ctx, view, 1.0)          # N-HATCHDEF
    dist = to_px(hatch.get("distance", {"px": 10}), ctx, view, 10.0)
    ang = num(hatch.get("angle", 45), ctx, 45.0)
    if isinstance(hatch.get("angle"), dict) and "rad" in hatch["angle"]:
        ang = math.degrees(num(hatch["angle"]["rad"], ctx, 0.0))
    elif isinstance(hatch.get("angle"), dict) and "deg" in hatch["angle"]:
        ang = num(hatch["angle"]["deg"], ctx, 0.0)
    if dist <= 0 or w <= 0:
        return
    a = math.radians(ang)
    # N-HATCHANGLE: 0 = horizontal, increasing clockwise on the map (screen y down)
    d = (math.cos(a), math.sin(a))
    n = (-math.sin(a), math.cos(a))
    b = path.computeTightBounds()
    corners = [(b.left(), b.top()), (b.right(), b.top()), (b.left(), b.bottom()), (b.right(), b.bottom())]
    proj = [c[0] * n[0] + c[1] * n[1] for c in corners]
    L = math.hypot(b.width(), b.height()) + abs(b.left()) + abs(b.top()) + 10
    k0, k1 = math.floor(min(proj) / dist) - 1, math.ceil(max(proj) / dist) + 1
    lines = skia.Path()
    cx, cy = (b.left() + b.right()) / 2, (b.top() + b.bottom()) / 2
    t = cx * d[0] + cy * d[1]
    for k in range(k0, k1 + 1):
        # lines anchored to the map's pixel origin (N-PATTERNORIGIN)
        px, py = k * dist * n[0] + t * d[0], k * dist * n[1] + t * d[1]
        lines.moveTo(px - L * d[0], py - L * d[1])
        lines.lineTo(px + L * d[0], py + L * d[1])
    canvas.save()
    canvas.clipPath(path, skia.ClipOp.kIntersect, True)
    p = stroke_paint(rgb, op, w)
    canvas.drawPath(lines, p)
    canvas.restore()


DOTPATTERN_DOT_PX = 2.0   # N-DOTSIZE


def draw_dotpattern(canvas, path, dp, rgb, op, ctx, view):
    if is_expr(dp):
        dp = evaluate(dp, ctx)
    dist = dp.get("distance", {})
    if isinstance(dist, list):
        h, v = dist
    else:
        h, v = dist.get("horizontal", {"px": 10}), dist.get("vertical", {"px": 10})
    h = to_px(h, ctx, view, 10.0)
    v = to_px(v, ctx, view, 10.0)
    if h <= 0 or v <= 0:
        return
    b = path.computeTightBounds()
    canvas.save()
    canvas.clipPath(path, skia.ClipOp.kIntersect, True)
    p = fill_paint(rgb, op)
    dots = skia.Path()
    i0, i1 = math.floor(b.left() / h) - 1, math.ceil(b.right() / h) + 1
    j0, j1 = math.floor(b.top() / v) - 1, math.ceil(b.bottom() / v) + 1
    r = DOTPATTERN_DOT_PX / 2
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            dots.addCircle((i + 0.5) * h, (j + 0.5) * v, r)
    canvas.drawPath(dots, p)
    canvas.restore()


def draw_stipple(canvas, path, st, rgb, op, ctx, view):
    if is_expr(st):
        st = evaluate(st, ctx)
    ratio = num(st.get("ratio", 0.5), ctx, 0.0)
    ratio = max(0.0, min(1.0, ratio))
    # N-STIPPLE: 1-pixel dots at pseudo-random pixels, each pixel on with
    # probability `ratio`, from a fixed seed so that the image is reproducible.
    rng = np.random.default_rng(20261114)
    mask = rng.random((view.H, view.W)) < ratio
    img = np.zeros((view.H, view.W, 4), dtype=np.uint8)
    img[..., 0] = int(round(rgb[0] * 255))
    img[..., 1] = int(round(rgb[1] * 255))
    img[..., 2] = int(round(rgb[2] * 255))
    img[..., 3] = np.where(mask, int(round(255 * op)), 0)
    sk = skia.Image.fromarray(img, colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)
    canvas.save()
    canvas.clipPath(path, skia.ClipOp.kIntersect, True)
    canvas.drawImage(sk, 0, 0)
    canvas.restore()


# ----------------------------- text --------------------------------------
_TF = {}


def typeface(face, bold, italic):
    face = (face or "Arial")
    base = {"arial": "arial", "times new roman": "times", "times": "times"}.get(face.lower(), "arial")  # N-FONTFACE
    suffix = {(False, False): "", (True, False): "bd", (False, True): "i", (True, True): "bi"}[(bool(bold), bool(italic))]
    fn = os.path.join(FONTS, base + suffix + ".ttf")
    if fn not in _TF:
        _TF[fn] = skia.Typeface.MakeFromFile(fn)
    return _TF[fn]


class TextLayout:
    """Laid-out Text graphic: blob, origin and bounding box in pixels."""

    def __init__(self, elem, ctx, view, anchor, group_offset=(0.0, 0.0)):
        self.ok = False
        txt = to_text(evaluate(elem.get("text"), ctx))  # N-TEXTCONV
        if not txt:
            return
        font = elem.get("font") or {}
        if is_expr(font):
            font = evaluate(font, ctx)
        size_pt = num(font.get("size", 10), ctx, 0.0)  # N-FONTDEF
        size_px = size_pt * 25.4 / 72 / view.mm_px    # /req/vector/fonts: size in points
        if size_px <= 0:
            return
        tf = typeface(evaluate(font.get("face"), ctx), num(font.get("bold", False), ctx, 0),
                      num(font.get("italic", False), ctx, 0))
        f = skia.Font(tf, size_px)
        f.setEdging(skia.Font.Edging.kAntiAlias)
        f.setSubpixel(True)
        self.font = f
        self.text = txt
        self.blob = skia.TextBlob.MakeFromString(txt, f)
        w = f.measureText(txt)
        m = f.getMetrics()
        asc, desc = m.fAscent, m.fDescent  # asc negative
        ha, va = alignment(elem.get("alignment"), ctx)
        pos = elem.get("position")
        ox, oy = position_px(pos, ctx, view, size_px)
        ax = anchor[0] + ox + group_offset[0]
        ay = anchor[1] - oy - group_offset[1]  # N-YAXIS: position y points up
        x = {"left": ax, "center": ax - w / 2, "right": ax - w}[ha]          # N-ALIGN
        base = {"top": ay - asc, "middle": ay - (asc + desc) / 2, "bottom": ay - desc}[va]
        self.x, self.y = x, base
        self.rgb = parse_color(font.get("color", "black"), ctx) or (0, 0, 0)
        self.opacity = num(font.get("opacity", 1), ctx, 0.0) * num(elem.get("opacity", 1), ctx, 0.0)
        ol = font.get("outline")
        if is_expr(ol):
            ol = evaluate(ol, ctx)
        self.outline = None
        pad = 0.0
        if isinstance(ol, dict):
            osz = to_px(ol.get("size", 1), ctx, view, 0.0)  # N-OUTLINE: px
            ocol = parse_color(ol.get("color", "white"), ctx) or (1, 1, 1)
            oop = num(ol.get("opacity", 1), ctx, 0.0)
            if osz > 0:
                self.outline = (osz, ocol, oop)
                pad = osz
        self.box = (x - pad, base + asc - pad, x + w + pad, base + desc + pad)
        self.ok = True

    def draw(self, canvas):
        if not self.ok:
            return
        if self.outline:
            osz, ocol, oop = self.outline
            p = skia.Paint()
            p.setAntiAlias(True)
            p.setStyle(skia.Paint.kStroke_Style)
            p.setStrokeWidth(2 * osz)  # extends `size` outward from the contours
            p.setStrokeJoin(skia.Paint.kRound_Join)
            p.setColor4f(skcolor(ocol, oop * num_or1(self.opacity_group)))
            canvas.drawTextBlob(self.blob, self.x, self.y, p)
        p = skia.Paint()
        p.setAntiAlias(True)
        p.setColor4f(skcolor(self.rgb, self.opacity))
        canvas.drawTextBlob(self.blob, self.x, self.y, p)

    opacity_group = 1.0


def num_or1(v):
    return 1.0 if v is None else v


def alignment(al, ctx):
    ha, va = "center", "middle"  # N-ALIGNDEF
    if al is None:
        return ha, va
    if is_expr(al):
        al = evaluate(al, ctx)
    if isinstance(al, list):
        ha, va = evaluate(al[0], ctx), evaluate(al[1], ctx)
    elif isinstance(al, dict):
        for k in ("hAlignment", "horzAlignment", "horizontal"):
            if k in al:
                ha = evaluate(al[k], ctx)
        for k in ("vAlignment", "vertAlignment", "vertical"):
            if k in al:
                va = evaluate(al[k], ctx)
    return ha or "center", va or "middle"


def position_px(pos, ctx, view, em_px=None):
    if pos is None:
        return 0.0, 0.0
    if is_expr(pos):
        pos = evaluate(pos, ctx)
    if isinstance(pos, list):
        x, y = pos[0], pos[1]
    else:
        x, y = pos.get("x", 0), pos.get("y", 0)
    return to_px(x, ctx, view, 0.0, em_px), to_px(y, ctx, view, 0.0, em_px)


# ----------------------------- images ------------------------------------
_IMG = {}


def load_image(case_dir, res, ctx):
    if is_expr(res):
        res = evaluate(res, ctx)
    path = evaluate(res.get("path"), ctx) if res.get("path") is not None else None
    # N-RESOURCE: the local `path` is used, relative to the style file's folder
    if path is None:
        uri = res.get("uri") or res.get("url")
        uri = evaluate(uri, ctx) if uri is not None else None
        if uri and not uri.startswith("http"):
            path = uri
    if path is None:
        raise FileNotFoundError("image resource without a local path: %r" % (res,))
    fn = os.path.normpath(os.path.join(case_dir, path))
    if fn not in _IMG:
        _IMG[fn] = np.asarray(PILImage.open(fn).convert("RGBA"), dtype=np.float64) / 255.0
    return _IMG[fn]


def draw_image(canvas, elem, ctx, view, anchor, case_dir, opacity, goff):
    arr = load_image(case_dir, elem["image"], ctx)
    h, w = arr.shape[:2]
    tint = parse_color(elem.get("tint", "white"), ctx) or (1, 1, 1)
    btint = parse_color(elem.get("blackTint", "black"), ctx) or (0, 0, 0)
    rgb = arr[..., :3]
    out = np.empty_like(arr)
    for i in range(3):  # /req/vector/image: tint*v + blackTint*(1-v)
        out[..., i] = tint[i] * rgb[..., i] + btint[i] * (1 - rgb[..., i])
    out[..., 3] = arr[..., 3] * opacity
    hs = elem.get("hotSpot", [0.5, 0.5])
    if isinstance(hs, dict) and not is_expr(hs):
        hs = [hs.get("x", 0.5), hs.get("y", 0.5)]
    hx = hotspot_coord(hs[0], ctx, view, w)
    hy = hotspot_coord(hs[1], ctx, view, h)
    ox, oy = position_px(elem.get("position"), ctx, view)
    x = anchor[0] + ox + goff[0] - hx
    y = anchor[1] - oy - goff[1] - hy
    x, y = round(x), round(y)  # N-IMAGESNAP
    img8 = np.clip(np.round(out * 255), 0, 255).astype(np.uint8)
    sk = skia.Image.fromarray(np.ascontiguousarray(img8), colorType=skia.kRGBA_8888_ColorType,
                              alphaType=skia.kUnpremul_AlphaType)
    canvas.drawImage(sk, x, y)


def hotspot_coord(v, ctx, view, size):
    # N-HOTSPOT: pc = percent of the image size, unitless = fraction of the image
    # size (as in the default { 0.5, 0.5 }), other units = distance from the
    # top-left corner of the image, y downwards.
    if isinstance(v, dict) and not is_expr(v):
        if "pc" in v:
            return num(v["pc"], ctx, 0.0) / 100.0 * size
        return to_px(v, ctx, view, 0.0)
    return num(v, ctx, 0.5) * size


# ----------------------------- markers -----------------------------------


def marker_elements(marker, ctx):
    """Return (elements, group_opacity, group_offset) or None."""
    if marker is None:
        return None
    if is_expr(marker):
        marker = evaluate(marker, ctx)
        if marker is None:
            return None
    if not isinstance(marker, dict):
        return None
    els = marker.get("elements", DEFAULT_MARKER["elements"])
    if is_expr(els):
        els = evaluate(els, ctx)
    if not els:
        return None
    return [e for e in els if e is not None], num(marker.get("opacity", 1), ctx, 0.0), marker.get("position")


def draw_graphic(canvas, elem, ctx, view, anchor, case_dir, gop, goff):
    t = elem.get("type")
    op = gop * num(elem.get("opacity", 1), ctx, 0.0)
    if t == "Dot":
        st = elem.get("stroke") if isinstance(elem.get("stroke"), dict) else {}
        size = elem.get("size", st.get("width", DEFAULT_DOT["size"]))
        col = elem.get("color", st.get("color", DEFAULT_DOT["color"]))
        d = to_px(size, ctx, view, 0.0)
        rgb = parse_color(col, ctx) or (0, 0, 0)
        op *= num(st.get("opacity", 1), ctx, 0.0)
        ox, oy = position_px(elem.get("position"), ctx, view)
        if d > 0 and op > 0:  # N-NEGSIZE
            canvas.drawCircle(anchor[0] + ox + goff[0], anchor[1] - oy - goff[1], d / 2, fill_paint(rgb, op))
    elif t == "Image":
        draw_image(canvas, elem, ctx, view, anchor, case_dir, op, goff)
    elif t == "Text":
        tl = TextLayout(elem, ctx, view, anchor, goff)
        if tl.ok:
            tl.opacity *= gop
            tl.opacity_group = gop
            tl.draw(canvas)
    else:
        raise NotImplementedError("graphic type %r" % t)


# --------------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------------


def sample_band(hdr, arr, view):
    """Resample a band to the output pixel grid by bilinear interpolation
    between cell centres (N-RESAMPLE). Pixels outside the grid are NaN."""
    ncols, nrows = int(hdr["ncols"]), int(hdr["nrows"])
    cs = hdr["cellsize"]
    xll = hdr.get("xllcorner", hdr.get("xllcenter", 0) - cs / 2)
    yll = hdr.get("yllcorner", hdr.get("yllcenter", 0) - cs / 2)
    ytop = yll + nrows * cs
    xs = view.minx + (np.arange(view.W) + 0.5) * view.resx
    ys = view.maxy - (np.arange(view.H) + 0.5) * view.resy
    fx = (xs - xll) / cs - 0.5
    fy = (ytop - ys) / cs - 0.5
    inside_x = (xs >= xll) & (xs <= xll + ncols * cs)
    inside_y = (ys >= yll) & (ys <= ytop)
    fx = np.clip(fx, 0, ncols - 1)
    fy = np.clip(fy, 0, nrows - 1)
    x0 = np.floor(fx).astype(int)
    y0 = np.floor(fy).astype(int)
    x1 = np.minimum(x0 + 1, ncols - 1)
    y1 = np.minimum(y0 + 1, nrows - 1)
    tx = (fx - x0)[None, :]
    ty = (fy - y0)[:, None]
    a = arr[y0][:, x0]
    b = arr[y0][:, x1]
    c = arr[y1][:, x0]
    d = arr[y1][:, x1]
    out = (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty
    mask = inside_y[:, None] & inside_x[None, :]
    return np.where(mask, out, np.nan)


def map_interp(entries, v, ctx, kind):
    """colorMap / opacityMap: exact at entries, linear between the two
    closest entries, clamped outside (N-MAPINTERP)."""
    pts = []
    for e in entries:
        if isinstance(e, dict):
            val, out = e.get("value"), e.get("color" if kind == "color" else "opacity")
        else:
            val, out = e[0], e[1]
        val = num(val, ctx, 0.0)
        if kind == "color":
            out = parse_color(out, ctx)
        else:
            out = num(out, ctx, 0.0)
        pts.append((val, out))
    pts.sort(key=lambda p: p[0])
    xs = np.array([p[0] for p in pts])
    if kind == "color":
        return np.stack([np.interp(v, xs, np.array([p[1][i] for p in pts])) for i in range(3)], axis=-1)
    return np.interp(v, xs, np.array([p[1] for p in pts]))


def render_coverage(canvas, layer, sym, ctx, view):
    vis = sym.get("visibility", True)
    vis = evaluate(vis, ctx)
    if vis is None or (not isinstance(vis, np.ndarray) and not vis):
        return
    fields = list(ctx.props.keys())
    if "singleChannel" in sym:
        single = evaluate(sym["singleChannel"], ctx)
    elif len(fields) == 1:
        single = ctx.props[fields[0]]
    else:
        single = None
    H, W = view.H, view.W
    nanmask = np.zeros((H, W), bool)
    for f in fields:
        nanmask |= np.isnan(ctx.props[f])
    if sym.get("colorMap") is not None and single is not None:
        rgb = map_interp(evaluate(sym["colorMap"], ctx) if is_expr(sym["colorMap"]) else sym["colorMap"],
                         single, ctx, "color")
    elif "colorChannels" in sym or len(fields) >= 3:
        cc = sym.get("colorChannels", {"r": {"property": fields[0]}, "g": {"property": fields[1]},
                                        "b": {"property": fields[2]}})
        if isinstance(cc, list):
            cc = dict(zip("rgb", cc))
        rgb = np.stack([np.broadcast_to(np.asarray(evaluate(cc[k], ctx), float), (H, W)) for k in "rgb"], -1)
    else:
        rgb = np.repeat(np.asarray(single, float)[..., None], 3, -1)
    rgb = np.clip(np.nan_to_num(rgb), 0, 1)
    alpha = np.broadcast_to(np.asarray(num(sym.get("alphaChannel", 1), ctx, 0.0), float), (H, W)).copy()
    if sym.get("opacityMap") is not None and single is not None:
        alpha = alpha * map_interp(sym["opacityMap"], single, ctx, "opacity")  # N-ALPHACOMBINE
    hs = sym.get("hillShading")
    if is_expr(hs):
        hs = evaluate(hs, ctx)
    if isinstance(hs, dict) and single is not None:
        shade = hill_shade(np.asarray(single, float), hs, ctx, view)
        if hs.get("colorMap") is not None:
            rgb = map_interp(hs["colorMap"], shade, ctx, "color")
        else:
            rgb = rgb * shade[..., None]
        if hs.get("opacityMap") is not None:
            alpha = alpha * map_interp(hs["opacityMap"], shade, ctx, "opacity")
    op = num(sym.get("opacity", 1), ctx, 0.0)
    alpha = np.clip(alpha * op, 0, 1)
    if isinstance(vis, np.ndarray):
        alpha = np.where(vis, alpha, 0)
    alpha = np.where(nanmask, 0, alpha)  # N-NODATA
    img = np.zeros((H, W, 4), np.uint8)
    img[..., :3] = np.clip(np.round(rgb * 255), 0, 255).astype(np.uint8)
    img[..., 3] = np.clip(np.round(alpha * 255), 0, 255).astype(np.uint8)
    sk = skia.Image.fromarray(np.ascontiguousarray(img), colorType=skia.kRGBA_8888_ColorType,
                              alphaType=skia.kUnpremul_AlphaType)
    canvas.drawImage(sk, 0, 0)


def hill_shade(z, hs, ctx, view):
    factor = num(hs.get("factor", 1), ctx, 1.0)  # N-HSDEF
    sun = hs.get("sun") or {}

    def angle(a, d):
        if a is None:
            return d
        if isinstance(a, dict) and not is_expr(a):
            if "rad" in a:
                return math.degrees(num(a["rad"], ctx, 0.0))
            if "deg" in a:
                return num(a["deg"], ctx, 0.0)
        return num(a, ctx, d)

    az = math.radians(angle(sun.get("azimuth"), 315.0))
    el = math.radians(angle(sun.get("elevation"), 45.0))
    zf = np.where(np.isnan(z), np.nanmean(z), z)
    # N-HSGRAD: central differences between neighbouring rendered samples
    # (one-sided at the image edge); rows go southwards.
    dz_drow, dz_dcol = np.gradient(zf, view.resy, view.resx)
    dzdx = dz_dcol            # east
    dzdy = -dz_drow           # north
    nx, ny, nz = -factor * dzdx, -factor * dzdy, np.ones_like(zf)
    nlen = np.sqrt(nx * nx + ny * ny + nz * nz)
    sx, sy, sz = math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)
    shade = (nx * sx + ny * sy + nz * sz) / nlen
    return np.clip(shade, 0, 1)


# --------------------------------------------------------------------------
# Map rendering
# --------------------------------------------------------------------------


class Item:
    pass


def render_case(case):
    case_dir = os.path.join(CASES, case)
    style = json.load(open(os.path.join(case_dir, "style.cs.json"), encoding="utf-8"))
    rules = load_rules(style, case_dir)
    outs = []
    for fn in sorted(os.listdir(case_dir)):
        m = re.match(r"view-(\d+)\.json$", fn)
        if not m:
            continue
        vj = json.load(open(os.path.join(case_dir, fn)))
        img = render_view(rules, vj, case_dir)
        out = os.path.join(OUT, "%s-%s.png" % (case, m.group(1)))
        img.save(out)
        outs.append(out)
    return outs


def load_rules(style, case_dir):
    rules = []
    inc = style.get("$include")
    if inc:
        for p in ([inc] if isinstance(inc, str) else inc):
            sub = json.load(open(os.path.join(case_dir, p), encoding="utf-8"))
            rules.extend(load_rules(sub, case_dir))
    rules.extend(style.get("stylingRules", []))
    return rules


def render_view(rules, vj, case_dir):
    view = View(vj)
    surface = skia.Surface(view.W, view.H)
    canvas = surface.getCanvas()
    bg = parse_color(vj.get("background", "white"), None)
    canvas.clear(skcolor(bg, 1.0))

    items = []
    order = 0
    for li, layer_id in enumerate(vj["layers"]):
        layer = load_layer(case_dir, layer_id)
        sysv = view.sys(layer_id, layer["type"])
        if layer["type"] == "coverage":
            props = {b: sample_band(h, a, view) for b, (h, a) in layer["bands"].items()}
            ctx = Context(props, sysv)
            sym = resolve(rules, ctx)
            it = Item()
            it.kind, it.layer, it.ctx, it.sym, it.order = "coverage", layer, ctx, sym, order
            it.z = num(sym.get("zOrder", 1), ctx, 0.0)
            order += 1
            items.append(it)
            continue
        feats = layer["data"]["features"]
        dims = set()
        for f in feats:
            dims.add({"point": 0, "line": 1, "polygon": 2}[geom_parts(f["geometry"])[0]])
        sysv["dataLayer.featuresGeometryDimensions"] = dims.pop() if len(dims) == 1 else None
        for fi, f in enumerate(feats):
            kind, parts = geom_parts(f["geometry"])
            s2 = dict(sysv)
            s2["feature.id"] = f.get("id", fi)
            s2["feature.geometryDimensions"] = {"point": 0, "line": 1, "polygon": 2}[kind]
            ctx = Context(f.get("properties") or {}, s2)
            sym = resolve(rules, ctx)
            vis = evaluate(sym.get("visibility", True), ctx)
            if vis is not True:  # null -> false (/req/parameter-values/null)
                continue
            it = Item()
            it.kind, it.geom, it.parts, it.ctx, it.sym, it.order = kind, f["geometry"], parts, ctx, sym, order
            it.z = num(sym.get("zOrder", 1), ctx, 0.0)
            order += 1
            items.append(it)

    labels = []
    # /req/core/z-order: increasing zOrder; equal zOrder keeps layer then feature order (N-ZORDER)
    for z in sorted(set(it.z for it in items)):
        group = [it for it in items if it.z == z]
        for it in group:
            if it.kind in ("line", "polygon"):
                it.path = make_path(view, it.kind, it.parts)
        # casing sub-pass (/req/casing/casing, 4th part)
        for it in group:
            if it.kind in ("line", "polygon"):
                draw_casing(canvas, it, view)
        # main pass
        for it in group:
            if it.kind == "coverage":
                render_coverage(canvas, it.layer, it.sym, it.ctx, view)
            else:
                draw_feature(canvas, it, view, case_dir)
            lab = get_obj(it.sym, "label", it.ctx, None) if it.kind != "coverage" else None
            if lab:
                labels.append((it, lab))
        # centre-line sub-pass (N-CENTER)
        for it in group:
            if it.kind in ("line", "polygon"):
                draw_center(canvas, it, view)

    place_labels(canvas, labels, view)

    arr = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    img = PILImage.fromarray(arr[..., :3].copy(), "RGB")
    assert img.size == (view.W, view.H)
    return img


def stroke_obj(it):
    st = get_obj(it.sym, "stroke", it.ctx, DEFAULT_STROKE)
    return st if isinstance(st, dict) else None


def draw_casing(canvas, it, view):
    st = stroke_obj(it)
    if not st or st.get("casing") is None:
        return
    main = styling_values(st, it.ctx, view)
    cas = styling_values(st["casing"], it.ctx, view, {"color": "black", "opacity": 1, "width": {"px": 1}})  # N-CASINGDEF
    if cas is None:
        return
    rgb, op, w = cas
    total = (main[2] if main else 0.0) + 2 * w
    op_sym = num(it.sym.get("opacity", 1), it.ctx, 0.0)
    draw_stroke(canvas, it.path, (rgb, op * op_sym, total))


def draw_center(canvas, it, view):
    st = stroke_obj(it)
    if not st:
        return
    c = st.get("center", st.get("centerLine"))  # N-CENTERNAME
    if c is None:
        return
    cv = styling_values(c, it.ctx, view, {"color": "black", "opacity": 1, "width": {"px": 1}})
    if cv is None:
        return
    op_sym = num(it.sym.get("opacity", 1), it.ctx, 0.0)
    draw_stroke(canvas, it.path, (cv[0], cv[1] * op_sym, cv[2]))


def draw_feature(canvas, it, view, case_dir):
    ctx, sym = it.ctx, it.sym
    op = num(sym.get("opacity", 1), ctx, 0.0)
    if op <= 0:
        return
    grouped = op < 1
    if grouped:  # /rec/core/opacity-together: fill, stroke and marker in one group
        p = skia.Paint()
        p.setAlphaf(op)
        canvas.saveLayer(None, p)
    if it.kind == "polygon":
        draw_fill(canvas, it.path, get_obj(sym, "fill", ctx, DEFAULT_FILL), ctx, view)
    if it.kind in ("line", "polygon"):
        st = stroke_obj(it)
        if st:
            stv = styling_values(st, ctx, view)
            draw_stroke(canvas, it.path, stv, dash_of(st, ctx, view))
    mk = marker_elements(get_obj(sym, "marker", ctx, DEFAULT_MARKER), ctx)
    if mk:
        els, gop, gpos = mk
        goff = position_px(gpos, ctx, view)
        for a in marker_anchors(view, it.kind, it.parts):
            for e in els:
                draw_graphic(canvas, e, ctx, view, a, case_dir, gop, goff)
    if grouped:
        canvas.restore()


# ----------------------------- labels ------------------------------------


def line_candidates(view, parts, step=4.0):
    out = []
    for line in parts:
        p = view.to_px(line)
        acc = 0.0
        nxt = 0.0
        for i in range(len(p) - 1):
            a, b = p[i], p[i + 1]
            seg = float(np.hypot(*(b - a)))
            while seg > 0 and nxt <= acc + seg:
                t = (nxt - acc) / seg
                out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
                nxt += step
            acc += seg
    return out


def boxes_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def place_labels(canvas, labels, view):
    """/req/labels/*: labels in a separate pass on top; higher priority first;
    labels overlapping an already placed label are omitted (N-LABELS)."""
    cands = []
    for it, lab in labels:
        ctx = it.ctx
        if not isinstance(lab, dict):
            continue
        els = lab.get("elements") or []
        if not els:
            continue
        pl = lab.get("placement") or {}
        if is_expr(pl):
            pl = evaluate(pl, ctx)
        prio = num(pl.get("priority", 0), ctx, 0.0)  # null -> 0 (/req/parameter-values/null)
        minsp = to_px(pl.get("minSpacing"), ctx, view, None) if pl.get("minSpacing") is not None else None
        gop = num(lab.get("opacity", 1), ctx, 0.0)
        goff = position_px(lab.get("position"), ctx, view)
        cands.append((-(prio if prio is not None else 0.0), it.order, it, els, minsp, gop, goff))
    cands.sort(key=lambda c: (c[0], c[1]))
    placed = []          # boxes
    placed_text = []     # (key, x, y)
    for _, _, it, els, minsp, gop, goff in cands:
        ctx = it.ctx
        if it.kind == "point":
            anchors = marker_anchors(view, "point", it.parts)
        elif it.kind == "polygon":
            anchors = marker_anchors(view, "polygon", it.parts)
        else:
            if minsp is None:  # N-LINELABEL: one label at the middle of the line
                c = line_candidates(view, it.parts)
                anchors = [c[len(c) // 2]] if c else []
            else:
                anchors = line_candidates(view, it.parts)
        for a in anchors:
            layouts = []
            for e in els:
                if e.get("type") == "Text":
                    tl = TextLayout(e, ctx, view, a, goff)
                    if tl.ok:
                        tl.opacity *= gop
                        tl.opacity_group = gop
                        layouts.append(tl)
            if not layouts:
                continue
            key = tuple(tl.text for tl in layouts)
            box = (min(t.box[0] for t in layouts), min(t.box[1] for t in layouts),
                   max(t.box[2] for t in layouts), max(t.box[3] for t in layouts))
            if box[0] < 0 or box[1] < 0 or box[2] > view.W or box[3] > view.H:
                continue  # N-LABELINSIDE
            if any(boxes_overlap(box, b) for b in placed):
                continue
            if minsp is not None and any(k == key and math.hypot(x - a[0], y - a[1]) < minsp
                                         for k, x, y in placed_text):
                continue
            placed.append(box)
            placed_text.append((key, a[0], a[1]))
            for tl in layouts:
                tl.draw(canvas)


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    cases = argv or sorted(d for d in os.listdir(CASES)
                           if os.path.exists(os.path.join(CASES, d, "style.cs.json")))
    ok, failed = [], []
    for c in cases:
        try:
            outs = render_case(c)
            ok.extend(outs)
            print("rendered", c, [os.path.basename(o) for o in outs])
        except Exception as ex:  # report and continue
            import traceback
            traceback.print_exc()
            failed.append((c, repr(ex)))
    print("%d images, %d failed cases" % (len(ok), len(failed)))
    for c, e in failed:
        print("FAILED", c, e)


if __name__ == "__main__":
    main(sys.argv[1:])
