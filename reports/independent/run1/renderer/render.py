"""Independent CartoSym-JSON renderer written from spec/1-core only.

Usage: python render.py <cases-dir> <out-dir> [case ...]
"""
import copy
import datetime as dt
import glob
import json
import math
import os
import sys

import cairo
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from expr import parse_instant  # noqa: E402
from style import (DEFAULT_FILL, DEFAULT_MARKER, DEFAULT_STROKE, Units,  # noqa: E402
                   Unsupported, apply_map, resolve_alignment, resolve_angle,
                   resolve_bool, resolve_color, resolve_length, resolve_number,
                   resolve_point, resolve_symbolizer, resolve_text,
                   resolve_value_map, split_unit)

SUPPORTED_CAPABILITIES = {
    "vector", "coverage", "labels", "hillshading", "fontoutlines", "hatches",
    "stipples", "dashes", "casing", "parametervalues", "arithmetic", "conditional",
    "righthand",
}


# ---------------------------------------------------------------- evaluation context

class Ctx:
    def __init__(self, view, layer_id, layer_type, props=None, feature=None, layer_dims=None):
        self.view = view
        self.layer_id = layer_id
        self.layer_type = layer_type
        self.props = props or {}
        self.feature = feature
        self.layer_dims = layer_dims

    def prop(self, name):
        return self.props.get(name)

    def sys(self, sid):
        s = sid
        if s.startswith("visualization."):
            s = "viz." + s[len("visualization."):]
        elif s == "visualization":
            s = "viz"
        s = s.replace("scaleDenominator", "sd").replace("dataLayer.identifier", "dataLayer.id")
        s = s.replace("feature.identifier", "feature.id")
        s = s.replace("geometryDimension", "geometryDimensions").replace("Dimensionss", "Dimensions")
        v = self.view
        viz = v.get("visualization", {})
        if s == "dataLayer.id":
            return self.layer_id
        if s == "dataLayer.type":
            return self.layer_type
        if s == "dataLayer.featuresGeometryDimensions":
            return self.layer_dims
        if s == "feature.geometryDimensions":
            return self.feature.get("dims") if self.feature else None
        if s == "feature.id":
            return self.feature.get("id") if self.feature else None
        if s == "viz.sd":
            return float(v["scaleDenominator"])
        if s in ("viz.pass", "feature.pass"):
            return 0
        if s.startswith("capabilities."):
            return s.split(".", 1)[1] in SUPPORTED_CAPABILITIES
        if s.startswith("viz."):
            parts = s.split(".")[1:]
            base = None
            if parts[0] == "date":
                base = parse_instant(viz.get("date"))
                parts = parts[1:]
            elif parts[0] == "dateTime":
                base = _as_datetime(viz.get("dateTime") or viz.get("date"))
                parts = parts[1:]
            elif parts[0] == "timeOfDay":
                d = _as_datetime(viz.get("dateTime") or viz.get("date"))
                base = d.time() if d else None
                parts = parts[1:]
            elif parts[0] == "timeInterval":
                ti = viz.get("timeInterval") or {}
                if len(parts) == 1:
                    return (parse_instant(ti.get("start")), parse_instant(ti.get("end")))
                base = _as_datetime(ti.get(parts[1]))
                parts = parts[2:]
            return _member(base, parts)
        return None


def _as_datetime(s):
    p = parse_instant(s) if s is not None else None
    if p is None:
        return None
    if isinstance(p, dt.datetime):
        return p
    return dt.datetime(p.year, p.month, p.day)


def _member(base, parts):
    for p in parts:
        if base is None:
            return None
        if p == "date":
            base = base.date() if isinstance(base, dt.datetime) else base
        elif p == "time":
            base = base.time() if isinstance(base, dt.datetime) else dt.time(0, 0)
        elif p in ("year", "month", "day", "hour"):
            base = getattr(base, p)
        elif p == "minutes":
            base = base.minute
        elif p == "seconds":
            base = base.second + base.microsecond / 1e6
        else:
            return None
    return base


# ---------------------------------------------------------------- data loading

def load_geojson(path, tr):
    d = json.load(open(path, encoding="utf-8"))
    feats = []
    for i, f in enumerate(d["features"]):
        g = f.get("geometry")
        if not g:
            continue
        t = g["type"]
        c = g["coordinates"]
        pts, lines, polys = [], [], []
        if t == "Point":
            pts = [tr(c)]
        elif t == "MultiPoint":
            pts = [tr(p) for p in c]
        elif t == "LineString":
            lines = [[tr(p) for p in c]]
        elif t == "MultiLineString":
            lines = [[tr(p) for p in l] for l in c]
        elif t == "Polygon":
            polys = [[[tr(p) for p in r] for r in c]]
        elif t == "MultiPolygon":
            polys = [[[tr(p) for p in r] for r in poly] for poly in c]
        dims = 0 if pts else (1 if lines else 2)
        feats.append({"id": f.get("id", i), "props": f.get("properties") or {}, "pts": pts,
                      "lines": lines, "polys": polys, "dims": dims})
    return feats


