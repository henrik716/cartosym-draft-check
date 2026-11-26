"""Renderer written only from the CartoSym 2.0 Part 1 draft text in spec/.

Usage: render.py [case-name ...]   (default: all cases)
Environment: PASSMODE=every (default) | first   -- see notes.md choice C1
"""
import glob
import io
import json
import math
import os
import re
import sys

import numpy as np
import resvg_py
from PIL import Image, ImageDraw, ImageFont
from shapely.affinity import affine_transform
from shapely.geometry import (GeometryCollection, LinearRing, LineString,
                              MultiLineString, MultiPoint, MultiPolygon, Point,
                              Polygon, shape)
from shapely.ops import substring

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 4  # supersampling factor for geometry
PASSMODE = os.environ.get("PASSMODE", "every")

# ---------------------------------------------------------------- colors


def load_colors():
    tbl = {}
    path = os.path.join(ROOT, "spec", "1-core", "sections", "clause_16_cscss.adoc")
    for line in open(path, encoding="utf8"):
        m = re.match(r"^\s*\|?\s*(\w+)\s*\|\s*`0x([0-9a-fA-F]{6})`", line)
        if m:
            h = m.group(2)
            tbl[m.group(1).lower()] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return tbl


COLORS = load_colors()


def color(c, default=(0, 0, 0)):
    if c is None:
        return default
    if isinstance(c, (list, tuple)) and len(c) == 3:
        return tuple(float(x) for x in c)
    if isinstance(c, dict) and "r" in c:
        return (float(c.get("r", 0)), float(c.get("g", 0)), float(c.get("b", 0)))
    if isinstance(c, str):
        if c.startswith("#") and len(c) == 7:
            return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
        return COLORS.get(c.lower(), default)
    return default


# ---------------------------------------------------------------- expressions
class Ctx:
    def __init__(self, props, sysv):
        self.props = props
        self.sys = sysv


def get_prop(props, name):
    if name in props:
        return props[name]
    cur = props
    for part in name.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


SYS_ALIAS = {"viz.pass": "visualization.pass", "viz.sd": "visualization.scaleDenominator",
             "viz": "visualization", "dataLayer.id": "dataLayer.identifier"}


def is_expr(x):
    return isinstance(x, dict) and ("op" in x or "property" in x or "sysId" in x)


def ev(x, ctx):
    if isinstance(x, dict):
        if "property" in x:
            return get_prop(ctx.props, x["property"])
        if "sysId" in x:
            k = x["sysId"]
            k = SYS_ALIAS.get(k, k)
            return ctx.sys.get(k)
        if "op" in x:
            return apply_op(x["op"], x.get("args", []), ctx)
        return x
    if isinstance(x, list):
        return [ev(i, ctx) for i in x]
    return x


def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def like(s, pat):
    rx = "^" + "".join(".*" if c == "%" else "." if c == "_" else re.escape(c) for c in pat) + "$"
    return re.match(rx, s, re.S) is not None


