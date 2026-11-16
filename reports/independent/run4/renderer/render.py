"""Renderer for OGC Cartographic Symbology 2.0 Part 1 (draft), written from ../spec only.

usage: python render.py [case ...]     (default: all cases under ../cases)
writes ../out/<case>-<N>.png
"""
import glob
import json
import math
import os
import sys

import cairo
import numpy as np
from PIL import Image
from shapely.geometry import shape, box, LineString, MultiLineString, Point
from shapely.ops import transform as shp_transform

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cartosym import (View, Ctx, cascade, resolve_value, parse_color, to_px, num, get_num, get_bool,  # noqa: E402
                      to_text, default_of, load_style, is_unit_value, evaluate)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
CASES = os.path.join(ROOT, "cases")
OUT = os.path.join(ROOT, "out")


# ================================================================ data

class VectorLayer:
    def __init__(self, path, lid):
        with open(path, encoding="utf-8") as f:
            fc = json.load(f)
        self.id = lid
        self.type = "vector"
        self.features = []
        for i, ft in enumerate(fc["features"]):
            if not ft.get("geometry"):
                continue
            self.features.append((ft.get("id", i), ft.get("properties") or {}, shape(ft["geometry"])))
        dims = {geom_dim(g) for _, _, g in self.features}
        self.dim = dims.pop() if len(dims) == 1 else None


def geom_dim(g):
    t = g.geom_type
    if "Point" in t:
        return 0
    if "Line" in t:
        return 1
    if "Polygon" in t:
        return 2
    return None


def read_asc(path):
    hdr = {}
    with open(path) as f:
        for _ in range(6):
            k, v = f.readline().split()
            hdr[k.lower()] = float(v)
        data = np.loadtxt(f, dtype=float)
    return hdr, data.reshape(int(hdr["nrows"]), int(hdr["ncols"]))


class CoverageLayer:
    def __init__(self, paths, lid):
        self.id = lid
        self.type = "coverage"
        self.bands = {}
        self.hdr = None
        for p in paths:
            band = os.path.basename(p).split(".")[1]
            hdr, data = read_asc(p)
            nod = hdr.get("nodata_value")
            mask = data == nod if nod is not None else np.zeros_like(data, bool)
            data = np.where(mask, np.nan, data)
            self.bands[band] = data
            self.hdr = hdr
        h = self.hdr
        self.x0 = h["xllcorner"]
        self.cs = h["cellsize"]
        self.nrows = int(h["nrows"])
        self.ncols = int(h["ncols"])
        self.ytop = h["yllcorner"] + self.nrows * self.cs

    def pixel_centres(self, view):
        xs = view.minx + (np.arange(view.width) + 0.5) * view.resx
        ys = view.maxy - (np.arange(view.height) + 0.5) * view.resy
        return np.meshgrid(xs, ys)

    def sample_nearest(self, view):
        """CHOICE: each output pixel shows the cell that contains the pixel centre."""
        X, Y = self.pixel_centres(view)
        c = np.floor((X - self.x0) / self.cs).astype(int)
        r = np.floor((self.ytop - Y) / self.cs).astype(int)
        inside = (c >= 0) & (c < self.ncols) & (r >= 0) & (r < self.nrows)
        cc = np.clip(c, 0, self.ncols - 1)
        rr = np.clip(r, 0, self.nrows - 1)
        out = {}
        for b, d in self.bands.items():
            v = d[rr, cc]
            out[b] = np.where(inside, v, np.nan)
        return out

    def sample_bilinear(self, view):
        """Samples at the resolution being rendered, for hill shading (CHOICE)."""
        X, Y = self.pixel_centres(view)
        fc = (X - self.x0) / self.cs - 0.5
        fr = (self.ytop - Y) / self.cs - 0.5
        inside = (fc >= -0.5) & (fc <= self.ncols - 0.5) & (fr >= -0.5) & (fr <= self.nrows - 0.5)
        fc = np.clip(fc, 0, self.ncols - 1)
        fr = np.clip(fr, 0, self.nrows - 1)
        c0 = np.minimum(np.floor(fc).astype(int), self.ncols - 2)
        r0 = np.minimum(np.floor(fr).astype(int), self.nrows - 2)
        tx = fc - c0
        ty = fr - r0
        out = {}
        for b, d in self.bands.items():
            v = (d[r0, c0] * (1 - tx) * (1 - ty) + d[r0, c0 + 1] * tx * (1 - ty) +
                 d[r0 + 1, c0] * (1 - tx) * ty + d[r0 + 1, c0 + 1] * tx * ty)
            out[b] = np.where(inside, v, np.nan)
        return out