def load_asc(path):
    hdr = {}
    with open(path) as fh:
        for _ in range(6):
            k, v = fh.readline().split()
            hdr[k.lower()] = float(v)
        data = np.loadtxt(fh, dtype=float)
    nodata = hdr.get("nodata_value")
    if nodata is not None:
        data[data == nodata] = np.nan
    return hdr, data


# ---------------------------------------------------------------- geometry helpers

def ring_centroid_area(ring):
    a = cx = cy = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        cr = x0 * y1 - x1 * y0
        a += cr
        cx += (x0 + x1) * cr
        cy += (y0 + y1) * cr
    a *= 0.5
    if a == 0:
        return (ring[0][0], ring[0][1]), 0.0
    return (cx / (6 * a), cy / (6 * a)), a


def polygon_centroid(poly):
    # exterior positive, holes negative (orientation-independent)
    sx = sy = sa = 0.0
    for k, ring in enumerate(poly):
        (cx, cy), a = ring_centroid_area(ring)
        a = abs(a) * (1 if k == 0 else -1)
        sx += cx * a
        sy += cy * a
        sa += a
    if sa == 0:
        return poly[0][0]
    return (sx / sa, sy / sa)


def multipolygon_centroid(polys):
    sx = sy = sa = 0.0
    for p in polys:
        c = polygon_centroid(p)
        a = abs(ring_centroid_area(p[0])[1]) - sum(abs(ring_centroid_area(h)[1]) for h in p[1:])
        sx += c[0] * a
        sy += c[1] * a
        sa += a
    return (sx / sa, sy / sa) if sa else polygon_centroid(polys[0])


def line_points_at(line, step, W, H):
    """Arc-length positions L/2 + k*step along a line (k integer)."""
    seg = []
    total = 0.0
    for a, b in zip(line[:-1], line[1:]):
        l = math.hypot(b[0] - a[0], b[1] - a[1])
        seg.append((a, b, l))
        total += l
    if total == 0:
        return []
    positions = [total / 2]
    if step and step > 0:
        k = 1
        while total / 2 - k * step >= 0 or total / 2 + k * step <= total:
            if total / 2 - k * step >= 0:
                positions.append(total / 2 - k * step)
            if total / 2 + k * step <= total:
                positions.append(total / 2 + k * step)
            k += 1
        positions.sort()
    out = []
    for s in positions:
        acc = 0.0
        for a, b, l in seg:
            if acc + l >= s and l > 0:
                t = (s - acc) / l
                out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
                break
            acc += l
    return out


# ---------------------------------------------------------------- symbolizer -> draw params

