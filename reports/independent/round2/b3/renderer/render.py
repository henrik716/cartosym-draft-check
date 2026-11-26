"""Independent CartoSym-JSON renderer, written from the requirement text only.

usage: uv run --no-project --with numpy --with pillow --with resvg-py python renderer/render.py [case-01 ...]
"""
import io
import itertools
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import resvg_py

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "cases")
OUT = os.path.join(ROOT, "out")
SS = 4                      # supersampling factor for all drawing
MM_PX = 0.28                # standard pixel (view-1.json pixelSize_mm)
FONT_DIR = "C:/Windows/Fonts"
FONT_FILES = {(False, False): "arial.ttf", (True, False): "arialbd.ttf",
              (False, True): "ariali.ttf", (True, True): "arialbi.ttf"}
NAMED = {"white": (255, 255, 255), "black": (0, 0, 0)}
DEFAULT_DOT = {"type": "Dot", "size": {"px": 10}, "color": "white"}
DEFAULT_FONT = {"face": "Arial", "size_px": 16.0, "bold": False, "italic": False,
                "opacity": 1.0, "color": (0, 0, 0), "outline": None}
HFRAC = {"left": 0.0, "center": 0.5, "right": 1.0}
_font_cache = {}
_order = itertools.count()


# ---------------------------------------------------------------- units, colours
def parse_color(c, default=(0, 0, 0)):
    if c is None:
        return default
    if isinstance(c, str):
        if c.startswith("#"):
            h = c[1:]
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        return NAMED[c]
    return tuple(int(v) for v in c[:3])