def load_layers(case_dir, names):
    layers = []
    for n in names:
        gj = os.path.join(case_dir, n + ".geojson")
        if os.path.exists(gj):
            layers.append(VectorLayer(gj, n))
            continue
        ascs = sorted(glob.glob(os.path.join(case_dir, n + ".*.asc")))
        if ascs:
            layers.append(CoverageLayer(ascs, n))
            continue
        raise FileNotFoundError(n)
    return layers


# ================================================================ helpers

def set_rgba(cr, rgb, a):
    cr.set_source_rgba(rgb[0], rgb[1], rgb[2], max(0.0, min(1.0, a)))


def geom_to_px(g, view):
    return shp_transform(lambda x, y, z=None: ((np.asarray(x) - view.minx) / view.resx,
                                               (view.maxy - np.asarray(y)) / view.resy), g)


def path_lines(cr, g):
    t = g.geom_type
    if t == "LineString":
        cs = list(g.coords)
        if len(cs) < 2:
            return
        cr.move_to(*cs[0][:2])
        for c in cs[1:]:
            cr.line_to(*c[:2])
    elif t in ("MultiLineString", "GeometryCollection"):
        for p in g.geoms:
            path_lines(cr, p)
    elif t == "Polygon":
        for ring in [g.exterior] + list(g.interiors):
            cs = list(ring.coords)
            cr.move_to(*cs[0][:2])
            for c in cs[1:]:
                cr.line_to(*c[:2])
            cr.close_path()
    elif t == "MultiPolygon":
        for p in g.geoms:
            path_lines(cr, p)


def marker_points(g):
    """/req/vector/marker: points, each point of line strings, centroid of polygons."""
    t = g.geom_type
    if t == "Point":
        return [(g.x, g.y)]
    if t == "MultiPoint":
        return [(p.x, p.y) for p in g.geoms]
    if t == "LineString":
        return [c[:2] for c in g.coords]
    if t == "MultiLineString":
        return [c[:2] for p in g.geoms for c in p.coords]
    if t in ("Polygon", "MultiPolygon"):
        # CHOICE: one centroid for the whole (multi)polygon
        c = g.centroid
        return [(c.x, c.y)]
    return []


def unit_point(v, view):
    """UnitPoint -> (x, y) in px.  Accepts {x, y}, [x, y] or a tuple."""
    if v is None:
        return (0.0, 0.0)
    if isinstance(v, dict) and not is_unit_value(v):
        return (to_px(v.get("x", 0), view) or 0.0, to_px(v.get("y", 0), view) or 0.0)
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        return (to_px(v[0], view) or 0.0, to_px(v[1], view) or 0.0)
    return (0.0, 0.0)


FONT_CACHE = {}