class Resolver:
    def __init__(self, units, case_dir):
        self.units = units
        self.case_dir = case_dir
        self._img_cache = {}

    def length(self, raw, ctx, default=None, pc_base=None):
        if raw is None:
            return default
        return resolve_length(raw, ctx, self.units, pc_base=pc_base)

    def stroke_styling(self, s, ctx, defaults):
        if s is None:
            return None
        return {
            "color": resolve_color(s.get("color", defaults["color"]), ctx),
            "opacity": resolve_number(s.get("opacity"), ctx, 1.0),
            "width": self.length(s.get("width", defaults["width"]), ctx),
        }

    def stroke(self, s, ctx):
        if s is None:
            return None
        st = self.stroke_styling(s, ctx, DEFAULT_STROKE)
        dp = s.get("dashPattern")
        if dp is not None:
            # percent: of the stroke width (/per/dashes/dash-pattern-units)
            st["dash"] = [self.length(x, ctx, pc_base=st["width"]) for x in dp]
        st["dashOffset"] = self.length(s.get("dashOffset"), ctx, 0.0, pc_base=st["width"])
        st["casing"] = self.stroke_styling(s.get("casing"), ctx, DEFAULT_STROKE)
        center = s.get("center", s.get("centerLine"))
        st["center"] = self.stroke_styling(center, ctx, DEFAULT_STROKE)
        return st

    def fill(self, f, ctx):
        if f is None:
            return None
        out = {"color": resolve_color(f.get("color", DEFAULT_FILL["color"]), ctx),
               "opacity": resolve_number(f.get("opacity"), ctx, 1.0)}
        h = f.get("hatch")
        if h is not None:
            out["hatch"] = {
                "width": self.length(h.get("width"), ctx, 1.0),
                "angle": resolve_angle(h.get("angle"), ctx, 45.0),
                "distance": self.length(h.get("distance"), ctx, 10.0),
            }
        sp = f.get("stipple")
        if sp is not None:
            out["stipple"] = {"ratio": resolve_number(sp.get("ratio"), ctx, 0.5)}
        dp = f.get("dotpattern")
        if dp is not None:
            d = dp.get("distance")
            hz = vt = None
            if isinstance(d, list):
                hz, vt = d[0], d[1]
            elif isinstance(d, dict):
                hz, vt = d.get("horizontal"), d.get("vertical")
            out["dotpattern"] = {"h": self.length(hz, ctx, 10.0), "v": self.length(vt, ctx, 10.0)}
        return out

    def font(self, f, ctx):
        f = f or {}
        size_pt = resolve_number(f.get("size"), ctx, 10.0)
        o = f.get("outline")
        outline = None
        if o is not None:
            outline = {
                "size": resolve_number(o.get("size"), ctx, 1.0),
                "opacity": resolve_number(o.get("opacity"), ctx, 1.0),
                "color": resolve_color(o.get("color", "white"), ctx),
            }
        return {
            "face": resolve_text(f.get("face"), ctx) or "Arial",
            "size_px": self.units.to_px(size_pt, "pt"),
            "bold": resolve_bool(f.get("bold"), ctx, False),
            "italic": resolve_bool(f.get("italic"), ctx, False),
            "color": resolve_color(f.get("color", "black"), ctx),
            "opacity": resolve_number(f.get("opacity"), ctx, 1.0),
            "outline": outline,
        }

    def image(self, res):
        path = res.get("path")
        cands = []
        if isinstance(path, str):
            cands.append(os.path.normpath(os.path.join(self.case_dir, path)))
            cands.append(os.path.join(self.case_dir, "icons", os.path.basename(path)))
        for c in cands:
            if os.path.exists(c):
                return c
        raise FileNotFoundError("image resource %r" % (res,))

    def graphics(self, elements, ctx, sym_marker=True):
        out = []
        for g in elements or []:
            if g is None:
                continue
            t = g.get("type")
            pos = resolve_point(g.get("position"), ctx)
            dx = dy = 0.0
            if pos is not None:
                (x, ux), (y, uy) = pos
                dx = self.units.to_px(x, ux or "px")
                dy = self.units.to_px(y, uy or "px")
            e = {"type": t, "dx": dx, "dy": -dy,  # y of a position points up (assumed)
                 "opacity": resolve_number(g.get("opacity"), ctx, 1.0)}
            if t == "Dot":
                stroke = g.get("stroke") or {}
                size_raw = g.get("size", stroke.get("width", {"px": 10}))
                col_raw = g.get("color", stroke.get("color", "white"))
                e["size"] = self.length(size_raw, ctx)
                e["color"] = resolve_color(col_raw, ctx)
                if "opacity" in stroke:
                    e["opacity"] *= resolve_number(stroke.get("opacity"), ctx, 1.0)
            elif t == "Text":
                e["text"] = resolve_text(g.get("text"), ctx)
                e["font"] = self.font(g.get("font"), ctx)
                e["align"] = resolve_alignment(g.get("alignment"), ctx)
            elif t == "Image":
                path = self.image(g.get("image") or {})
                im = self._img_cache.get(path)
                if im is None:
                    im = np.asarray(Image.open(path).convert("RGBA"), dtype=float) / 255.0
                    self._img_cache[path] = im
                h, w = im.shape[:2]
                hs = g.get("hotSpot")
                if hs is None:
                    hx, hy = 0.5 * w, 0.5 * h
                else:
                    (x, ux), (y, uy) = resolve_point(hs, ctx)
                    hx = self.units.to_px(x, ux or "px", pc_base=w)
                    hy = self.units.to_px(y, uy or "px", pc_base=h)
                e["img"] = im
                e["hot"] = (hx, hy)
                e["tint"] = resolve_color(g.get("tint", "white"), ctx)
                e["blackTint"] = resolve_color(g.get("blackTint", "black"), ctx)
                e["alphaThreshold"] = resolve_number(g.get("alphaThreshold"), ctx, 0.0)
            else:
                raise Unsupported("graphic type %r" % t)
            out.append(e)
        return out