def apply_op(op, args, ctx):
    if op == "?:":
        c = ev(args[0], ctx)
        return ev(args[1], ctx) if c is True else ev(args[2], ctx)
    if op == "and":
        vals = [ev(a, ctx) for a in args]
        if any(v is False for v in vals):
            return False
        return None if any(v is None for v in vals) else True
    if op == "or":
        vals = [ev(a, ctx) for a in args]
        if any(v is True for v in vals):
            return True
        return None if any(v is None for v in vals) else False
    a = [ev(i, ctx) for i in args]
    if op == "not":
        return None if a[0] is None else (not a[0])
    if op == "isNull":
        return a[0] is None
    if op in ("=", "<>", "<", ">", "<=", ">="):
        if a[0] is None or a[1] is None:
            return None
        x, y = a
        try:
            return {"=": x == y, "<>": x != y, "<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y}[op]
        except TypeError:
            return None
    if op == "in":
        if a[0] is None:
            return None
        return a[0] in a[1]
    if op == "between":
        if None in a:
            return None
        return a[1] <= a[0] <= a[2]
    if op == "like":
        if a[0] is None or a[1] is None:
            return None
        return like(str(a[0]), a[1])
    if None in a:
        return None
    if op == "abs":
        return abs(a[0])
    if op == "+":
        return a[0] + a[1]
    if op == "-":
        return a[0] - a[1] if len(a) > 1 else -a[0]
    if op == "*":
        return a[0] * a[1]
    if op == "/":
        return a[0] / a[1] if a[1] else None
    if op == "%":
        return a[0] % a[1]
    if op == "^":
        return a[0] ** a[1]
    raise ValueError("unsupported op " + op)


def ev_deep(x, ctx):
    if is_expr(x):
        return ev(x, ctx)
    if isinstance(x, dict):
        return {k: ev_deep(v, ctx) for k, v in x.items()}
    if isinstance(x, list):
        return [ev_deep(v, ctx) for v in x]
    return x


# ---------------------------------------------------------------- style
def merge(a, b):
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and v.get("alter") is True and isinstance(out.get(k), dict):
            out[k] = merge(out[k], {kk: vv for kk, vv in v.items() if kk != "alter"})
        else:
            out[k] = v
    return out


def apply_rules(rules, ctx, sym):
    for r in rules:
        sel = r.get("selector")
        if sel is not None and ev(sel, ctx) is not True:
            continue
        if r.get("symbolizer"):
            sym = merge(sym, r["symbolizer"])
        if r.get("nestedRules"):
            sym = apply_rules(r["nestedRules"], ctx, sym)
    return sym


def scan_passes(rules, found):
    def walk(x):
        if isinstance(x, dict):
            if x.get("op") == "=" and len(x.get("args", [])) == 2:
                a, b = x["args"]
                for p, q in ((a, b), (b, a)):
                    if isinstance(p, dict) and p.get("sysId") in ("viz.pass", "visualization.pass", "feature.pass") \
                            and num(q):
                        found.setdefault(p["sysId"].split(".")[0].replace("visualization", "viz"), set()).add(int(q))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(rules)


# ---------------------------------------------------------------- units
class Units:
    def __init__(self, view):
        self.pix_mm = view.get("pixelSize_mm", 0.28)
        self.ground = self.pix_mm * view["scaleDenominator"] / 1000.0  # metres per pixel

    def px(self, v, default=0.0):
        if v is None:
            return default
        if num(v):
            return float(v)
        if isinstance(v, dict):
            for k, f in (("px", lambda x: x), ("m", lambda x: x / self.ground),
                         ("ft", lambda x: x * 0.3048 / self.ground),
                         ("mm", lambda x: x / self.pix_mm), ("cm", lambda x: x * 10 / self.pix_mm),
                         ("in", lambda x: x * 25.4 / self.pix_mm), ("inch", lambda x: x * 25.4 / self.pix_mm),
                         ("pt", lambda x: x * 25.4 / 72 / self.pix_mm)):
                if k in v:
                    return float(f(v[k]))
        return default

    def pt_px(self, pt):
        return pt * 25.4 / 72.0 / self.pix_mm


# ---------------------------------------------------------------- canvas
class Layer:
    def __init__(self, W, H, bg=None):
        self.W, self.H = W, H
        self.P = np.zeros((H, W, 3), np.float32)
        self.A = np.zeros((H, W), np.float32)
        if bg is not None:
            self.P[:] = np.array(bg, np.float32) / 255.0
            self.A[:] = 1.0

    def paint(self, mask, col, alpha=1.0):
        a = mask * alpha
        c = np.array(col, np.float32) / 255.0
        self.P = c * a[..., None] + self.P * (1 - a[..., None])
        self.A = a + self.A * (1 - a)

    def paint_premult(self, prem, a):
        self.P = prem + self.P * (1 - a[..., None])
        self.A = a + self.A * (1 - a)

    def composite(self, other, opacity):
        a = other.A * opacity
        self.P = other.P * opacity + self.P * (1 - a[..., None])
        self.A = a + self.A * (1 - a)

    def to_image(self):
        a = np.maximum(self.A, 1e-6)[..., None]
        rgb = np.clip(self.P / a, 0, 1)
        return Image.fromarray((rgb * 255 + 0.5).astype(np.uint8), "RGB")


def polys_of(g):
    if g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if hasattr(g, "geoms"):
        out = []
        for s in g.geoms:
            out += polys_of(s)
        return out
    return []


def raster_S(geom, W, H):
    """Supersampled uint8 mask (H*S, W*S) of the polygonal geometry (pixel coords)."""
    img = Image.new("L", (W * S, H * S), 0)
    d = ImageDraw.Draw(img)
    for p in polys_of(geom):
        minx, miny, maxx, maxy = p.bounds
        if maxx < 0 or maxy < 0 or minx > W or miny > H:
            continue
        d.polygon([(x * S, y * S) for x, y in p.exterior.coords], fill=255)
        for ring in p.interiors:
            d.polygon([(x * S, y * S) for x, y in ring.coords], fill=0)
    return np.asarray(img)


def down(arrS, W, H):
    return arrS.reshape(H, S, W, S).astype(np.float32).mean(axis=(1, 3)) / 255.0


def raster(geom, W, H):
    # restrict work to the bounding box for speed
    polys = polys_of(geom)
    if not polys:
        return np.zeros((H, W), np.float32)
    b = [p.bounds for p in polys]
    x0 = max(0, int(math.floor(min(i[0] for i in b))))
    y0 = max(0, int(math.floor(min(i[1] for i in b))))
    x1 = min(W, int(math.ceil(max(i[2] for i in b))) + 1)
    y1 = min(H, int(math.ceil(max(i[3] for i in b))) + 1)
    out = np.zeros((H, W), np.float32)
    if x1 <= x0 or y1 <= y0:
        return out
    w, h = x1 - x0, y1 - y0
    img = Image.new("L", (w * S, h * S), 0)
    d = ImageDraw.Draw(img)
    for p in polys:
        d.polygon([((x - x0) * S, (y - y0) * S) for x, y in p.exterior.coords], fill=255)
        for ring in p.interiors:
            d.polygon([((x - x0) * S, (y - y0) * S) for x, y in ring.coords], fill=0)
    out[y0:y1, x0:x1] = down(np.asarray(img), w, h)
    return out


# ---------------------------------------------------------------- geometry helpers
def lines_of(g):
    if g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    if isinstance(g, Polygon):
        return [LinearRing(g.exterior.coords)] + [LinearRing(r.coords) for r in g.interiors]
    if hasattr(g, "geoms"):
        out = []
        for s in g.geoms:
            out += lines_of(s)
        return out
    return []


def vertices_of(g):
    if g.is_empty:
        return []
    if isinstance(g, Point):
        return [(g.x, g.y)]
    if isinstance(g, LineString):
        return list(g.coords)
    if isinstance(g, Polygon):
        c = g.centroid
        return [(c.x, c.y)]
    out = []
    for s in g.geoms:
        out += vertices_of(s)
    return out


def dash_pieces(line, pattern, offset):
    total = sum(pattern)
    if total <= 0:
        return [line]
    L = line.length
    pieces = []
    # position inside the pattern at the start of the line
    pos = -(offset % total)
    i = 0
    while pos < L:
        seg = pattern[i % len(pattern)]
        if i % 2 == 0 and seg > 0:
            s, e = max(pos, 0.0), min(pos + seg, L)
            if e > s:
                pieces.append(substring(line, s, e))
        pos += seg
        i += 1
        if i > 200000:
            break
    return pieces


def buffer_line(line, half, cap, join):
    cs = {"round": "round", "butt": "flat", "square": "square"}.get(cap, "round")
    js = {"round": "round", "miter": "mitre", "bevel": "bevel"}.get(join, "round")
    if isinstance(line, LinearRing):
        line = LineString(line.coords)
        return line.buffer(half, cap_style="round", join_style=js, mitre_limit=4.0)
    return line.buffer(half, cap_style=cs, join_style=js, mitre_limit=4.0)


# ---------------------------------------------------------------- svg tiles
_tile_cache = {}


def svg_size(path):
    txt = open(path, encoding="utf8").read(4000)
    m = re.search(r"<svg\b[^>]*>", txt, re.S)
    head = m.group(0)
    w = float(re.search(r'\swidth="([\d.]+)', head).group(1))
    h = float(re.search(r'\sheight="([\d.]+)', head).group(1))
    return w, h


def svg_rgba(path, factor):
    """Rasterise the SVG at S * factor times its own size; returns float RGBA premult arrays."""
    key = (path, factor)
    if key in _tile_cache:
        return _tile_cache[key]
    w, h = svg_size(path)
    tw, th = max(1, int(round(w * factor * S))), max(1, int(round(h * factor * S)))
    png = resvg_py.svg_to_bytes(svg_path=path, width=tw, height=th, skip_system_fonts=True)
    im = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    arr = np.asarray(im).astype(np.float32) / 255.0
    _tile_cache[key] = arr
    return arr


# ---------------------------------------------------------------- text
_font_cache = {}


def get_font(size_px):
    k = round(size_px * 3)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.load_default(size=k)  # bundled with Pillow
    return _font_cache[k]


def text_mask(txt, size_px, bold, W, H, x, y, halign, valign):
    """Returns (mask HxW float, bbox) of text drawn with anchor point (x, y) in pixels."""
    T = 3
    font = ImageFont.load_default(size=int(round(size_px * T)))
    img = Image.new("L", (W * T, H * T), 0)
    d = ImageDraw.Draw(img)
    anchor = {"left": "l", "center": "m", "right": "r"}.get(halign, "l") + \
        {"top": "a", "middle": "m", "bottom": "d"}.get(valign, "a")
    d.text((x * T, y * T), txt, fill=255, font=font, anchor=anchor, stroke_width=1 if bold else 0, stroke_fill=255)
    bb = d.textbbox((x * T, y * T), txt, font=font, anchor=anchor, stroke_width=1 if bold else 0)
    arr = np.asarray(img).reshape(H, T, W, T).astype(np.float32).mean(axis=(1, 3)) / 255.0
    return arr, (bb[0] / T, bb[1] / T, bb[2] / T, bb[3] / T)


# ---------------------------------------------------------------- drawing of one item
def num_or0(v):
    return float(v) if num(v) else 0.0


def stroke_params(st, U):
    return dict(
        color=color(st.get("color"), (0, 0, 0)),
        width=U.px(st.get("width"), 1.0) if "width" in st else 1.0,
        opacity=num_or0(st["opacity"]) if "opacity" in st else 1.0,
    )


def stroke_geom(g, st, U):
    """Polygon geometry (pixel coords) covered by the main stroke."""
    sp = stroke_params(st, U)
    w = sp["width"]
    if w <= 0:
        return None
    cap = st.get("cap", "round")
    join = st.get("join", "round")
    dash = st.get("dashPattern")
    out = []
    pat = None
    if isinstance(dash, list) and dash:
        pat = [max(0.0, U.px(d)) for d in dash]
        if len(pat) % 2:
            pat = pat * 2
        if sum(pat) <= 0:
            pat = None
    off = U.px(st.get("dashOffset"), 0.0)
    for ln in lines_of(g):
        if pat:
            for pc in dash_pieces(ln, pat, off):
                if pc.length > 0:
                    out.append(buffer_line(pc, w / 2, "butt", join))
        else:
            out.append(buffer_line(ln, w / 2, cap, join))
    if not out:
        return None
    from shapely.ops import unary_union
    return unary_union(out)


def draw_dot(layer, el, cx, cy, U, W, H, opacity):
    st = el.get("stroke") or {}
    size = el["size"] if "size" in el else (st.get("width") if "width" in st else 10)
    d = U.px(size, 10.0)
    col = color(el["color"] if "color" in el else st.get("color"), (255, 255, 255))
    if d <= 0:
        return
    m = raster(Point(cx, cy).buffer(d / 2, 32), W, H)
    layer.paint(m, col, opacity)


def draw_graphic(layer, el, pt, U, W, H, opacity=1.0):
    pos = el.get("position")
    ox = oy = 0.0
    if isinstance(pos, list) and len(pos) == 2:
        ox, oy = U.px(pos[0]), U.px(pos[1])
    elif isinstance(pos, dict):
        ox, oy = U.px(pos.get("x")), U.px(pos.get("y"))
    x, y = pt[0] + ox, pt[1] + oy
    t = el.get("type", "Dot")
    if t == "Dot":
        draw_dot(layer, el, x, y, U, W, H, opacity * (num_or0(el["opacity"]) if "opacity" in el else 1))
    elif t == "Text":
        txt = el.get("text")
        txt = "" if txt is None else str(txt)
        draw_text(layer, el, txt, x, y, U, W, H)


def draw_text(layer, el, txt, x, y, U, W, H):
    font = el.get("font") or {}
    size = U.pt_px(num_or0(font.get("size", 12)))
    al = el.get("alignment")
    h, v = "left", "top"
    if isinstance(al, list) and len(al) == 2:
        h, v = al
    elif isinstance(al, dict):
        h = al.get("horzAlignment", al.get("horizontal", "left"))
        v = al.get("vertAlignment", al.get("vertical", "top"))
    m, bb = text_mask(txt, size, bool(font.get("bold")), W, H, x, y, h, v)
    layer.paint(m, color(font.get("color"), (0, 0, 0)), num_or0(font["opacity"]) if "opacity" in font else 1.0)
    return bb


def default_marker():
    return {"elements": [{"type": "Dot"}]}


def marker_elements(mk):
    if mk is None:
        return []
    if isinstance(mk, dict) and isinstance(mk.get("elements"), list):
        return mk["elements"]
    if isinstance(mk, dict) and "elements" not in mk:
        return default_marker()["elements"]
    return []


def fill_state(sym):
    f = sym.get("fill", {})
    return f


def draw_body(canvas, g, sym, U, W, H, base_dir):
    """Fill, stroke and marker of one feature portrayal, as one group."""
    op = sym.get("opacity", 1.0)
    op = num_or0(op)
    grp = Layer(W, H) if op < 1 else canvas
    dim = {Polygon: 2, MultiPolygon: 2, LineString: 1, MultiLineString: 1, Point: 0, MultiPoint: 0}.get(type(g), 2)
    # fill (polygons only)
    fl = sym.get("fill", {})
    if dim == 2 and fl is not None:
        fl = fl if isinstance(fl, dict) else {}
        fop = num_or0(fl["opacity"]) if "opacity" in fl else 1.0
        pat = fl.get("pattern")
        if isinstance(pat, dict) and pat.get("type") == "Image":
            draw_pattern_fill(grp, g, pat, fop, U, W, H, base_dir)
        elif any(k in fl for k in ("hatch", "dotpattern", "stipple")):
            pass  # not used by any case
        else:
            col = color(fl.get("color"), (255, 255, 255))
            grp.paint(raster(g, W, H), col, fop)
    # stroke
    st = sym.get("stroke", {})
    if dim >= 1 and st is not None:
        st = st if isinstance(st, dict) else {}
        sp = stroke_params(st, U)
        pat = st.get("pattern")
        if isinstance(pat, dict) and pat.get("type") == "Image":
            draw_pattern_stroke(grp, g, st, pat, U, W, H, base_dir)
        else:
            sg = stroke_geom(g, st, U)
            if sg is not None:
                grp.paint(raster(sg, W, H), sp["color"], sp["opacity"])
    # marker
    for el in marker_elements(sym.get("marker", default_marker())):
        for v in vertices_of(g):
            draw_graphic(grp, el, v, U, W, H)
    if grp is not canvas:
        canvas.composite(grp, op)


def tile_scale(pat):
    sc = (pat.get("transform") or {}).get("scaling", [1, 1])
    if num(sc):
        sc = [sc, sc]
    # choice C9: a number without unit is divided by 100 (see notes.md)
    return sc[0] / 100.0, sc[1] / 100.0


def draw_pattern_fill(layer, g, pat, fop, U, W, H, base_dir):
    path = os.path.join(base_dir, pat["image"]["path"])
    fx, fy = tile_scale(pat)
    tile = svg_rgba(path, fx)  # square scaling assumed (fx == fy)
    th, tw = tile.shape[:2]
    reps = (H * S // th + 1, W * S // tw + 1)
    big = np.tile(tile, (reps[0], reps[1], 1))[:H * S, :W * S]
    mask = raster_S(g, W, H).astype(np.float32) / 255.0
    a = big[..., 3] * mask * fop
    prem = big[..., :3] * a[..., None]
    pa = prem.reshape(H, S, W, S, 3).mean(axis=(1, 3))
    aa = a.reshape(H, S, W, S).mean(axis=(1, 3))
    layer.paint_premult(pa, aa)


def draw_pattern_stroke(layer, g, st, pat, U, W, H, base_dir):
    path = os.path.join(base_dir, pat["image"]["path"])
    fx, fy = tile_scale(pat)
    tile = svg_rgba(path, fx)
    th, tw = tile.shape[:2]
    gap = U.px(st.get("patternGap"), 10.0)
    init = U.px(st.get("patternInitialGap"), 0.0)
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    tim = Image.fromarray((tile * 255 + 0.5).astype(np.uint8), "RGBA")
    for ln in lines_of(g):
        L = ln.length
        d = init
        step = max(gap, 0.5)
        while d <= L:
            p = ln.interpolate(d)
            cx, cy = p.x * S, p.y * S
            img.alpha_composite(tim, (int(round(cx - tw / 2)), int(round(cy - th / 2)))) if \
                (0 <= cx - tw / 2 and 0 <= cy - th / 2 and cx + tw / 2 < W * S and cy + th / 2 < H * S) else None
            d += step
    arr = np.asarray(img).astype(np.float32) / 255.0
    a = arr[..., 3]
    prem = arr[..., :3] * a[..., None]
    layer.paint_premult(prem.reshape(H, S, W, S, 3).mean(axis=(1, 3)), a.reshape(H, S, W, S).mean(axis=(1, 3)))


# ---------------------------------------------------------------- main per case
def load_layer(case_dir, lid, view):
    d = json.load(open(os.path.join(case_dir, lid + ".geojson"), encoding="utf8"))
    minx, miny, maxx, maxy = view["bbox"]
    res = (maxx - minx) / view["width"]
    m = [1 / res, 0, 0, -1 / res, -minx / res, maxy / res]
    feats = []
    for f in d["features"]:
        g = affine_transform(shape(f["geometry"]), m)
        feats.append((f.get("properties") or {}, g))
    return feats


def geom_dim(g):
    return {Polygon: 2, MultiPolygon: 2, LineString: 1, MultiLineString: 1, Point: 0, MultiPoint: 0}.get(type(g), 2)


def render_case(name):
    case_dir = os.path.join(ROOT, "cases", name)
    view = json.load(open(os.path.join(case_dir, "view-1.json")))
    style = json.load(open(os.path.join(case_dir, "style.cs.json"), encoding="utf8"))
    rules = style["stylingRules"]
    W, H = view["width"], view["height"]
    U = Units(view)
    bg = color(view.get("background"), (255, 255, 255))
    canvas = Layer(W, H, bg)

    found = {}
    scan_passes(rules, found)
    vpasses = sorted({0} | found.get("viz", set()))
    fpasses = sorted({0} | found.get("feature", set()))

    layers = []
    for l in view["layers"]:
        feats = load_layer(case_dir, l["id"], view)
        dims = {geom_dim(g) for _, g in feats}
        layers.append((l["id"], l.get("type", "vector"), feats, dims.pop() if len(dims) == 1 else None))

    labels = {}
    for vp in vpasses:
        items = []
        for lid, ltype, feats, ldim in layers:
            for fi, (props, g) in enumerate(feats):
                for fp in fpasses:
                    if PASSMODE == "first" and vp != vpasses[0]:
                        pass
                    ctx = Ctx(props, {"visualization.pass": vp, "feature.pass": fp,
                                      "dataLayer.identifier": lid, "dataLayer.type": ltype,
                                      "dataLayer.featuresGeometryDimensions": ldim,
                                      "feature.geometryDimension": geom_dim(g),
                                      "visualization.scaleDenominator": view["scaleDenominator"]})
                    raw = apply_rules(rules, ctx, {})
                    if PASSMODE == "first" and vp != vpasses[0]:
                        # only symbolizers that depend on viz.pass are used after the first pass
                        ctx0 = Ctx(props, dict(ctx.sys, **{"visualization.pass": None}))
                        base = apply_rules(rules, ctx0, {})
                        if raw == base:
                            continue
                    sym = ev_deep(raw, ctx)
                    vis = sym.get("visibility", True)
                    if vis is False or vis is None and "visibility" in sym:
                        continue
                    z = sym.get("zOrder", 1)
                    z = 0 if z is None else z
                    labels[(lid, fi)] = (sym.get("label"), g, props)
                    items.append((z, len(items), lid, fi, props, g, sym))
        items.sort(key=lambda t: (t[0], t[1]))
        i = 0
        while i < len(items):
            j = i
            while j < len(items) and items[j][0] == items[i][0]:
                j += 1
            grp = items[i:j]
            # casings of all features of this zOrder first
            for _, _, lid, fi, props, g, sym in grp:
                st = sym.get("stroke", {})
                if isinstance(st, dict) and isinstance(st.get("casing"), dict) and geom_dim(g) >= 1:
                    cs = st["casing"]
                    w = U.px(st.get("width"), 1.0) if "width" in st else 1.0
                    cw = U.px(cs.get("width"), 0.0)
                    if cw > 0 and w > 0:
                        cst = {"cap": st.get("cap", "round"), "join": st.get("join", "round"),
                               "width": w + 2 * cw, "color": cs.get("color")}
                        sg = stroke_geom(g, cst, U)
                        if sg is not None:
                            op = num_or0(sym.get("opacity", 1.0)) * (num_or0(cs["opacity"]) if "opacity" in cs else 1)
                            canvas.paint(raster(sg, W, H), color(cs.get("color")), op)
            for _, _, lid, fi, props, g, sym in grp:
                draw_body(canvas, g, sym, U, W, H, case_dir)
            for _, _, lid, fi, props, g, sym in grp:
                st = sym.get("stroke", {})
                if isinstance(st, dict) and isinstance(st.get("center"), dict) and geom_dim(g) >= 1:
                    cs = st["center"]
                    cw = U.px(cs.get("width"), 0.0)
                    if cw > 0:
                        cst = {"cap": st.get("cap", "round"), "join": st.get("join", "round"),
                               "width": cw, "color": cs.get("color")}
                        sg = stroke_geom(g, cst, U)
                        if sg is not None:
                            op = num_or0(sym.get("opacity", 1.0)) * (num_or0(cs["opacity"]) if "opacity" in cs else 1)
                            canvas.paint(raster(sg, W, H), color(cs.get("color")), op)
            i = j

    # labels: a separate pass on top of everything
    placed = []
    todo = []
    order = 0
    for (lid, fi), (lab, g, props) in labels.items():
        els = marker_elements(lab) if isinstance(lab, dict) and "elements" in lab else []
        if not els:
            continue
        pr = num_or0((lab.get("placement") or {}).get("priority", 0))
        todo.append((-pr, order, g, els))
        order += 1
    todo.sort(key=lambda t: (t[0], t[1]))
    for _, _, g, els in todo:
        pt = label_point(g)
        tmp = Layer(W, H)
        bbs = []
        for el in els:
            if el.get("type") == "Text":
                pos = el.get("position")
                ox = oy = 0.0
                if isinstance(pos, list) and len(pos) == 2:
                    ox, oy = U.px(pos[0]), U.px(pos[1])
                txt = el.get("text")
                bb = draw_text(tmp, el, "" if txt is None else str(txt), pt[0] + ox, pt[1] + oy, U, W, H)
                bbs.append(bb)
            else:
                draw_graphic(tmp, el, pt, U, W, H)
        if any(overlap(b, p) for b in bbs for p in placed):
            continue
        placed += bbs
        canvas.composite(tmp, 1.0)

    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    canvas.to_image().save(os.path.join(ROOT, "out", name + "-1.png"))


def overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def label_point(g):
    if isinstance(g, (Point,)):
        return (g.x, g.y)
    if isinstance(g, (LineString,)):
        p = g.interpolate(0.5, normalized=True)
        return (p.x, p.y)
    if isinstance(g, Polygon):
        p = g.representative_point()
        return (p.x, p.y)
    if hasattr(g, "geoms"):
        parts = sorted(g.geoms, key=lambda s: -(s.length if s.geom_type.endswith("String") else s.area))
        return label_point(parts[0])
    c = g.centroid
    return (c.x, c.y)


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "cases", "case-*")))
    for n in names:
        render_case(n)
        print("rendered", n, flush=True)