def font_setup(cr, font, view):
    face = font.get("face") if isinstance(font, dict) else None
    face = face if isinstance(face, str) and face else "Arial"  # CHOICE: default face
    size_pt = get_num(font, "size", 10.0)  # CHOICE: default size 10 pt
    bold = get_bool(font, "bold", False)
    italic = get_bool(font, "italic", False)
    cr.select_font_face(face, cairo.FONT_SLANT_ITALIC if italic else cairo.FONT_SLANT_NORMAL,
                        cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    px = size_pt * (25.4 / 72.0) / view.pixel_mm  # /req/vector/fonts: size in points
    cr.set_font_size(px)
    return px


def text_layout(cr, el, view):
    """Return (text, font_px, dx, baseline_dy, width, ascent, descent, outline) for a Text graphic
    relative to its anchor (screen coordinates, y down)."""
    font = el.get("font") if isinstance(el.get("font"), dict) else {}
    text = to_text(el.get("text"))
    fpx = font_setup(cr, font, view)
    asc, desc = cr.font_extents()[0], cr.font_extents()[1]
    ext = cr.text_extents(text)
    w = ext.x_advance
    al = el.get("alignment")
    h, v = "center", "middle"  # CHOICE: default alignment
    if isinstance(al, (list, tuple)) and len(al) == 2:
        h, v = al[0] or h, al[1] or v
    elif isinstance(al, dict):
        h = al.get("hAlignment", al.get("horzAlignment", al.get("horizontal", h))) or h
        v = al.get("vAlignment", al.get("vertAlignment", al.get("vertical", v))) or v
    dx = {"left": 0.0, "center": -w / 2, "right": -w}.get(h, -w / 2)
    # CHOICE: top/bottom are the font ascent/descent lines, middle is half way between them
    dy = {"top": asc, "middle": (asc - desc) / 2, "bottom": -desc}.get(v, (asc - desc) / 2)
    outline = font.get("outline") if isinstance(font.get("outline"), dict) else None
    return text, fpx, dx, dy, w, asc, desc, outline


def element_bbox(cr, el, x, y, view, case_dir):
    """Screen bbox of one graphic drawn with its anchor at (x, y) (already offset)."""
    t = el.get("type")
    if t == "Text":
        text, fpx, dx, dy, w, asc, desc, outline = text_layout(cr, el, view)
        pad = to_px(outline.get("size", 1), view) if outline else 0.0
        top = y + dy - asc
        return (x + dx - pad, top - pad, x + dx + w + pad, top + asc + desc + pad)
    if t == "Dot":
        s = dot_size(el, view) / 2
        return (x - s, y - s, x + s, y + s)
    if t == "Image":
        img = load_image(el, case_dir)
        if img is None:
            return None
        w, h = img.get_width(), img.get_height()
        hx, hy = hotspot(el, w, h, view)
        return (x - hx, y - hy, x - hx + w, y - hy + h)
    return None


def dot_size(el, view):
    st = el.get("stroke") if isinstance(el.get("stroke"), dict) else {}
    if "size" in el:
        return to_px(el["size"], view) or 0.0
    if "width" in st:
        return to_px(st["width"], view) or 0.0
    return 10.0  # Dot default size 10 px


def dot_color(el):
    st = el.get("stroke") if isinstance(el.get("stroke"), dict) else {}
    if "color" in el:
        return parse_color(el["color"])
    if "color" in st:
        return parse_color(st["color"])
    return (1.0, 1.0, 1.0)  # Dot default colour white


IMG_CACHE = {}


def load_image(el, case_dir):
    res = el.get("image") or {}
    path = res.get("path") if isinstance(res, dict) else None
    if not path:
        return None
    full = os.path.normpath(os.path.join(case_dir, path))
    tint = parse_color(el.get("tint", "white"))
    black = parse_color(el.get("blackTint", "black"))
    key = (full, tint, black)
    if key in IMG_CACHE:
        return IMG_CACHE[key]
    if not os.path.exists(full):
        IMG_CACHE[key] = None
        return None
    im = np.asarray(Image.open(full).convert("RGBA")).astype(float) / 255.0
    rgb = im[..., :3]
    t = np.array(tint)
    b = np.array(black)
    # /req/vector/image: v -> tint*v + blackTint*(1-v), per component
    rgb = t * rgb + b * (1 - rgb)
    a = im[..., 3:4]
    pre = np.concatenate([rgb * a, a], axis=2)
    surf = np_to_surface(pre)
    IMG_CACHE[key] = surf
    return surf


def hotspot(el, w, h, view):
    """hotSpot in image pixels from top-left (y down, image convention)."""
    hs = el.get("hotSpot")
    if hs is None:
        return (0.5 * w, 0.5 * h)
    comps = [hs.get("x"), hs.get("y")] if isinstance(hs, dict) else list(hs)[:2]
    out = []
    for c, size in zip(comps, (w, h)):
        if isinstance(c, dict) and "pc" in c:
            out.append(num(c["pc"]) / 100.0 * size)
        elif isinstance(c, (int, float)):
            # CHOICE: a bare number is a fraction of the image size (default {0.5, 0.5})
            out.append(c * size)
        else:
            v = to_px(c, view)
            out.append(v if v is not None else 0.5 * size)
    return tuple(out)


def np_to_surface(pre):
    """pre: HxWx4 float premultiplied RGBA 0..1 -> cairo ImageSurface."""
    hgt, wid = pre.shape[:2]
    arr = np.zeros((hgt, wid, 4), dtype=np.uint8)
    p8 = np.clip(np.round(pre * 255), 0, 255).astype(np.uint8)
    arr[..., 0] = p8[..., 2]
    arr[..., 1] = p8[..., 1]
    arr[..., 2] = p8[..., 0]
    arr[..., 3] = p8[..., 3]
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, wid, hgt)
    stride = surf.get_stride()
    buf = surf.get_data()
    mv = np.ndarray(shape=(hgt, stride // 4, 4), dtype=np.uint8, buffer=buf)
    mv[:, :wid, :] = arr
    surf.mark_dirty()
    return surf


# ================================================================ graphics

def draw_graphic(cr, el, x, y, view, case_dir, opacity=1.0):
    """Draw one Graphic with its (already offset) anchor at screen (x, y)."""
    if not isinstance(el, dict):
        return
    t = el.get("type")
    op = opacity * get_num(el, "opacity", 1.0)
    if t == "Dot":
        s = dot_size(el, view)
        if s <= 0:
            return
        st = el.get("stroke") if isinstance(el.get("stroke"), dict) else {}
        set_rgba(cr, dot_color(el), op * get_num(st, "opacity", 1.0))
        cr.new_path()
        cr.arc(x, y, s / 2, 0, 2 * math.pi)
        cr.fill()
    elif t == "Image":
        img = load_image(el, case_dir)
        if img is None:
            return
        w, h = img.get_width(), img.get_height()
        hx, hy = hotspot(el, w, h, view)
        # CHOICE: image drawn at its native pixel size, snapped to whole pixels
        cr.save()
        cr.set_source_surface(img, round(x - hx), round(y - hy))
        cr.paint_with_alpha(op)
        cr.restore()
    elif t == "Text":
        draw_text(cr, el, x, y, view, op)
    elif "elements" in el:
        dx, dy = unit_point(el.get("position"), view)
        for sub in el.get("elements") or []:
            sdx, sdy = unit_point(sub.get("position") if isinstance(sub, dict) else None, view)
            draw_graphic(cr, sub, x + dx + sdx, y - dy - sdy, view, case_dir, op)


def draw_text(cr, el, x, y, view, opacity=1.0):
    text, fpx, dx, dy, w, asc, desc, outline = text_layout(cr, el, view)
    if not text:
        return
    font = el.get("font") if isinstance(el.get("font"), dict) else {}
    color = parse_color(font.get("color", "black"))  # CHOICE: default font colour black
    fop = get_num(font, "opacity", 1.0)
    bx, by = x + dx, y + dy
    if outline:
        size = to_px(outline.get("size", 1), view) or 0.0  # CHOICE: outline size in px
        if size > 0:
            cr.new_path()
            cr.move_to(bx, by)
            cr.text_path(text)
            cr.set_line_width(2 * size)  # extends outward by `size` from the contour
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            set_rgba(cr, parse_color(outline.get("color", "white")),
                     opacity * get_num(outline, "opacity", 1.0))
            cr.stroke()
    cr.new_path()
    cr.move_to(bx, by)
    set_rgba(cr, color, opacity * fop)
    cr.show_text(text)
    cr.new_path()


# ================================================================ fills

RNG_CACHE = {}


def stipple_surface(view, rgb, ratio, alpha):
    key = (view.width, view.height)
    if key not in RNG_CACHE:
        RNG_CACHE[key] = np.random.default_rng(12345).random((view.height, view.width))
    on = (RNG_CACHE[key] < ratio).astype(float)[..., None]
    pre = np.concatenate([np.array(rgb) * on * alpha, on * alpha], axis=2)
    return np_to_surface(pre)


def fill_polygon(cr, g, fill, view):
    color = parse_color(fill.get("color", "white"))
    a = get_num(fill, "opacity", 1.0)
    hatch = fill.get("hatch") if isinstance(fill.get("hatch"), dict) else None
    dotp = fill.get("dotpattern") if isinstance(fill.get("dotpattern"), dict) else None
    stip = fill.get("stipple") if isinstance(fill.get("stipple"), dict) else None
    cr.new_path()
    path_lines(cr, g)
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    if not (hatch or dotp or stip):
        set_rgba(cr, color, a)
        cr.fill()
        return
    cr.save()
    cr.clip()
    if hatch:
        # CHOICE: lines in the fill colour; no solid background; angle clockwise on screen
        # from the horizontal (+x); `distance` centre to centre; a line passes through pixel (0, 0).
        width = to_px(hatch.get("width", {"px": 1}), view) or 0.0
        dist = to_px(hatch.get("distance", {"px": 10}), view) or 0.0
        ang = get_num(hatch, "angle", 45.0)
        if isinstance(hatch.get("angle"), dict):
            av = hatch["angle"]
            ang = num(av.get("deg")) if "deg" in av else math.degrees(num(av.get("rad")) or 0)
        if width > 0 and dist > 0:
            th = math.radians(ang)
            d = (math.cos(th), math.sin(th))  # y down: positive angle turns clockwise
            n = (-d[1], d[0])
            diag = math.hypot(view.width, view.height)
            corners = [(0, 0), (view.width, 0), (0, view.height), (view.width, view.height)]
            proj = [c[0] * n[0] + c[1] * n[1] for c in corners]
            k0 = math.floor(min(proj) / dist) - 1
            k1 = math.ceil(max(proj) / dist) + 1
            cr.new_path()
            for k in range(k0, k1 + 1):
                ox, oy = n[0] * k * dist, n[1] * k * dist
                # point on the line nearest the canvas centre
                cx, cy = view.width / 2, view.height / 2
                t = (cx - ox) * d[0] + (cy - oy) * d[1]
                px, py = ox + d[0] * t, oy + d[1] * t
                cr.move_to(px - d[0] * diag, py - d[1] * diag)
                cr.line_to(px + d[0] * diag, py + d[1] * diag)
            cr.set_line_width(width)
            cr.set_line_cap(cairo.LINE_CAP_BUTT)
            set_rgba(cr, color, a)
            cr.stroke()
    if dotp:
        dist = dotp.get("distance") or {}
        if isinstance(dist, (list, tuple)):
            hd, vd = to_px(dist[0], view), to_px(dist[1], view)
        else:
            hd = to_px(dist.get("horizontal", {"px": 10}), view)
            vd = to_px(dist.get("vertical", {"px": 10}), view)
        if hd and vd and hd > 0 and vd > 0:
            # CHOICE: 2 px round dots in the fill colour, grid anchored at the top-left
            # of the image, first dot at (h/2, v/2); no solid background.
            set_rgba(cr, color, a)
            x1, y1, x2, y2 = cr.clip_extents()
            i0, i1 = int(math.floor(x1 / hd)) - 1, int(math.ceil(x2 / hd)) + 1
            j0, j1 = int(math.floor(y1 / vd)) - 1, int(math.ceil(y2 / vd)) + 1
            cr.new_path()
            for j in range(j0, j1):
                for i in range(i0, i1):
                    cx, cy = i * hd + hd / 2, j * vd + vd / 2
                    cr.move_to(cx + 1.0, cy)
                    cr.arc(cx, cy, 1.0, 0, 2 * math.pi)
            cr.fill()
    if stip:
        ratio = get_num(stip, "ratio", 0.5)
        # CHOICE: each pixel of the area gets a 1 px dot with probability `ratio`
        # (fixed pseudo-random sequence over the image), in the fill colour.
        cr.set_source_surface(stipple_surface(view, color, ratio, a), 0, 0)
        cr.paint()
    cr.restore()
    cr.new_path()


def stroke_path(cr, g, styling, view, dash=None, dash_offset=0.0, extra_width=0.0, alpha=1.0):
    w = (to_px(styling.get("width", {"px": 1}), view) or 0.0) + extra_width
    if w <= 0:
        return
    color = parse_color(styling.get("color", "black"))
    a = get_num(styling, "opacity", 1.0) * alpha
    cr.new_path()
    path_lines(cr, g)
    cr.set_line_width(w)
    cr.set_line_cap(cairo.LINE_CAP_BUTT)     # clause 8: butt caps
    cr.set_line_join(cairo.LINE_JOIN_MITER)  # clause 8: miter joins
    if dash:
        cr.set_dash(dash, dash_offset)       # CHOICE: dashOffset = distance into the pattern
    else:
        cr.set_dash([])
    set_rgba(cr, color, a)
    cr.stroke()
    cr.set_dash([])


def dash_of(stroke, view):
    dp = stroke.get("dashPattern")
    if not isinstance(dp, list) or not dp:
        return None, 0.0
    lens = [max(0.0, to_px(x, view) or 0.0) for x in dp]
    if sum(lens) <= 0:
        return None, 0.0
    if len(lens) % 2 == 1:
        lens = lens * 2
    off = to_px(stroke.get("dashOffset", 0), view) or 0.0
    return lens, off


# ================================================================ coverage

def interp_map(entries, v, ncomp):
    """Value map with linear interpolation, clamped outside (req coverage color-map / opacity-map)."""
    es = sorted(entries, key=lambda e: e[0])
    xs = np.array([e[0] for e in es], float)
    out = []
    for k in range(ncomp):
        ys = np.array([e[1][k] for e in es], float)
        out.append(np.interp(v, xs, ys))
    return out


def draw_coverage(cr, layer, sym, view, rules_ctx):
    near = layer.sample_nearest(view)
    ctxn = Ctx(view, layer.id, "coverage", props=near, variables=rules_ctx.variables)
    names = list(layer.bands.keys())
    H, W = view.height, view.width
    valid = np.ones((H, W), bool)
    for b in names:
        valid &= ~np.isnan(near[b])
    sc_expr = sym.get("singleChannel")
    if sc_expr is None and len(names) == 1:
        sc_expr = {"property": names[0]}
    single = evaluate(sc_expr, ctxn) if sc_expr is not None else None
    if single is not None:
        single = np.broadcast_to(np.asarray(single, float), (H, W))
    rgb = None
    cmap = sym.get("colorMap")
    if isinstance(cmap, list) and cmap and single is not None:
        ents = [(float(num(evaluate(e[0], ctxn))), parse_color(evaluate(e[1], ctxn))) for e in cmap]
        rgb = np.stack(interp_map(ents, np.nan_to_num(single), 3), axis=-1)
    elif sym.get("colorChannels") is not None:
        cc = sym["colorChannels"]
        comps = [cc.get(k) for k in "rgb"] if isinstance(cc, dict) else list(cc)
        rgb = np.stack([np.broadcast_to(np.asarray(evaluate(c, ctxn), float), (H, W)) for c in comps], -1)
        rgb = np.clip(rgb, 0, 1)
    elif single is not None:
        rgb = np.repeat(np.clip(single, 0, 1)[..., None], 3, axis=-1)
    elif len(names) >= 3:
        rgb = np.stack([near[n] for n in names[:3]], -1)
        rgb = np.clip(rgb, 0, 1)
    else:
        rgb = np.ones((H, W, 3))
    alpha = np.broadcast_to(np.asarray(evaluate(sym.get("alphaChannel", 1), ctxn) or 0, float), (H, W)).copy()
    omap = sym.get("opacityMap")
    if isinstance(omap, list) and omap and single is not None:
        ents = [(float(num(evaluate(e[0], ctxn))), (float(num(evaluate(e[1], ctxn))),)) for e in omap]
        alpha = alpha * interp_map(ents, np.nan_to_num(single), 1)[0]
    hs = sym.get("hillShading")
    if isinstance(hs, dict):
        bil = layer.sample_bilinear(view)
        ctxb = Ctx(view, layer.id, "coverage", props=bil, variables=rules_ctx.variables)
        elev = evaluate(sc_expr, ctxb) if sc_expr is not None else bil[names[0]]
        elev = np.asarray(elev, float)
        shade = hill_shade(elev, view, hs)
        hcm = hs.get("colorMap")
        if isinstance(hcm, list) and hcm:
            ents = [(float(num(e[0])), parse_color(e[1])) for e in hcm]
            rgb = np.stack(interp_map(ents, shade, 3), axis=-1)
        else:
            rgb = rgb * shade[..., None]
        hom = hs.get("opacityMap")
        if isinstance(hom, list) and hom:
            ents = [(float(num(e[0])), (float(num(e[1])),)) for e in hom]
            alpha = alpha * interp_map(ents, shade, 1)[0]
    alpha = np.where(valid, np.clip(alpha, 0, 1), 0.0)
    alpha = alpha * get_num(sym, "opacity", 1.0)
    pre = np.concatenate([np.clip(rgb, 0, 1) * alpha[..., None], alpha[..., None]], axis=-1)
    cr.set_source_surface(np_to_surface(pre), 0, 0)
    cr.paint()


def hill_shade(elev, view, hs):
    factor = get_num(hs, "factor", 1.0)  # CHOICE: default factor 1
    sun = hs.get("sun") if isinstance(hs.get("sun"), dict) else {}

    def ang(v, d):
        if v is None:
            return d
        if isinstance(v, dict):
            return num(v["deg"]) if "deg" in v else math.degrees(num(v.get("rad", 0)))
        return float(num(v))
    az = math.radians(ang(sun.get("azimuth"), 315.0))  # CHOICE: default sun 315 / 45
    el = math.radians(ang(sun.get("elevation"), 45.0))
    e = np.where(np.isnan(elev), np.nanmean(elev), elev)
    # rows go south, columns go east; spacing = ground size of an output pixel
    d_drow, d_dcol = np.gradient(e)
    dzdx = d_dcol / view.resx
    dzdy = -d_drow / view.resy
    nx, ny, nz = -factor * dzdx, -factor * dzdy, np.ones_like(e)
    nl = np.sqrt(nx * nx + ny * ny + nz * nz)
    sx, sy, sz = math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)
    shade = (nx * sx + ny * sy + nz * sz) / nl
    return np.clip(shade, 0.0, 1.0)


# ================================================================ labels

class LabelCand:
    def __init__(self, x, y, label, priority, key, order, spacing, case_dir):
        self.x, self.y = x, y
        self.label = label
        self.priority = priority
        self.key = key
        self.order = order
        self.spacing = spacing


def label_boxes(cr, cand, view, case_dir):
    boxes = []
    lab = cand.label
    dx, dy = unit_point(lab.get("position"), view)
    for el in lab.get("elements") or []:
        if not isinstance(el, dict):
            continue
        ex, ey = unit_point(el.get("position"), view)
        b = element_bbox(cr, el, cand.x + dx + ex, cand.y - dy - ey, view, case_dir)
        if b:
            boxes.append(b)
    return boxes


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def line_label_points(gpx, spacing, view):
    clip = gpx.intersection(box(0, 0, view.width, view.height))
    parts = []
    if clip.is_empty:
        return []
    if clip.geom_type == "LineString":
        parts = [clip]
    elif hasattr(clip, "geoms"):
        parts = [p for p in clip.geoms if p.geom_type == "LineString"]
    pts = []
    if spacing is None:
        # CHOICE: without spacing, one label at the middle of the longest visible part
        if parts:
            p = max(parts, key=lambda q: q.length)
            c = p.interpolate(p.length / 2)
            pts.append((c.x, c.y))
        return pts
    for p in parts:
        L = p.length
        n = int(L // spacing) + 1
        off = (L - (n - 1) * spacing) / 2
        for k in range(n):
            c = p.interpolate(off + k * spacing)
            pts.append((c.x, c.y))
    return pts


def place_and_draw_labels(cr, cands, view, case_dir):
    # /req/labels/placement: higher priority placed first; ties keep data order
    cands.sort(key=lambda c: (-c.priority, c.order))
    placed_boxes = []
    placed_by_key = {}
    accepted = []
    for c in cands:
        boxes = label_boxes(cr, c, view, case_dir)
        if not boxes:
            continue
        if all(b[2] <= 0 or b[0] >= view.width or b[3] <= 0 or b[1] >= view.height for b in boxes):
            continue
        # /rec/labels/overlap: omit labels that would overlap a placed label
        if any(overlaps(b, p) for b in boxes for p in placed_boxes):
            continue
        if c.spacing:
            if any(math.hypot(c.x - px, c.y - py) < c.spacing for px, py in placed_by_key.get(c.key, [])):
                continue
        placed_boxes.extend(boxes)
        placed_by_key.setdefault(c.key, []).append((c.x, c.y))
        accepted.append(c)
    for c in accepted:
        draw_graphic(cr, dict(c.label, type=None), c.x, c.y, view, case_dir, 1.0)


# ================================================================ main pass

def render_view(case_dir, style, vj, out_path):
    view = View(vj)
    layers = load_layers(case_dir, view.layers)
    variables = style.get("$variables", {})
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, view.width, view.height)
    cr = cairo.Context(surf)
    set_rgba(cr, parse_color(view.background), 1.0)
    cr.paint()

    items = []   # (zOrder, layer_index, feature_index, kind, payload)
    label_cands = []
    order = 0
    for li, layer in enumerate(layers):
        if layer.type == "coverage":
            ctx = Ctx(view, layer.id, "coverage", variables=variables)
            sym, _ = cascade(style["stylingRules"], ctx)
            if not get_bool(sym, "visibility", True):
                continue
            items.append((get_num(sym, "zOrder", 1), li, 0, "coverage", (layer, sym, ctx)))
            continue
        for fi, (fid, props, geom) in enumerate(layer.features):
            ctx = Ctx(view, layer.id, "vector", props=props, feature_id=fid, geom_dim=geom_dim(geom),
                      variables=variables, layer_dim=layer.dim)
            # CHOICE: a feature selected by no rule is still drawn with the default symbolizer
            raw, _ = cascade(style["stylingRules"], ctx)
            sym = resolve_value(raw, ctx)
            if not get_bool(sym, "visibility", True):
                continue
            gpx = geom_to_px(geom, view)
            items.append((get_num(sym, "zOrder", 1), li, fi, "vector", (gpx, sym)))
            lab = sym.get("label")
            if isinstance(lab, dict) and lab.get("elements"):
                pl = lab.get("placement") if isinstance(lab.get("placement"), dict) else {}
                prio = get_num(pl, "priority", 0.0)  # CHOICE: default priority 0
                spacing = None
                if "minSpacing" in pl:
                    spacing = to_px(pl["minSpacing"], view)
                elif "maxSpacing" in pl:
                    spacing = to_px(pl["maxSpacing"], view)
                key = (layer.id, tuple(to_text(e.get("text")) for e in lab["elements"] if isinstance(e, dict)))
                dim = geom_dim(geom)
                if dim == 1:
                    pts = line_label_points(gpx, spacing, view)
                else:
                    pts = [view.to_pixel(*p) for p in marker_points(geom)]
                for (x, y) in pts:
                    label_cands.append(LabelCand(x, y, lab, prio, key, order, spacing if dim == 1 else None,
                                                 case_dir))
                    order += 1

    items.sort(key=lambda it: (it[0], it[1], it[2]))
    zs = sorted({it[0] for it in items})
    for z in zs:
        group = [it for it in items if it[0] == z]
        # /req/casing/casing: all casings of this zOrder beneath all main strokes
        for it in group:
            if it[3] != "vector":
                continue
            gpx, sym = it[4]
            st = sym.get("stroke", default_of("stroke"))
            if isinstance(st, dict) and isinstance(st.get("casing"), dict) and geom_dim(gpx) in (1, 2):
                main_w = to_px(st.get("width", {"px": 1}), view) or 0.0
                cw = to_px(st["casing"].get("width", {"px": 1}), view) or 0.0
                cs = dict(st["casing"])
                cs["width"] = main_w + 2 * cw
                stroke_path(cr, gpx, cs, view, alpha=get_num(sym, "opacity", 1.0))
        for it in group:
            if it[3] == "coverage":
                layer, sym, ctx = it[4]
                draw_coverage(cr, layer, sym, view, ctx)
            else:
                draw_feature(cr, it[4][0], it[4][1], view, case_dir)
        # CHOICE: centre lines after all main strokes of this zOrder
        for it in group:
            if it[3] != "vector":
                continue
            gpx, sym = it[4]
            st = sym.get("stroke", default_of("stroke"))
            cl = None
            if isinstance(st, dict):
                cl = st.get("center", st.get("centerLine"))
            if isinstance(cl, dict) and geom_dim(gpx) in (1, 2):
                stroke_path(cr, gpx, cl, view, alpha=get_num(sym, "opacity", 1.0))

    # /req/labels/label: separate pass on top
    place_and_draw_labels(cr, label_cands, view, case_dir)

    surf.flush()
    buf = np.ndarray(shape=(view.height, surf.get_stride() // 4, 4), dtype=np.uint8, buffer=surf.get_data())
    arr = buf[:, :view.width, :]
    rgb = np.stack([arr[..., 2], arr[..., 1], arr[..., 0]], axis=-1)
    Image.fromarray(rgb.copy(), "RGB").save(out_path)


def draw_feature(cr, gpx, sym, view, case_dir):
    op = get_num(sym, "opacity", 1.0)
    dim = geom_dim(gpx)
    # /rec/core/opacity-together: fill, stroke and marker composed first, then opacity applied
    cr.push_group()
    if dim == 2:
        fill = sym.get("fill", default_of("fill"))
        if isinstance(fill, dict):
            fill_polygon(cr, gpx, fill, view)
    if dim in (1, 2):
        st = sym.get("stroke", default_of("stroke"))
        if isinstance(st, dict):
            dash, off = dash_of(st, view)
            stroke_path(cr, gpx, st, view, dash, off)
    marker = sym["marker"] if "marker" in sym else default_of("marker")
    if isinstance(marker, dict):
        elements = marker.get("elements", default_of("marker")["elements"]) if marker else \
            default_of("marker")["elements"]
        if elements:
            mdx, mdy = unit_point(marker.get("position"), view)
            mop = get_num(marker, "opacity", 1.0)
            for (x, y) in marker_points(gpx):
                for el in elements:
                    if not isinstance(el, dict):
                        continue
                    ex, ey = unit_point(el.get("position"), view)
                    # CHOICE: +y of a Graphic position points up on the map
                    draw_graphic(cr, el, x + mdx + ex, y - mdy - ey, view, case_dir, mop)
    cr.pop_group_to_source()
    cr.paint_with_alpha(max(0.0, min(1.0, op)))


def render_case(case):
    case_dir = os.path.join(CASES, case)
    style = load_style(os.path.join(case_dir, "style.cs.json"))
    outs = []
    for vp in sorted(glob.glob(os.path.join(case_dir, "view-*.json"))):
        n = os.path.basename(vp)[5:-5]
        with open(vp, encoding="utf-8") as f:
            vj = json.load(f)
        out = os.path.join(OUT, f"{case}-{n}.png")
        render_view(case_dir, style, vj, out)
        outs.append(out)
    return outs


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    cases = argv or sorted(d for d in os.listdir(CASES)
                           if os.path.isdir(os.path.join(CASES, d)) and d != "icons")
    ok, failed = 0, []
    for c in cases:
        try:
            outs = render_case(c)
            ok += 1
            print("ok", c, [os.path.basename(o) for o in outs])
        except Exception as e:  # report and continue
            import traceback
            traceback.print_exc()
            failed.append((c, repr(e)))
    print(f"{ok} cases rendered, {len(failed)} failed")
    for c, e in failed:
        print("FAILED", c, e)


if __name__ == "__main__":
    main(sys.argv[1:])