def marker_elements(sym):
    if "marker" not in sym:
        return copy.deepcopy(DEFAULT_MARKER["elements"])
    m = sym["marker"]
    if m is None:
        return []
    if isinstance(m, dict) and "elements" not in m:
        return copy.deepcopy(DEFAULT_MARKER["elements"])
    return m.get("elements") or []


# ---------------------------------------------------------------- drawing primitives

def set_rgba(cr, rgb, a):
    cr.set_source_rgba(rgb[0], rgb[1], rgb[2], a)


def path_polys(cr, polys):
    for poly in polys:
        for ring in poly:
            cr.move_to(*ring[0])
            for p in ring[1:]:
                cr.line_to(*p)
            cr.close_path()


def path_lines(cr, lines):
    for line in lines:
        cr.move_to(*line[0])
        for p in line[1:]:
            cr.line_to(*p)


def outline_path(cr, f):
    """Path along which a feature's stroke is drawn."""
    if f["lines"]:
        path_lines(cr, f["lines"])
    if f["polys"]:
        path_polys(cr, f["polys"])


def stroke_with(cr, st, width, rgb, alpha, dash=None, offset=0.0):
    if width is None or width <= 0 or alpha <= 0:
        cr.new_path()
        return
    cr.set_line_width(width)
    cr.set_line_cap(cairo.LINE_CAP_BUTT)
    cr.set_line_join(cairo.LINE_JOIN_MITER)
    if dash:
        if all(d >= 0 for d in dash) and sum(dash) > 0:
            cr.set_dash(dash, offset or 0.0)
    else:
        cr.set_dash([])
    set_rgba(cr, rgb, alpha)
    cr.stroke()
    cr.set_dash([])


_STIPPLE_CACHE = {}


def draw_fill(cr, f, fill, W, H):
    if fill is None or not f["polys"]:
        return
    a = fill["opacity"]
    if a <= 0:
        return
    rgb = fill["color"]
    special = any(k in fill for k in ("hatch", "stipple", "dotpattern"))
    if not special:
        path_polys(cr, f["polys"])
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        set_rgba(cr, rgb, a)
        cr.fill()
        return
    cr.save()
    path_polys(cr, f["polys"])
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    x0, y0, x1, y1 = cr.fill_extents()
    cr.clip()
    if "hatch" in fill:
        h = fill["hatch"]
        th = math.radians(h["angle"])
        d = (math.cos(th), math.sin(th))  # clockwise on screen from the +x axis (y down)
        n = (-d[1], d[0])
        corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
        proj = [c[0] * n[0] + c[1] * n[1] for c in corners]
        projd = [c[0] * d[0] + c[1] * d[1] for c in corners]
        dist = h["distance"]
        if dist > 0 and h["width"] > 0:
            k0 = math.floor(min(proj) / dist)
            k1 = math.ceil(max(proj) / dist)
            t0, t1 = min(projd) - 2, max(projd) + 2
            for k in range(k0, k1 + 1):
                p = k * dist
                cr.move_to(p * n[0] + t0 * d[0], p * n[1] + t0 * d[1])
                cr.line_to(p * n[0] + t1 * d[0], p * n[1] + t1 * d[1])
            cr.set_line_width(h["width"])
            cr.set_line_cap(cairo.LINE_CAP_BUTT)
            set_rgba(cr, rgb, a)
            cr.stroke()
    if "stipple" in fill:
        ratio = float(fill["stipple"]["ratio"])
        key = (ratio, rgb, W, H)
        surf = _STIPPLE_CACHE.get(key)
        if surf is None:
            rng = np.random.default_rng(20261114)
            mask = rng.random((H, W)) < ratio
            arr = np.zeros((H, W, 4), dtype=np.uint8)
            arr[mask, 0] = int(round(rgb[2] * 255))
            arr[mask, 1] = int(round(rgb[1] * 255))
            arr[mask, 2] = int(round(rgb[0] * 255))
            arr[mask, 3] = 255
            surf = cairo.ImageSurface.create_for_data(bytearray(arr.tobytes()), cairo.FORMAT_ARGB32, W, H, W * 4)
            _STIPPLE_CACHE[key] = surf
        cr.set_source_surface(surf, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_NEAREST)
        cr.paint_with_alpha(a)
    if "dotpattern" in fill:
        hz, vt = fill["dotpattern"]["h"], fill["dotpattern"]["v"]
        r = 1.0  # dot diameter 2 px (not defined by the text)
        if hz > 0 and vt > 0:
            i0, i1 = math.floor(x0 / hz) - 1, math.ceil(x1 / hz) + 1
            j0, j1 = math.floor(y0 / vt) - 1, math.ceil(y1 / vt) + 1
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    cx, cy = (i + 0.5) * hz, (j + 0.5) * vt
                    cr.new_sub_path()
                    cr.arc(cx, cy, r, 0, 2 * math.pi)
            set_rgba(cr, rgb, a)
            cr.fill()
    cr.restore()