def length_px(v, sd, em=16.0):
    """uom-qualified length to pixels; a plain number is pixels."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if "px" in v:
        return float(v["px"])
    if "mm" in v:
        return float(v["mm"]) / MM_PX
    if "pt" in v:
        return float(v["pt"]) * (25.4 / 72) / MM_PX
    if "in" in v:
        return float(v["in"]) * 25.4 / MM_PX
    if "cm" in v:
        return float(v["cm"]) * 10 / MM_PX
    if "m" in v:                       # ground metres at the map scale 1:sd
        return float(v["m"]) * 1000.0 / (MM_PX * sd)
    if "ft" in v:
        return float(v["ft"]) * 0.3048 * 1000.0 / (MM_PX * sd)
    if "em" in v:
        return float(v["em"]) * em
    raise ValueError("unit " + json.dumps(v))


def pos_xy(p, sd, em=16.0):
    if not p:
        return 0.0, 0.0
    return length_px(p.get("x", 0), sd, em), length_px(p.get("y", 0), sd, em)


# ---------------------------------------------------------------- expressions
def sysval(sid, F):
    return {"dataLayer.id": F.get("layer_id"), "dataLayer.type": F.get("layer_type"),
            "dataLayer.featuresGeometryDimension": F.get("dim"), "viz.sd": F.get("sd"),
            "viz.timeInterval.start.date": F.get("start"),
            "viz.timeInterval.end.date": F.get("end"), "viz.date": F.get("date")}.get(sid)


def _cmp(op, a, b):
    if a is None or b is None:
        return None
    try:
        return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b,
                "<=": a <= b, ">=": a >= b}[op]
    except TypeError:
        return None


def num_text(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def ev(e, F):
    if isinstance(e, dict):
        if "sysId" in e:
            return sysval(e["sysId"], F)
        if "property" in e:
            return F["props"].get(e["property"])
        if "op" in e:
            op = e["op"]
            args = e.get("args", [])
            if op in ("and", "or"):
                vals = [ev(a, F) for a in args]
                if op == "and":
                    if any(v is False for v in vals):
                        return False
                    return None if any(v is None for v in vals) else True
                if any(v is True for v in vals):
                    return True
                return None if any(v is None for v in vals) else False
            if op == "not":
                v = ev(args[0], F)
                return None if v is None else (not v)
            vals = [ev(a, F) for a in args]
            if op in ("=", "<>", "<", ">", "<=", ">="):
                return _cmp(op, vals[0], vals[1])
            if op == "-":
                return None if None in vals else vals[0] - vals[1]
            if op == "concatenate":
                return None if None in vals else "".join(num_text(v) for v in vals)
            raise ValueError("operator " + op)
        return e
    if isinstance(e, list):
        return [ev(x, F) for x in e]
    return e


def text_of(e, F):
    v = ev(e, F)
    return None if v is None else num_text(v)


# ---------------------------------------------------------------- style cascade
def merge_marker(base, v):
    """base: current marker (absent = {} meaning default, None = no marker)."""
    if v is None:
        return None
    if not v.get("alter"):
        return {k: vv for k, vv in v.items() if k != "alter"}
    if base is None:
        els = []
        res = {}
    else:
        res = dict(base)
        els = list(res["elements"]) if "elements" in res else [dict(DEFAULT_DOT)]
    for k, vv in v.items():
        if k == "alter":
            continue
        if k == "elements" and isinstance(vv, dict) and "index" in vv:
            idx = vv["index"]
            if idx < len(els):
                els[idx] = vv["value"]
            else:               # index beyond the array: appended (reading chosen, see notes)
                els.append(vv["value"])
            res["elements"] = els
        else:
            res[k] = vv
    return res


def merge_obj(base, v):
    res = dict(base) if isinstance(base, dict) else {}
    for k, vv in v.items():
        if k == "alter":
            continue
        if isinstance(vv, dict) and vv.get("alter"):
            res[k] = merge_obj(res.get(k), vv)
        else:
            res[k] = vv
    return res


def merge_symbolizer(state, sym):
    for k, v in sym.items():
        if k == "alter":
            continue
        if k == "marker":
            state["marker"] = merge_marker(state.get("marker", {}), v)
        elif isinstance(v, dict) and v.get("alter"):
            state[k] = merge_obj(state.get(k), v)
        else:
            state[k] = v


def apply_rules(rules, F, state):
    for r in rules:
        sel = r.get("selector")
        if sel is not None and ev(sel, F) is not True:
            continue
        if r.get("symbolizer"):
            merge_symbolizer(state, r["symbolizer"])
        apply_rules(r.get("nestedRules", []), F, state)


def marker_elements(marker):
    if marker is None:
        return []
    if "elements" not in marker:
        return [dict(DEFAULT_DOT)]
    return list(marker["elements"])


# ---------------------------------------------------------------- fonts
def get_font(bold, italic, px_ss):
    key = (bold, italic, round(px_ss * 100))
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(os.path.join(FONT_DIR, FONT_FILES[(bold, italic)]), size=px_ss)
    return _font_cache[key]


def resolve_font(el_font, sd):
    f = dict(DEFAULT_FONT)
    if el_font:
        if "size" in el_font:
            f["size_px"] = length_px(el_font["size"], sd, 16.0)
        for k in ("bold", "italic", "opacity"):
            if k in el_font:
                f[k] = el_font[k]
        if "color" in el_font:
            f["color"] = parse_color(el_font["color"])
        if "outline" in el_font:
            o = el_font["outline"]
            f["outline"] = {"size": length_px(o.get("size", 0), sd),
                            "opacity": o.get("opacity", 1.0),
                            "color": parse_color(o.get("color", "white"))}
    return f


def text_metrics(text, fp):
    """Returns (font at SS scale, ascent, descent, width) in 1x pixels."""
    font = get_font(fp["bold"], fp["italic"], fp["size_px"] * SS)
    asc, desc = font.getmetrics()
    return font, asc / SS, desc / SS, font.getlength(text) / SS


def baseline_offset(valign, asc, desc):
    """Baseline below the anchor, screen y down, for the vertical alignment."""
    if valign == "top":
        return asc
    if valign == "bottom":
        return -desc
    return (asc - desc) / 2.0


# ---------------------------------------------------------------- canvas and primitives
class Canvas:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.C = np.full((H * SS, W * SS, 3), 255.0, np.float32)

    def paint(self, x0, y0, a, col, alpha=1.0):
        """a: coverage (h,w) at SS scale with top-left (x0,y0) in SS pixels; col: rgb or (h,w,3)."""
        h, w = a.shape
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(self.C.shape[1], x0 + w), min(self.C.shape[0], y0 + h)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        a2 = a[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0] * alpha
        if float(a2.max()) <= 0:
            return
        a3 = a2[..., None].astype(np.float32)
        if np.ndim(col) == 1:
            c = np.asarray(col, np.float32)
        else:
            c = np.asarray(col, np.float32)[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
        reg = self.C[cy0:cy1, cx0:cx1]
        self.C[cy0:cy1, cx0:cx1] = reg * (1 - a3) + c * a3


def bbox_ss(pts, pad=2):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (int(math.floor(min(xs))) - pad, int(math.floor(min(ys))) - pad,
            int(math.ceil(max(xs))) + pad, int(math.ceil(max(ys))) + pad)


def poly_patch(polys_ss):
    """One polygon (list of rings, SS coords): even-odd fill of its rings."""
    pts = [p for r in polys_ss for p in r]
    x0, y0, x1, y1 = bbox_ss(pts)
    w, h = x1 - x0, y1 - y0
    acc = np.zeros((h, w), bool)
    for ring in polys_ss:
        im = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im).polygon([(x - x0, y - y0) for x, y in ring], fill=255)
        acc ^= np.asarray(im) > 0
    return x0, y0, acc.astype(np.float32)


def line_patch(lines_ss, width_ss):
    pts = [p for l in lines_ss for p in l]
    x0, y0, x1, y1 = bbox_ss(pts, pad=int(width_ss) + 3)
    w, h = x1 - x0, y1 - y0
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    lw = max(1, int(round(width_ss)))
    r = width_ss / 2.0
    for l in lines_ss:
        for (ax, ay), (bx, by) in zip(l[:-1], l[1:]):
            d.line([(ax - x0, ay - y0), (bx - x0, by - y0)], fill=255, width=lw)
        for x, y in l:                       # round joins and caps
            d.ellipse([x - x0 - r, y - y0 - r, x - x0 + r, y - y0 + r], fill=255)
    return x0, y0, np.asarray(im).astype(np.float32) / 255.0


def disk_dilate(arr, r):
    """Grow a coverage patch by radius r (SS pixels). Result is (h+2k, w+2k), k = ceil(r)."""
    k = int(math.ceil(r))
    h, w = arr.shape
    base = np.pad(arr, k)
    out = np.zeros_like(base)
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            if dx * dx + dy * dy <= r * r + 1e-9:
                shifted = np.roll(np.roll(base, dy, 0), dx, 1)
                np.maximum(out, shifted, out=out)
    return out, k


def sat_overlap(A, B):
    for poly in (A, B):
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            nx, ny = y2 - y1, x1 - x2
            pa = [nx * x + ny * y for x, y in A]
            pb = [nx * x + ny * y for x, y in B]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


# ---------------------------------------------------------------- geometry helpers
class Mapping:
    def __init__(self, view):
        self.minx, self.miny, self.maxx, self.maxy = view["bbox"]
        self.W, self.H = view["width"], view["height"]
        self.resx = (self.maxx - self.minx) / self.W
        self.resy = (self.maxy - self.miny) / self.H

    def xy(self, x, y):
        return ((x - self.minx) / self.resx, (self.maxy - y) / self.resy)


def polyline_tools(pts):
    cum = [0.0]
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        cum.append(cum[-1] + math.hypot(bx - ax, by - ay))
    total = cum[-1]

    def at(s):
        s = min(max(s, 0.0), total)
        for i in range(len(pts) - 1):
            if s <= cum[i + 1] or i == len(pts) - 2:
                seg = cum[i + 1] - cum[i]
                t = 0.0 if seg == 0 else (s - cum[i]) / seg
                (ax, ay), (bx, by) = pts[i], pts[i + 1]
                dx, dy = bx - ax, by - ay
                n = math.hypot(dx, dy) or 1.0
                return (ax + t * dx, ay + t * dy), (dx / n, dy / n)
        raise RuntimeError("empty polyline")
    return total, at


def centroid(ring):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring[:-1], ring[1:]):
        cr = x0 * y1 - x1 * y0
        a += cr
        cx += (x0 + x1) * cr
        cy += (y0 + y1) * cr
    if abs(a) < 1e-12:
        return (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
    return cx / (3 * a), cy / (3 * a)


# ---------------------------------------------------------------- images
def load_image_native(path):
    if path.lower().endswith(".svg"):
        text = open(path, encoding="utf8").read()
        w = float(re.search(r'<svg[^>]*\swidth="([\d.]+)"', text).group(1))
        h = float(re.search(r'<svg[^>]*\sheight="([\d.]+)"', text).group(1))
        return {"svg": text, "w": w, "h": h}
    im = Image.open(path).convert("RGBA")
    return {"img": im, "w": im.size[0], "h": im.size[1]}


def rasterize_image(native, w_ss, h_ss):
    if "svg" in native:
        png = resvg_py.svg_to_bytes(svg_string=native["svg"], width=w_ss, height=h_ss)
        im = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    else:
        im = native["img"].resize((w_ss, h_ss), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0


def draw_dot(cv, el, anchor, op, sd):
    cx, cy = anchor[0] + pos_xy(el.get("position"), sd)[0], anchor[1] + pos_xy(el.get("position"), sd)[1]
    size = length_px(el.get("size", {"px": 10}), sd)
    if size <= 0:
        return
    col = parse_color(el.get("color", "white"), (255, 255, 255))
    r = size / 2.0
    x0, y0 = int(math.floor((cx - r) * SS)) - 2, int(math.floor((cy - r) * SS)) - 2
    d = int(math.ceil(size * SS)) + 6
    im = Image.new("L", (d, d), 0)
    ImageDraw.Draw(im).ellipse([(cx - r) * SS - x0, (cy - r) * SS - y0,
                                (cx + r) * SS - x0, (cy + r) * SS - y0], fill=255)
    cv.paint(x0, y0, np.asarray(im).astype(np.float32) / 255.0, col, op)


def draw_image(cv, el, anchor, op, case_dir, sd):
    cx, cy = anchor[0] + pos_xy(el.get("position"), sd)[0], anchor[1] + pos_xy(el.get("position"), sd)[1]
    img = el["image"]
    native = load_image_native(os.path.normpath(os.path.join(case_dir, img["path"])))
    w0, h0 = native["w"], native["h"]
    size = el.get("size")
    if size is None:
        wd, hd = float(w0), float(h0)
    elif "x" in size or "y" in size:
        wd = length_px(size["x"], sd) if "x" in size else None
        hd = length_px(size["y"], sd) if "y" in size else None
        if wd is None:
            wd = hd * w0 / h0
        if hd is None:
            hd = wd * h0 / w0
    else:
        wd = hd = length_px(size, sd)
    hs = el.get("hotSpot", [{"pc": 50}, {"pc": 50}])

    def hot(v, drawn, nat):
        if isinstance(v, dict) and "pc" in v:
            return v["pc"] / 100.0 * drawn
        if isinstance(v, (int, float)):          # pixels of the image file
            return v * drawn / nat
        return length_px(v, sd)
    hx, hy = hot(hs[0], wd, w0), hot(hs[1], hd, h0)
    wss, hss = max(1, int(round(wd * SS))), max(1, int(round(hd * SS)))
    rgba = rasterize_image(native, wss, hss)
    tint = np.array(parse_color(el.get("tint", "white"), (255, 255, 255)), np.float32) / 255.0
    black = np.array(parse_color(el.get("blackTint", "black")), np.float32) / 255.0
    v = rgba[..., :3]
    rgb = (tint * v + black * (1 - v)) * 255.0
    cv.paint(int(round((cx - hx) * SS)), int(round((cy - hy) * SS)), rgba[..., 3], rgb, op)


def point_text_patch(text, fp, ax, ay, align):
    """Text box placed by its alignment at the 1x anchor. Returns SS patch (x0, y0, arr)."""
    font, asc, desc, w1 = text_metrics(text, fp)
    x0 = ax - w1 * HFRAC[align[0]]
    base = ay + baseline_offset(align[1], asc, desc)
    fx0, fy0 = int(math.floor(x0 * SS)) - 6, int(math.floor((base - asc) * SS)) - 6
    fx1, fy1 = int(math.ceil((x0 + w1) * SS)) + 12, int(math.ceil((base + desc) * SS)) + 12
    im = Image.new("L", (fx1 - fx0, fy1 - fy0), 0)
    ImageDraw.Draw(im).text((x0 * SS - fx0, base * SS - fy0), text, font=font, fill=255, anchor="ls")
    return fx0, fy0, np.asarray(im).astype(np.float32) / 255.0


def paint_text(cv, text, fp, patch, op):
    fx0, fy0, a = patch
    if fp["outline"]:
        o = fp["outline"]
        dil, k = disk_dilate(a, o["size"] * SS)
        cv.paint(fx0 - k, fy0 - k, dil, o["color"], op * o["opacity"])
    cv.paint(fx0, fy0, a, fp["color"], op * fp["opacity"])


def draw_marker_text(cv, el, F, anchor, op, sd):
    text = text_of(el.get("text"), F)
    if not text:
        return
    fp = resolve_font(el.get("font"), sd)
    px, py = pos_xy(el.get("position"), sd, fp["size_px"])
    patch = point_text_patch(text, fp, anchor[0] + px, anchor[1] + py, el.get("alignment", ["left", "top"]))
    paint_text(cv, text, fp, patch, op)


# ---------------------------------------------------------------- coverage
def read_asc(path):
    toks = open(path, encoding="utf8").read().split()
    hdr, i = {}, 0
    while toks[i][0].isalpha():
        hdr[toks[i].lower()] = float(toks[i + 1])
        i += 2
    nrows, ncols = int(hdr["nrows"]), int(hdr["ncols"])
    z = np.array(toks[i:], dtype=np.float64).reshape(nrows, ncols)
    return {"z": z, "nodata": hdr.get("nodata_value", -9999), "xll": hdr["xllcorner"],
            "yll": hdr["yllcorner"], "cs": hdr["cellsize"], "nrows": nrows, "ncols": ncols}


def paint_coverage(cv, M, grid, state, op):
    z = grid["z"]
    valid = z != grid["nodata"]
    cs = grid["cs"]
    z2 = np.where(valid, z, z[valid].mean())
    # colour per cell from singleChannel through colorMap
    cmap = sorted(state.get("colorMap", []), key=lambda e: float(e[0]))
    vals = np.array([float(e[0]) for e in cmap])
    cols = np.array([parse_color(e[1]) for e in cmap], float)
    rgb = np.stack([np.interp(z2, vals, cols[:, k]) for k in range(3)], axis=-1)
    hs = state.get("hillShading") or {}
    factor = hs.get("factor", 0)
    if factor and "colorMap" not in hs:       # hill shading multiplies the cell colour
        gr, gc = np.gradient(z2, cs)          # per metre; rows run south, columns east
        nx, ny, nz = -factor * gc, factor * gr, np.ones_like(z2)
        nrm = np.sqrt(nx * nx + ny * ny + nz * nz)
        nx, ny, nz = nx / nrm, ny / nrm, nz / nrm
        sun = hs.get("sun", {"azimuth": 315.0, "elevation": 45.0})
        az, el = math.radians(sun["azimuth"]), math.radians(sun["elevation"])
        Lx, Ly, Lz = math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)
        shade = np.clip(nx * Lx + ny * Ly + nz * Lz, 0.0, 1.0)
        rgb = rgb * shade[..., None]
    H, W = cv.H * SS, cv.W * SS
    ys, xs = np.mgrid[0:H, 0:W]
    X = M.minx + (xs + 0.5) / SS * M.resx
    Y = M.maxy - (ys + 0.5) / SS * M.resy
    col = np.floor((X - grid["xll"]) / cs).astype(int)
    row = np.floor((grid["yll"] + grid["nrows"] * cs - Y) / cs).astype(int)
    inside = (col >= 0) & (col < grid["ncols"]) & (row >= 0) & (row < grid["nrows"])
    rc = np.clip(row, 0, grid["nrows"] - 1)
    cc = np.clip(col, 0, grid["ncols"] - 1)
    ok = inside & valid[rc, cc]
    cv.paint(0, 0, ok.astype(np.float32), rgb[rc, cc], float(op))


# ---------------------------------------------------------------- labels
def point_label(pt, F, elements, prio, op, sd, case_dir):
    """Candidate for a label on a point (or polygon centroid). None if it has no text."""
    parts, box = [], None
    for el in elements:
        if el.get("type") == "Text":
            text = text_of(el.get("text"), F)
            if not text:
                return None
            fp = resolve_font(el.get("font"), sd)
            px, py = pos_xy(el.get("position"), sd, fp["size_px"])
            align = el.get("alignment", ["left", "top"])
            font, asc, desc, w1 = text_metrics(text, fp)
            x0 = pt[0] + px - w1 * HFRAC[align[0]]
            base = pt[1] + py + baseline_offset(align[1], asc, desc)
            pad = fp["outline"]["size"] if fp["outline"] else 0
            bx = [(x0 - pad, base - asc - pad), (x0 + w1 + pad, base - asc - pad),
                  (x0 + w1 + pad, base + desc + pad), (x0 - pad, base + desc + pad)]
            box = bx if box is None else _box_union(box, bx)
            parts.append(("text", (text, fp, pt[0] + px, pt[1] + py, align)))
        elif el.get("type") == "Dot":
            size = length_px(el.get("size", {"px": 10}), sd)
            px, py = pos_xy(el.get("position"), sd)
            r = size / 2
            bx = [(pt[0] + px - r, pt[1] + py - r), (pt[0] + px + r, pt[1] + py - r),
                  (pt[0] + px + r, pt[1] + py + r), (pt[0] + px - r, pt[1] + py + r)]
            box = bx if box is None else _box_union(box, bx)
            parts.append(("dot", el))
        else:
            return None
    if box is None:
        return None

    def draw(cv):
        for kind, d in parts:
            if kind == "dot":
                draw_dot(cv, d, pt, op, sd)
            else:
                text, fp, ax, ay, align = d
                paint_text(cv, text, fp, point_text_patch(text, fp, ax, ay, align), op)
    return {"prio": prio, "order": next(_order), "box": box, "draw": draw}


def _box_union(a, b):
    xs = [p[0] for p in a + b]
    ys = [p[1] for p in a + b]
    return [(min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))]


def join_chains(lines):
    """Join lines that meet at their end points into chains (greedy, one chain per run)."""
    used = [False] * len(lines)
    chains = []

    def same(p, q):
        return abs(p[0] - q[0]) < 1e-6 and abs(p[1] - q[1]) < 1e-6
    for i in range(len(lines)):
        if used[i]:
            continue
        used[i] = True
        chain = list(lines[i])
        grow = True
        while grow:
            grow = False
            for j in range(len(lines)):
                if used[j]:
                    continue
                s = lines[j]
                if same(chain[-1], s[0]):
                    chain = chain + s[1:]
                elif same(chain[-1], s[-1]):
                    chain = chain + list(reversed(s))[1:]
                elif same(chain[0], s[-1]):
                    chain = s[:-1] + chain
                elif same(chain[0], s[0]):
                    chain = list(reversed(s))[:-1] + chain
                else:
                    continue
                used[j] = True
                grow = True
        chains.append(chain)
    return chains


def line_label_candidates(chain, F, elements, placement, prio, op, sd):
    """Repetitions of one label along a joined line, every minSpacing (measured between anchors)."""
    total, at = polyline_tools(chain)
    out = []
    text_el = [el for el in elements if el.get("type") == "Text"]
    if total <= 0 or not text_el:
        return out
    el = text_el[0]                          # one text per line label in these cases
    text = text_of(el.get("text"), F)
    if not text:
        return out
    fp = resolve_font(el.get("font"), sd)
    font, asc, desc, w1 = text_metrics(text, fp)
    px, py = pos_xy(el.get("position"), sd, fp["size_px"])
    align = el.get("alignment", ["left", "top"])
    tx0 = -w1 * HFRAC[align[0]]
    ty_b = baseline_offset(align[1], asc, desc)
    if total < w1:                           # rec: omit a label on a line shorter than the label
        return out
    minsp = placement.get("minSpacing")
    if minsp:
        k = int(total // minsp) + 2
        centres = [total / 2 + j * minsp for j in range(-k, k + 1)]
    else:
        centres = [total / 2]
    adv = [font.getlength(text[:i]) / SS for i in range(len(text) + 1)]
    for sc in centres:
        if sc < 0 or sc > total:
            continue
        _, t = at(sc)
        dr = 1 if (t[0] > 0 or (t[0] == 0 and t[1] < 0)) else -1
        a, b = sc + dr * (px + tx0), sc + dr * (px + tx0 + w1)
        if min(a, b) < 0 or max(a, b) > total:   # text must lie on the line
            continue
        P0, t0 = at(sc)
        d0 = (dr * t0[0], dr * t0[1])
        up0 = (d0[1], -d0[0])
        box = []
        for tx, ty in ((tx0, ty_b - asc), (tx0 + w1, ty_b - asc), (tx0 + w1, ty_b + desc), (tx0, ty_b + desc)):
            box.append((P0[0] + d0[0] * (px + tx) + up0[0] * (py - ty),
                        P0[1] + d0[1] * (px + tx) + up0[1] * (py - ty)))

        def draw(cv, sc=sc, dr=dr):
            if fp["outline"]:
                pass  # outline on glyph-by-glyph text: see draw below
            glyphs = []
            for i, ch in enumerate(text):
                if ch == " ":
                    continue
                s_i = sc + dr * (px + tx0 + adv[i])
                P, tt = at(s_i)
                di = (dr * tt[0], dr * tt[1])
                upi = (di[1], -di[0])
                Qx = P[0] + upi[0] * (py - ty_b)
                Qy = P[1] + upi[1] * (py - ty_b)
                gx, gy, arr = glyph_patch(ch, fp, Qx, Qy, di, (-upi[0], -upi[1]))
                glyphs.append((gx, gy, arr))
            if not glyphs:
                return
            gx0 = min(g[0] for g in glyphs)
            gy0 = min(g[1] for g in glyphs)
            gx1 = max(g[0] + g[2].shape[1] for g in glyphs)
            gy1 = max(g[1] + g[2].shape[0] for g in glyphs)
            acc = np.zeros((gy1 - gy0, gx1 - gx0), np.float32)
            for gx, gy, arr in glyphs:
                sub = acc[gy - gy0:gy - gy0 + arr.shape[0], gx - gx0:gx - gx0 + arr.shape[1]]
                np.maximum(sub, arr, out=sub)
            paint_text(cv, text, fp, (gx0, gy0, acc), op)
        out.append({"prio": prio, "order": next(_order), "box": box, "draw": draw})
    return out


def glyph_patch(ch, fp, Qx, Qy, d, n):
    """A glyph with its pen origin at the 1x point Q; x runs along d, y along n (both unit vectors)."""
    font, asc, desc, _ = text_metrics(ch, fp)
    adv = font.getlength(ch)
    pad = 6
    gw = int(math.ceil(adv)) + 2 * pad
    gh = int(math.ceil((asc + desc) * SS)) + 2 * pad
    gx0, gy0 = pad, pad + asc * SS
    im = Image.new("L", (gw, gh), 0)
    ImageDraw.Draw(im).text((gx0, gy0), ch, font=font, fill=255, anchor="ls")
    QX, QY = Qx * SS, Qy * SS
    corners = []
    for gx, gy in ((-gx0, -gy0), (gw - gx0, -gy0), (-gx0, gh - gy0), (gw - gx0, gh - gy0)):
        corners.append((QX + gx * d[0] + gy * n[0], QY + gx * d[1] + gy * n[1]))
    ox0, oy0, ox1, oy1 = bbox_ss(corners, pad=2)
    ow, oh = ox1 - ox0, oy1 - oy0
    c = (ox0 - QX) * d[0] + (oy0 - QY) * d[1] + gx0
    f = (ox0 - QX) * n[0] + (oy0 - QY) * n[1] + gy0
    out = im.transform((ow, oh), Image.AFFINE, (d[0], d[1], c, n[0], n[1], f), resample=Image.BILINEAR)
    return ox0, oy0, np.asarray(out).astype(np.float32) / 255.0


# ---------------------------------------------------------------- the renderer
def render_case(case_dir, out_path):
    view = json.load(open(os.path.join(case_dir, "view-1.json"), encoding="utf8"))
    style = json.load(open(os.path.join(case_dir, "style.cs.json"), encoding="utf8"))
    M = Mapping(view)
    sd = view["scaleDenominator"]
    W, H = view["width"], view["height"]
    cv = Canvas(W, H)
    vis = view.get("visualization", {})
    ti = vis.get("timeInterval", {})
    base_ctx = {"sd": sd, "start": ti.get("start"), "end": ti.get("end"), "date": vis.get("date")}
    rules = style.get("stylingRules", [])

    items = []            # (zOrder, phase, layer index, seq, kind, payload)
    point_labels = []     # candidate builders
    line_groups = {}      # (layer, text key) -> (F, elements, placement, prio, op, [lines])
    seq = itertools.count()

    for li, lid in enumerate(view["layers"]):
        vec_path = os.path.join(case_dir, lid + ".geojson")
        if os.path.exists(vec_path):
            gj = json.load(open(vec_path, encoding="utf8"))
            for feat in gj["features"]:
                g = feat["geometry"]
                gt = g["type"]
                dim = {"Point": 0, "LineString": 1, "Polygon": 2}[gt]
                F = dict(base_ctx, layer_id=lid, layer_type="vector", dim=dim,
                         props=feat.get("properties", {}))
                state = {}
                apply_rules(rules, F, state)
                if state.get("visibility", True) is False:
                    continue
                z = state.get("zOrder", 1)
                op = state.get("opacity", 1.0)
                pts, lines, polys = [], [], []
                if gt == "Point":
                    pts = [M.xy(*g["coordinates"])]
                elif gt == "LineString":
                    lines = [[M.xy(*c) for c in g["coordinates"]]]
                else:
                    polys = [[[M.xy(*c) for c in ring] for ring in g["coordinates"]]]
                if polys:
                    fill = state.get("fill") or {}
                    fcol = parse_color(fill.get("color", "white"), (255, 255, 255))
                    items.append((z, 0, li, next(seq), "fill",
                                  (polys, fcol, fill.get("opacity", 1.0) * op)))
                stroke = state.get("stroke") or {}
                w_px = length_px(stroke.get("width", {"px": 1.0}), sd)
                if (lines or polys) and w_px > 0:
                    scol = parse_color(stroke.get("color", "black"))
                    slines = lines if lines else [ring for poly in polys for ring in poly]
                    items.append((z, 1, li, next(seq), "stroke",
                                  (slines, w_px, scol, stroke.get("opacity", 1.0) * op)))
                elements = marker_elements(state.get("marker", {}))
                if elements:
                    if pts:
                        anchors = pts
                    elif lines:
                        anchors = list(lines[0])          # vertices of a line (see notes)
                    else:
                        anchors = [centroid(polys[0][0])]
                    items.append((z, 2, li, next(seq), "marker", (anchors, elements, op, F)))
                label = state.get("label")
                if label and label.get("elements"):
                    els = label["elements"]
                    placement = label.get("placement", {})
                    prio = ev(placement["priority"], F) if "priority" in placement else 0
                    prio = 0 if prio is None else prio
                    if lines:
                        key = tuple(text_of(e.get("text"), F) for e in els if e.get("type") == "Text")
                        grp = line_groups.setdefault((li, key), {"F": F, "els": els, "pl": placement,
                                                                 "prio": prio, "op": op, "lines": []})
                        grp["lines"].append(lines[0])
                    else:
                        anchor_pts = pts if pts else [centroid(polys[0][0])]
                        for ap in anchor_pts:
                            point_labels.append((ap, F, els, prio, op))
        else:
            band_files = sorted(f for f in os.listdir(case_dir) if f.startswith(lid + ".") and f.endswith(".asc"))
            if not band_files:
                continue
            F = dict(base_ctx, layer_id=lid, layer_type="coverage", dim=None, props={})
            state = {}
            apply_rules(rules, F, state)
            if state.get("visibility", True) is False:
                continue
            items.append((state.get("zOrder", 1), 0, li, next(seq), "coverage",
                          (read_asc(os.path.join(case_dir, band_files[0])), state, state.get("opacity", 1.0))))

    # features: increasing zOrder; in a pass, fills, then strokes, then markers
    items.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    for z, phase, li, _, kind, p in items:
        if kind == "fill":
            polys, col, op = p
            for poly in polys:
                x0, y0, a = poly_patch([[(x * SS, y * SS) for x, y in ring] for ring in poly])
                cv.paint(x0, y0, a, col, op)
        elif kind == "stroke":
            lines, w_px, col, op = p
            x0, y0, a = line_patch([[(x * SS, y * SS) for x, y in l] for l in lines], w_px * SS)
            cv.paint(x0, y0, a, col, op)
        elif kind == "marker":
            anchors, elements, op, F = p
            for ap in anchors:
                for el in elements:
                    if el.get("type") == "Dot":
                        draw_dot(cv, el, ap, op, sd)
                    elif el.get("type") == "Image":
                        draw_image(cv, el, ap, op, case_dir, sd)
                    elif el.get("type") == "Text":
                        draw_marker_text(cv, el, F, ap, op, sd)
                    else:
                        raise ValueError(el.get("type"))
        elif kind == "coverage":
            grid, state, op = p
            paint_coverage(cv, M, grid, state, op)

    # labels are a separate pass on top of everything
    cands = []
    for ap, F, els, prio, op in point_labels:
        c = point_label(ap, F, els, prio, op, sd, case_dir)
        if c:
            cands.append(c)
    for grp in line_groups.values():
        for chain in join_chains(grp["lines"]):
            cands.extend(line_label_candidates(chain, grp["F"], grp["els"], grp["pl"],
                                               grp["prio"], grp["op"], sd))
    cands.sort(key=lambda c: (-c["prio"], c["order"]))
    placed = []
    for c in cands:
        box = c["box"]
        if any(x < 0 or y < 0 or x > W or y > H for x, y in box):
            continue                          # labels that would leave the map are omitted
        if any(sat_overlap(box, b) for b in placed):
            continue
        placed.append(box)
        c["draw"](cv)

    img = cv.C.reshape(H, SS, W, SS, 3).mean(axis=(1, 3))
    Image.fromarray(np.clip(np.round(img), 0, 255).astype(np.uint8), "RGB").save(out_path)
    return len(placed), len(cands)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or sorted(n for n in os.listdir(CASES) if n.startswith("case-"))
    for nm in names:
        n, total = render_case(os.path.join(CASES, nm), os.path.join(OUT, nm + "-1.png"))
        print(nm, "labels placed", n, "of", total, flush=True)