def font_setup(cr, font):
    slant = cairo.FONT_SLANT_ITALIC if font["italic"] else cairo.FONT_SLANT_NORMAL
    weight = cairo.FONT_WEIGHT_BOLD if font["bold"] else cairo.FONT_WEIGHT_NORMAL
    cr.select_font_face(font["face"], slant, weight)
    cr.set_font_size(font["size_px"])
    fo = cairo.FontOptions()
    fo.set_hint_metrics(cairo.HINT_METRICS_OFF)
    fo.set_hint_style(cairo.HINT_STYLE_NONE)
    cr.set_font_options(fo)


def text_layout(cr, e, x, y):
    """Returns (origin_x, baseline_y, box) for a Text graphic anchored at (x, y)."""
    font = e["font"]
    font_setup(cr, font)
    asc, desc, _, _, _ = cr.font_extents()
    te = cr.text_extents(e["text"])
    adv = te.x_advance
    h, v = e["align"]
    ox = {"left": x, "center": x - adv / 2, "right": x - adv}.get(h, x - adv / 2)
    by = {"top": y + asc, "middle": y + (asc - desc) / 2, "bottom": y - desc}.get(v, y + (asc - desc) / 2)
    pad = font["outline"]["size"] if font["outline"] else 0.0
    box = (ox - pad, by - asc - pad, ox + adv + pad, by + desc + pad)
    return ox, by, box


def draw_text(cr, e, x, y):
    if not e["text"]:
        return
    ox, by, _ = text_layout(cr, e, x, y)
    font = e["font"]
    cr.move_to(ox, by)
    cr.text_path(e["text"])
    if font["outline"] and font["outline"]["size"] > 0:
        o = font["outline"]
        cr.set_line_width(2 * o["size"])
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        set_rgba(cr, o["color"], o["opacity"] * e["opacity"])
        cr.stroke_preserve()
    set_rgba(cr, font["color"], font["opacity"] * e["opacity"])
    cr.fill()


def image_surface(e):
    im = e["img"]
    rgb = im[..., :3]
    t = np.asarray(e["tint"])
    b = np.asarray(e["blackTint"])
    out = t * rgb + b * (1.0 - rgb)
    a = im[..., 3:4].copy()
    if e["alphaThreshold"] > 0:
        a[a < e["alphaThreshold"]] = 0.0  # /per/vector/image-alpha-test (permission)
    pm = np.clip(out * a, 0, 1)
    h, w = im.shape[:2]
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = np.round(pm[..., 2] * 255)
    arr[..., 1] = np.round(pm[..., 1] * 255)
    arr[..., 2] = np.round(pm[..., 0] * 255)
    arr[..., 3] = np.round(a[..., 0] * 255)
    return cairo.ImageSurface.create_for_data(bytearray(arr.tobytes()), cairo.FORMAT_ARGB32, w, h, w * 4)


def draw_graphic(cr, e, x, y):
    px, py = x + e["dx"], y + e["dy"]
    if e["type"] == "Dot":
        if e["size"] and e["size"] > 0:
            cr.new_path()
            cr.arc(px, py, e["size"] / 2.0, 0, 2 * math.pi)
            set_rgba(cr, e["color"], e["opacity"])
            cr.fill()
    elif e["type"] == "Text":
        draw_text(cr, e, px, py)
    elif e["type"] == "Image":
        s = image_surface(e)
        cr.save()
        cr.set_source_surface(s, px - e["hot"][0], py - e["hot"][1])
        cr.paint_with_alpha(e["opacity"])
        cr.restore()


def graphic_box(cr, e, x, y):
    px, py = x + e["dx"], y + e["dy"]
    if e["type"] == "Dot":
        r = (e["size"] or 0) / 2
        return (px - r, py - r, px + r, py + r)
    if e["type"] == "Text":
        if not e["text"]:
            return None
        return text_layout(cr, e, px, py)[2]
    if e["type"] == "Image":
        h, w = e["img"].shape[:2]
        return (px - e["hot"][0], py - e["hot"][1], px - e["hot"][0] + w, py - e["hot"][1] + h)
    return None


def marker_anchors(f):
    pts = list(f["pts"])
    for line in f["lines"]:
        pts.extend(line)
    if f["polys"]:
        pts.append(multipolygon_centroid(f["polys"]))
    return pts


# ---------------------------------------------------------------- coverage

def render_coverage(layer, sym, view, ctx_base, W, H, bbox):
    hdr, bands = layer["hdr"], layer["bands"]
    ncols, nrows = int(hdr["ncols"]), int(hdr["nrows"])
    cs = hdr["cellsize"]
    xll = hdr.get("xllcorner", hdr.get("xllcenter", 0) - cs / 2)
    yll = hdr.get("yllcorner", hdr.get("yllcenter", 0) - cs / 2)
    ytop = yll + nrows * cs
    minx, miny, maxx, maxy = bbox
    rx = (maxx - minx) / W
    ry = (maxy - miny) / H
    X = minx + (np.arange(W) + 0.5) * rx
    Y = maxy - (np.arange(H) + 0.5) * ry
    # fractional cell index, cell centres at integer positions; bilinear resampling
    fc = (X - xll) / cs - 0.5
    fr = (ytop - Y) / cs - 0.5
    inside = ((X >= xll) & (X <= xll + ncols * cs))[None, :] & ((Y >= yll) & (Y <= ytop))[:, None]
    fc = np.clip(fc, 0, ncols - 1)
    fr = np.clip(fr, 0, nrows - 1)
    c0 = np.floor(fc).astype(int)
    r0 = np.floor(fr).astype(int)
    c1 = np.minimum(c0 + 1, ncols - 1)
    r1 = np.minimum(r0 + 1, nrows - 1)
    tc = (fc - c0)[None, :]
    tr = (fr - r0)[:, None]
    props = {}
    for name, grid in bands.items():
        g00 = grid[r0][:, c0]
        g01 = grid[r0][:, c1]
        g10 = grid[r1][:, c0]
        g11 = grid[r1][:, c1]
        v = (g00 * (1 - tc) * (1 - tr) + g01 * tc * (1 - tr) + g10 * (1 - tc) * tr + g11 * tc * tr)
        v[~inside] = np.nan
        props[name] = v
    ctx = Ctx(view, ctx_base.layer_id, "coverage", props=props)
    fields = list(bands.keys())
    sc_raw = sym.get("singleChannel", {"property": fields[0]})
    value = resolve_number(sc_raw, ctx, None)
    value = np.broadcast_to(np.asarray(value, dtype=float), (H, W))
    cmap = resolve_value_map(sym.get("colorMap"), ctx, "color")
    if cmap is not None:
        rgb = apply_map(cmap, value)
    elif "colorChannels" in sym or len(fields) >= 3:
        cc = sym.get("colorChannels", [{"property": fields[0]}, {"property": fields[1]}, {"property": fields[2]}])
        comps = cc if isinstance(cc, list) else [cc.get("r"), cc.get("g"), cc.get("b")]
        rgb = np.stack([np.broadcast_to(np.asarray(resolve_number(c, ctx, 0.0), float), (H, W)) for c in comps], -1)
    else:
        rgb = np.repeat(value[..., None], 3, axis=-1)
    rgb = np.clip(rgb, 0, 1)
    alpha = np.ones((H, W))
    omap = resolve_value_map(sym.get("opacityMap"), ctx, "opacity")
    if omap is not None:
        alpha = alpha * apply_map(omap, value)
    if "alphaChannel" in sym:
        alpha = alpha * np.broadcast_to(np.asarray(resolve_number(sym["alphaChannel"], ctx, 1.0), float), (H, W))
    hs = sym.get("hillShading")
    if hs is not None:
        factor = resolve_number(hs.get("factor"), ctx, 1.0)
        sun = hs.get("sun") or {}
        az = math.radians(resolve_angle(sun.get("azimuth"), ctx, 315.0))
        el = math.radians(resolve_angle(sun.get("elevation"), ctx, 45.0))
        z = value
        # horizontal distance between neighbouring rendered samples, in metres
        dzdx = np.gradient(z, rx, axis=1)            # east
        dzdy = -np.gradient(z, ry, axis=0)           # north (rows go south)
        nx, ny, nz = -factor * dzdx, -factor * dzdy, np.ones_like(z)
        nl = np.sqrt(nx * nx + ny * ny + nz * nz)
        s = (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))
        shade = np.clip((nx * s[0] + ny * s[1] + nz * s[2]) / nl, 0, 1)
        hcm = resolve_value_map(hs.get("colorMap"), ctx, "color")
        if hcm is not None:
            rgb = apply_map(hcm, shade)
        else:
            rgb = rgb * shade[..., None]
        hom = resolve_value_map(hs.get("opacityMap"), ctx, "opacity")
        if hom is not None:
            alpha = alpha * apply_map(hom, shade)
    alpha = alpha * resolve_number(sym.get("opacity"), ctx, 1.0)
    bad = ~np.isfinite(value) | ~np.all(np.isfinite(rgb), axis=-1) | ~np.isfinite(alpha)
    alpha = np.where(bad, 0.0, np.clip(alpha, 0, 1))
    rgb = np.where(bad[..., None], 0.0, rgb)
    arr = np.zeros((H, W, 4), dtype=np.uint8)
    pm = rgb * alpha[..., None]
    arr[..., 0] = np.round(pm[..., 2] * 255)
    arr[..., 1] = np.round(pm[..., 1] * 255)
    arr[..., 2] = np.round(pm[..., 0] * 255)
    arr[..., 3] = np.round(alpha * 255)
    return cairo.ImageSurface.create_for_data(bytearray(arr.tobytes()), cairo.FORMAT_ARGB32, W, H, W * 4)


# ---------------------------------------------------------------- view rendering

def render_view(case_dir, style, view, out_path):
    W, H = int(view["width"]), int(view["height"])
    bbox = view["bbox"]
    minx, miny, maxx, maxy = bbox
    rx = (maxx - minx) / W
    ry = (maxy - miny) / H
    units = Units(float(view.get("pixelSize_mm", 0.28)), rx)
    res = Resolver(units, case_dir)
    rules = style.get("stylingRules", [])

    def tr(c):
        return ((c[0] - minx) / rx, (maxy - c[1]) / ry)

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surf)
    bg = view.get("background", "white")
    set_rgba(cr, resolve_color(bg, None), 1.0)
    cr.paint()

    items = []    # (zOrder, layer index, seq, item)
    labels = []   # label candidates
    seq = 0
    for li, lname in enumerate(view["layers"]):
        gj = os.path.join(case_dir, lname + ".geojson")
        if os.path.exists(gj):
            feats = load_geojson(gj, tr)
            dims = {f["dims"] for f in feats}
            ldims = dims.pop() if len(dims) == 1 else None
            for f in feats:
                ctx = Ctx(view, lname, "vector", props=f["props"], feature=f, layer_dims=ldims)
                sym = resolve_symbolizer(rules, ctx)
                if not resolve_bool(sym.get("visibility"), ctx, True):
                    continue
                it = {"kind": "vector", "f": f,
                      "opacity": resolve_number(sym.get("opacity"), ctx, 1.0),
                      "fill": res.fill(sym["fill"] if "fill" in sym else DEFAULT_FILL, ctx),
                      "stroke": res.stroke(sym["stroke"] if "stroke" in sym else DEFAULT_STROKE, ctx),
                      "marker": res.graphics(marker_elements(sym), ctx)}
                z = resolve_number(sym.get("zOrder"), ctx, 1.0)
                items.append((z, li, seq, it))
                lab = sym.get("label")
                if lab and lab.get("elements"):
                    pl = lab.get("placement") or {}
                    els = res.graphics(lab.get("elements"), ctx)
                    minsp = res.length(pl.get("minSpacing"), ctx, None)
                    if f["pts"]:
                        anchors = list(f["pts"])
                    elif f["polys"]:
                        anchors = [multipolygon_centroid(f["polys"])]
                    else:
                        anchors = []
                        for line in f["lines"]:
                            anchors.extend(line_points_at(line, minsp, W, H))
                    labels.append({"priority": resolve_number(pl.get("priority"), ctx, 0.0),
                                   "seq": seq, "anchors": anchors, "elements": els,
                                   "minSpacing": minsp,
                                   "key": tuple(e.get("text", "") for e in els)})
                seq += 1
            continue
        bandfiles = sorted(glob.glob(os.path.join(case_dir, lname + ".*.asc")))
        if bandfiles:
            hdr = None
            bands = {}
            for bf in bandfiles:
                band = os.path.basename(bf)[len(lname) + 1:-4]
                hdr, bands[band] = load_asc(bf)
            layer = {"hdr": hdr, "bands": bands}
            # selectors evaluated with the cell values as arrays
            ctx_sel = Ctx(view, lname, "coverage", props={})
            ctx_sel.props = _LazyBands(layer)
            sym = resolve_symbolizer(rules, ctx_sel, coverage=True)
            if not resolve_bool(sym.get("visibility"), ctx_sel, True):
                continue
            z = resolve_number(sym.get("zOrder"), ctx_sel, 1.0)
            items.append((z, li, seq, {"kind": "coverage", "layer": layer, "sym": sym, "lname": lname}))
            seq += 1
            continue
        raise FileNotFoundError("layer %s" % lname)

    items.sort(key=lambda t: (t[0], t[1], t[2]))
    # group by zOrder: casings of the group first
    i = 0
    while i < len(items):
        j = i
        while j < len(items) and items[j][0] == items[i][0]:
            j += 1
        group = items[i:j]
        for _, _, _, it in group:
            if it["kind"] != "vector" or not it["stroke"] or not it["stroke"]["casing"]:
                continue
            st = it["stroke"]
            cs = st["casing"]
            f = it["f"]
            if not (f["lines"] or f["polys"]):
                continue
            outline_path(cr, f)
            # casing is a StrokeStyling (no dash members): drawn solid
            stroke_with(cr, st, (st["width"] or 0) + 2 * (cs["width"] or 0), cs["color"],
                        cs["opacity"] * it["opacity"])
        for _, _, _, it in group:
            if it["kind"] == "coverage":
                ctxb = Ctx(view, it["lname"], "coverage")
                s = render_coverage(it["layer"], it["sym"], view, ctxb, W, H, bbox)
                cr.set_source_surface(s, 0, 0)
                cr.paint()
                continue
            f = it["f"]
            if it["opacity"] <= 0:
                continue
            cr.push_group()
            draw_fill(cr, f, it["fill"], W, H)
            st = it["stroke"]
            if st and (f["lines"] or f["polys"]):
                outline_path(cr, f)
                stroke_with(cr, st, st["width"], st["color"], st["opacity"], st.get("dash"), st.get("dashOffset"))
                if st["center"]:
                    c = st["center"]
                    outline_path(cr, f)
                    stroke_with(cr, st, c["width"], c["color"], c["opacity"])
            if it["marker"]:
                for (x, y) in marker_anchors(f):
                    for e in it["marker"]:
                        draw_graphic(cr, e, x, y)
            cr.pop_group_to_source()
            cr.paint_with_alpha(it["opacity"])
        i = j

    # label pass (on top of everything; symbolizer opacity not applied)
    labels.sort(key=lambda L: (-float(L["priority"]), L["seq"]))
    placed_boxes = []
    placed_anchors = []
    for L in labels:
        for (x, y) in L["anchors"]:
            if not (0 <= x <= W and 0 <= y <= H):
                continue
            boxes = [b for b in (graphic_box(cr, e, x, y) for e in L["elements"]) if b]
            if not boxes:
                continue
            if any(_overlap(b, p) for b in boxes for p in placed_boxes):
                continue
            if L["minSpacing"]:
                if any(k == L["key"] and math.hypot(ax - x, ay - y) < L["minSpacing"]
                       for (k, ax, ay) in placed_anchors):
                    continue
            placed_boxes.extend(boxes)
            placed_anchors.append((L["key"], x, y))
            for e in L["elements"]:
                draw_graphic(cr, e, x, y)

    surf.flush()
    buf = np.ndarray((H, surf.get_stride() // 4, 4), dtype=np.uint8, buffer=surf.get_data())[:, :W]
    a = buf[..., 3:4].astype(float) / 255.0
    rgb = np.where(a > 0, buf[..., [2, 1, 0]].astype(float) / np.maximum(a, 1e-9), 0)
    Image.fromarray(np.clip(np.round(rgb), 0, 255).astype(np.uint8), "RGB").save(out_path)


class _LazyBands(dict):
    """Cell values for coverage selectors (whole-grid arrays)."""

    def __init__(self, layer):
        super().__init__()
        self.layer = layer

    def get(self, k, d=None):
        b = self.layer["bands"].get(k)
        return b if b is not None else d


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def main():
    cases_dir = sys.argv[1]
    out_dir = sys.argv[2]
    only = set(sys.argv[3:])
    os.makedirs(out_dir, exist_ok=True)
    ok, failed = [], []
    for case in sorted(os.listdir(cases_dir)):
        cdir = os.path.join(cases_dir, case)
        sp = os.path.join(cdir, "style.cs.json")
        if not os.path.exists(sp) or (only and case not in only):
            continue
        style = json.load(open(sp, encoding="utf-8"))
        for vp in sorted(glob.glob(os.path.join(cdir, "view-*.json"))):
            n = os.path.basename(vp)[5:-5]
            view = json.load(open(vp, encoding="utf-8"))
            out = os.path.join(out_dir, "%s-%s.png" % (case, n))
            try:
                render_view(cdir, style, view, out)
                ok.append(out)
            except Exception as ex:  # report and continue
                import traceback
                traceback.print_exc()
                failed.append((case, n, repr(ex)))
    print("rendered", len(ok))
    for f in failed:
        print("FAILED", f)


if __name__ == "__main__":
    main()
