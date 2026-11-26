"""Renderer written from the CartoSym 2.0 Part 1 draft text only.

Usage: render.py <case-dir> <out.png>
Choices that the text leaves open are numbered C1.. in the comments and are
described in notes.md.
"""
import sys, os, json, math, copy
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageColor

SS = 4  # supersampling factor for all anti-aliased drawing
FONT_DIR = "C:/Windows/Fonts/"

# ---------------------------------------------------------------- colours


def parse_color(v):
    if v is None:
        return (0.0, 0.0, 0.0)
    if isinstance(v, str):
        return tuple(float(c) for c in ImageColor.getrgb(v)[:3])
    if isinstance(v, dict):
        return (float(v.get("r", 0)), float(v.get("g", 0)), float(v.get("b", 0)))
    if isinstance(v, (list, tuple)):
        return (float(v[0]), float(v[1]), float(v[2]))
    return (0.0, 0.0, 0.0)


# ---------------------------------------------------------------- expressions


class Ctx:
    def __init__(self, props, sysvals):
        self.props = props
        self.sys = sysvals


def norm_sysid(n):
    n = n.replace("viz.", "visualization.", 1) if n.startswith("viz.") else n
    n = n.replace("visualization.sd", "visualization.scaleDenominator")
    if n == "dataLayer.id":
        n = "dataLayer.identifier"
    return n


def _cmp(a, b):
    if a is None or b is None:
        return None
    if isinstance(a, bool) or isinstance(b, bool):
        return (a > b) - (a < b) if a != b else 0
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return (a > b) - (a < b)
    if isinstance(a, str) and isinstance(b, str):
        return (a > b) - (a < b)
    return None


def tostr(v):
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


def ev(e, ctx):
    if isinstance(e, dict):
        if "property" in e:
            return ctx.props.get(e["property"])
        if "sysId" in e:
            return ctx.sys.get(norm_sysid(e["sysId"]))
        if "op" in e:
            op = e["op"]
            args = e.get("args", [])
            if op in ("and", "or"):
                vals = [ev(a, ctx) for a in args]
                if op == "and":
                    if any(v is False for v in vals):
                        return False
                    if any(v is None for v in vals):
                        return None
                    return True
                if any(v is True for v in vals):
                    return True
                if any(v is None for v in vals):
                    return None
                return False
            vals = [ev(a, ctx) for a in args]
            return apply_op(op, vals)
        return e
    if isinstance(e, list):
        return [ev(x, ctx) for x in e]
    return e


def apply_op(op, v):
    if op == "not":
        return None if v[0] is None else (not v[0])
    if op in ("=", "<>", "<", ">", "<=", ">="):
        c = _cmp(v[0], v[1])
        if c is None:
            return None
        return {"=": c == 0, "<>": c != 0, "<": c < 0, ">": c > 0, "<=": c <= 0, ">=": c >= 0}[op]
    if op in ("isNull", "is null"):
        return v[0] is None
    if op == "in":
        arr = v[1] or []
        if v[0] is None:
            return False if not arr else None
        if any(_cmp(v[0], x) == 0 for x in arr):
            return True
        return None if any(x is None for x in arr) else False
    if op == "between":
        a, lo, hi = v
        c1, c2 = _cmp(a, lo), _cmp(a, hi)
        if c1 is None or c2 is None:
            return None
        return c1 >= 0 and c2 <= 0
    if op in ("+", "-", "*", "/", "%", "div"):
        if v[0] is None or v[1] is None:
            return None
        a, b = v
        try:
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                return None if b == 0 else a / b
            if op == "%":
                return None if b == 0 else a % b
            if op == "div":
                return None if b == 0 else int(a // b)
        except TypeError:
            return None
    if op == "concatenate":
        if any(x is None for x in v):
            return None
        return "".join(tostr(x) for x in v)
    if op == "like":
        import re
        if v[0] is None or v[1] is None:
            return None
        pat = "^" + re.escape(v[1]).replace("%", ".*").replace("_", ".") + "$"
        return re.match(pat, str(v[0])) is not None
    return None


def val(x, ctx):
    """Resolve a Parameter Value."""
    if isinstance(x, dict) and ("property" in x or "sysId" in x or "op" in x):
        return ev(x, ctx)
    return x


# ---------------------------------------------------------------- style merge


def merge_sym(base, new):
    for k, v in new.items():
        if isinstance(v, dict) and v.get("alter") and isinstance(base.get(k), dict):
            merge_obj(base[k], v)
        elif isinstance(v, dict) and v.get("alter") and base.get(k) is None:
            nv = {kk: vv for kk, vv in v.items() if kk != "alter"}
            base[k] = copy.deepcopy(nv)
        else:
            base[k] = copy.deepcopy(v)
            if isinstance(base[k], dict):
                base[k].pop("alter", None)


def merge_obj(base, upd):
    for k, v in upd.items():
        if k == "alter":
            continue
        if k == "elements" and isinstance(v, dict) and "index" in v:
            lst = base.setdefault("elements", [])
            i = v["index"]
            nv = copy.deepcopy(v["value"])
            if i < len(lst):
                if isinstance(nv, dict) and nv.get("alter") and isinstance(lst[i], dict):
                    merge_obj(lst[i], nv)
                else:
                    lst[i] = nv
            else:
                lst.append(nv)
        elif isinstance(v, dict) and v.get("alter") and isinstance(base.get(k), dict):
            merge_obj(base[k], v)
        else:
            base[k] = copy.deepcopy(v)
            if isinstance(base[k], dict):
                base[k].pop("alter", None)


def resolve_style(rules, ctx, sym=None):
    if sym is None:
        sym = {}
    for r in rules:
        sel = r.get("selector")
        ok = True if sel is None else (ev(sel, ctx) is True)
        if not ok:
            continue
        if r.get("symbolizer"):
            merge_sym(sym, r["symbolizer"])
        if r.get("nestedRules"):
            resolve_style(r["nestedRules"], ctx, sym)
    return sym


# ---------------------------------------------------------------- surfaces


def down(a):
    h, w = a.shape[0] // SS, a.shape[1] // SS
    return a.reshape(h, SS, w, SS).mean(axis=(1, 3))


class Surface:
    def __init__(self, w, h, bg=None):
        self.w, self.h = w, h
        self.rgb = np.zeros((h, w, 3), np.float32)
        self.a = np.zeros((h, w), np.float32)
        if bg is not None:
            self.rgb[:] = np.array(bg, np.float32) / 255.0
            self.a[:] = 1.0

    def _clip(self, x0, y0, w, h):
        sx0, sy0 = max(0, x0), max(0, y0)
        sx1, sy1 = min(self.w, x0 + w), min(self.h, y0 + h)
        if sx1 <= sx0 or sy1 <= sy0:
            return None
        return sx0, sy0, sx1, sy1

    def paint(self, mask, x0, y0, color, alpha):
        c = self._clip(x0, y0, mask.shape[1], mask.shape[0])
        if c is None or alpha <= 0:
            return
        sx0, sy0, sx1, sy1 = c
        m = mask[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] * alpha
        col = np.array(color, np.float32) / 255.0
        R = self.rgb[sy0:sy1, sx0:sx1]
        A = self.a[sy0:sy1, sx0:sx1]
        R[:] = R * (1 - m)[..., None] + col * m[..., None]
        A[:] = m + A * (1 - m)

    def paint_premult(self, rgbp, ap, x0, y0, opacity):
        c = self._clip(x0, y0, ap.shape[1], ap.shape[0])
        if c is None:
            return
        sx0, sy0, sx1, sy1 = c
        r = rgbp[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] * opacity
        a = ap[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] * opacity
        R = self.rgb[sy0:sy1, sx0:sx1]
        A = self.a[sy0:sy1, sx0:sx1]
        R[:] = r + R * (1 - a)[..., None]
        A[:] = a + A * (1 - a)

    def blend(self, other):
        self.rgb[:] = other.rgb + self.rgb * (1 - other.a)[..., None]
        self.a[:] = other.a + self.a * (1 - other.a)


def mask_from_draw(bounds, W, H, fn):
    """bounds: (xmin,ymin,xmax,ymax) in px (float). Returns (mask, x0, y0) or None."""
    x0 = max(0, int(math.floor(bounds[0])))
    y0 = max(0, int(math.floor(bounds[1])))
    x1 = min(W, int(math.ceil(bounds[2])))
    y1 = min(H, int(math.ceil(bounds[3])))
    if x1 <= x0 or y1 <= y0:
        return None
    img = Image.new("L", ((x1 - x0) * SS, (y1 - y0) * SS), 0)
    d = ImageDraw.Draw(img)
    fn(d, x0, y0)
    return down(np.asarray(img, np.float32) / 255.0), x0, y0


def stroke_polyline(surf, pts, width, color, alpha):
    if width <= 0 or alpha <= 0 or len(pts) < 1:
        return
    pts = np.asarray(pts, float)
    pad = width / 2 + 1
    b = (pts[:, 0].min() - pad, pts[:, 1].min() - pad, pts[:, 0].max() + pad, pts[:, 1].max() + pad)
    wss = max(1, int(round(width * SS)))

    def fn(d, x0, y0):
        p = [((x - x0) * SS, (y - y0) * SS) for x, y in pts]
        if len(p) >= 2:
            d.line(p, fill=255, width=wss, joint="curve")
        r = wss / 2.0
        if wss > 2:
            for (x, y) in p:
                d.ellipse([x - r, y - r, x + r, y + r], fill=255)
        else:
            for (x, y) in (p[0], p[-1]):
                d.ellipse([x - r, y - r, x + r, y + r], fill=255)

    m = mask_from_draw(b, surf.w, surf.h, fn)
    if m:
        surf.paint(m[0], m[1], m[2], color, alpha)


def fill_polygon(surf, rings, color, alpha):
    if alpha <= 0:
        return
    ext = np.asarray(rings[0], float)
    b = (ext[:, 0].min() - 1, ext[:, 1].min() - 1, ext[:, 0].max() + 1, ext[:, 1].max() + 1)

    def fn(d, x0, y0):
        d.polygon([((x - x0) * SS, (y - y0) * SS) for x, y in rings[0]], fill=255)
        for h in rings[1:]:
            d.polygon([((x - x0) * SS, (y - y0) * SS) for x, y in h], fill=0)

    m = mask_from_draw(b, surf.w, surf.h, fn)
    if m:
        surf.paint(m[0], m[1], m[2], color, alpha)


def fill_circle(surf, cx, cy, diameter, color, alpha):
    if diameter <= 0 or alpha <= 0:
        return
    r = diameter / 2.0
    b = (cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1)

    def fn(d, x0, y0):
        X, Y = (cx - x0) * SS, (cy - y0) * SS
        d.ellipse([X - r * SS, Y - r * SS, X + r * SS, Y + r * SS], fill=255)

    m = mask_from_draw(b, surf.w, surf.h, fn)
    if m:
        surf.paint(m[0], m[1], m[2], color, alpha)


# ---------------------------------------------------------------- fonts / text

_fonts = {}


def get_font(face, bold, italic, size_ss):
    key = (str(face).lower(), bool(bold), bool(italic), round(size_ss, 3))
    if key in _fonts:
        return _fonts[key]
    fam = str(face or "Arial").lower()
    table = {"arial": ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf")}
    names = table.get(fam)
    if names is None:
        base = fam.replace(" ", "")
        names = (base + ".ttf", base + "bd.ttf", base + "i.ttf", base + "bi.ttf")
    idx = (1 if bold else 0) + (2 if italic else 0)
    order = [0, 1, 2, 3]
    cand = [names[idx]] + [names[i] for i in order]
    f = None
    for n in cand:
        p = FONT_DIR + n
        if os.path.exists(p):
            f = ImageFont.truetype(p, size_ss)
            break
    if f is None:
        f = ImageFont.truetype(FONT_DIR + "arial.ttf", size_ss)
    _fonts[key] = f
    return f


class FontSpec:
    def __init__(self, face, size_px, bold, italic, color, opacity, outline):
        self.face, self.size, self.bold, self.italic = face, size_px, bold, italic
        self.color, self.opacity, self.outline = color, opacity, outline

    def ss(self):
        return get_font(self.face, self.bold, self.italic, self.size * SS)

    def metrics(self):
        a, d = self.ss().getmetrics()
        return a / SS, d / SS

    def advance(self, s):
        return self.ss().getlength(s) / SS


class TextAcc:
    """Accumulates glyph and outline masks at supersampled resolution."""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.g = np.zeros((H * SS, W * SS), np.float32)
        self.o = np.zeros((H * SS, W * SS), np.float32)

    def _blit(self, acc, img, ox, oy):
        arr = np.asarray(img, np.float32) / 255.0
        h, w = arr.shape
        x0, y0 = max(0, ox), max(0, oy)
        x1, y1 = min(acc.shape[1], ox + w), min(acc.shape[0], oy + h)
        if x1 <= x0 or y1 <= y0:
            return
        sub = arr[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
        acc[y0:y1, x0:x1] = np.maximum(acc[y0:y1, x0:x1], sub)

    def add(self, s, fs, pivot_x, pivot_y_rel, P, theta):
        """s drawn so that the point (pivot_x px from string start, pivot_y_rel px below baseline)
        lands on P (px, float) after rotating by theta (radians, clockwise on screen)."""
        f = fs.ss()
        asc, desc = f.getmetrics()
        wss = int(math.ceil(f.getlength(s))) + 1
        ow = fs.outline["size"] if fs.outline else 0
        pad = int(math.ceil(ow * SS)) + 4
        tw, th = wss + 2 * pad, asc + desc + 2 * pad
        img_g = Image.new("L", (tw, th), 0)
        ImageDraw.Draw(img_g).text((pad, pad + asc), s, font=f, anchor="ls", fill=255)
        img_o = None
        if ow > 0:
            img_o = Image.new("L", (tw, th), 0)
            ImageDraw.Draw(img_o).text((pad, pad + asc), s, font=f, anchor="ls", fill=255,
                                       stroke_width=max(1, int(round(ow * SS))), stroke_fill=255)
        px_l = pad + pivot_x * SS
        py_l = pad + asc + pivot_y_rel * SS
        if abs(theta) < 1e-9:
            ox = int(round(P[0] * SS - px_l))
            oy = int(round(P[1] * SS - py_l))
            self._blit(self.g, img_g, ox, oy)
            if img_o is not None:
                self._blit(self.o, img_o, ox, oy)
        else:
            R = int(math.hypot(tw, th)) + 4
            deg = -math.degrees(theta)
            for img, acc in ((img_g, self.g), (img_o, self.o)):
                if img is None:
                    continue
                big = Image.new("L", (2 * R, 2 * R), 0)
                big.paste(img, (int(round(R - px_l)), int(round(R - py_l))))
                big = big.rotate(deg, resample=Image.BICUBIC, center=(R, R))
                self._blit(acc, big, int(round(P[0] * SS - R)), int(round(P[1] * SS - R)))

    def paint(self, surf, fs, alpha_mul=1.0, outline_alpha_mul=1.0):
        if fs.outline and fs.outline["size"] > 0:
            surf.paint(down(self.o), 0, 0, fs.outline["color"], fs.outline["opacity"] * outline_alpha_mul)
        surf.paint(down(self.g), 0, 0, fs.color, fs.opacity * alpha_mul)


def valign_ref(fs, v):
    """y of the alignment reference relative to the baseline (px, downwards)."""
    a, d = fs.metrics()
    if v == "top":
        return -a
    if v == "bottom":
        return d
    return (d - a) / 2.0


def halign_ref(w, h):
    return {"left": 0.0, "center": w / 2.0, "right": w}.get(h, 0.0)


# ---------------------------------------------------------------- renderer


class View:
    def __init__(self, v, case_dir):
        self.v = v
        self.case_dir = case_dir
        self.bbox = v["bbox"]
        self.W, self.H = v["width"], v["height"]
        self.sd = v["scaleDenominator"]
        self.pix_mm = v.get("pixelSize_mm", 0.28)
        self.m_per_px = self.sd * self.pix_mm / 1000.0
        self.sx = self.W / (self.bbox[2] - self.bbox[0])
        self.sy = self.H / (self.bbox[3] - self.bbox[1])

    def to_px(self, x, y):
        return ((x - self.bbox[0]) * self.sx, (self.bbox[3] - y) * self.sy)

    def length_px(self, v, em=None, default_unit="px"):
        """Convert a uom-qualified value to pixels."""
        if v is None:
            return None
        if isinstance(v, dict):
            (u, n), = [(k, vv) for k, vv in v.items()][:1]
            n = float(n)
            if u == "px":
                return n
            if u == "m":
                return n / self.m_per_px
            if u == "ft":
                return n * 0.3048 / self.m_per_px
            if u == "mm":
                return n / self.pix_mm
            if u in ("cm",):
                return n * 10 / self.pix_mm
            if u in ("inch", "in"):
                return n * 25.4 / self.pix_mm
            if u == "pt":
                return n * (25.4 / 72.0) / self.pix_mm
            if u == "em":
                return n * (em if em else 16.0)
            if u == "pc":
                return n / 100.0 * (em if em else 1.0)
            return n
        return float(v)


def load_asc(path):
    with open(path) as f:
        hdr = {}
        for _ in range(6):
            k, v = f.readline().split()
            hdr[k.lower()] = float(v)
        data = np.loadtxt(f, dtype=np.float64)
    return hdr, data


def poly_centroid(ring):
    r = np.asarray(ring, float)
    x, y = r[:, 0], r[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y1 - x1 * y
    a = cr.sum() / 2.0
    if abs(a) < 1e-9:
        return float(x.mean()), float(y.mean())
    return float(((x + x1) * cr).sum() / (6 * a)), float(((y + y1) * cr).sum() / (6 * a))


def build_font(view, *fonts, default_size=16.0):
    """Font inheritance: per property, the nearest place that sets it."""
    def pick(key):
        for f in fonts:
            if f and key in f and f[key] is not None:
                return f[key]
        return None
    size = pick("size")
    em_ctx = default_size
    sizepx = view.length_px(size, em=em_ctx) if size is not None else default_size
    ol = pick("outline")
    outline = None
    if ol:
        outline = {"size": float(ol.get("size", 0) or 0),
                   "opacity": float(ol.get("opacity", 1.0)),
                   "color": parse_color(ol.get("color", "black"))}
    col = pick("color")
    return FontSpec(pick("face") or "Arial", sizepx, bool(pick("bold")), bool(pick("italic")),
                    parse_color(col) if col is not None else (0.0, 0.0, 0.0),
                    float(pick("opacity") if pick("opacity") is not None else 1.0), outline)


class Renderer:
    def __init__(self, case_dir):
        self.dir = case_dir
        self.view = View(json.load(open(os.path.join(case_dir, "view-1.json"), encoding="utf-8")), case_dir)
        self.style = json.load(open(os.path.join(case_dir, "style.cs.json"), encoding="utf-8"))
        v = self.view
        self.surf = Surface(v.W, v.H, bg=parse_color(v.v.get("background", "white")))
        viz = v.v.get("visualization", {})
        ti = viz.get("timeInterval", {})
        self.sysbase = {
            "visualization.scaleDenominator": v.sd,
            "visualization.date": viz.get("date"),
            "visualization.timeInterval.start.date": ti.get("start"),
            "visualization.timeInterval.end.date": ti.get("end"),
            "visualization.pass": 1,
        }
        self.items = []   # drawing items
        self.labels = []  # label requests
        self.notes = []

    # ---- layer loading
    def run(self):
        for li, name in enumerate(self.view.v["layers"]):
            gj = os.path.join(self.dir, name + ".geojson")
            if os.path.exists(gj):
                self.load_vector(li, name, gj)
            else:
                self.load_coverage(li, name)
        self.draw_items()
        self.place_labels()
        return self.surf

    def layer_sys(self, name, ltype, dim):
        s = dict(self.sysbase)
        s["dataLayer.identifier"] = name
        s["dataLayer.type"] = ltype
        s["dataLayer.featuresGeometryDimension"] = dim
        return s

    # ---- coverage
    def load_coverage(self, li, name):
        bands = {}
        for fn in os.listdir(self.dir):
            if fn.startswith(name + ".") and fn.endswith(".asc"):
                band = fn[len(name) + 1:-4]
                bands[band] = load_asc(os.path.join(self.dir, fn))
        sysv = self.layer_sys(name, "coverage", None)
        sym = resolve_style(self.style["stylingRules"], Ctx({}, sysv))
        sym.setdefault("visibility", True)
        if not val(sym.get("visibility"), Ctx({}, sysv)):
            return
        self.items.append({"kind": "coverage", "layer": li, "z": int(val(sym.get("zOrder", 1), Ctx({}, sysv)) or 0),
                           "sym": sym, "bands": bands, "ord": 0})

    def draw_coverage(self, it):
        v = self.view
        sym = it["sym"]
        sc = sym.get("singleChannel")
        if sc is None or not it["bands"]:
            return
        band = sc.get("property") if isinstance(sc, dict) else sc
        hdr, data = it["bands"][band]
        cs = hdr["cellsize"]
        nrows, ncols = data.shape
        nod = hdr.get("nodata_value", -9999)
        top = hdr["yllcorner"] + nrows * cs
        # pixel centres -> cell (C3: cell containing the pixel centre, no interpolation)
        xs = v.bbox[0] + (np.arange(v.W) + 0.5) / v.sx
        ys = v.bbox[3] - (np.arange(v.H) + 0.5) / v.sy
        cols = np.floor((xs - hdr["xllcorner"]) / cs).astype(int)
        rows = np.floor((top - ys) / cs).astype(int)
        inside = ((rows[:, None] >= 0) & (rows[:, None] < nrows) & (cols[None, :] >= 0) & (cols[None, :] < ncols))
        rc = np.clip(rows, 0, nrows - 1)
        cc = np.clip(cols, 0, ncols - 1)
        vals = data[rc[:, None], cc[None, :]]
        valid = inside & (vals != nod)
        rgb = np.zeros((v.H, v.W, 3), np.float32)
        cmap = sym.get("colorMap")
        if cmap:
            ks = np.array([float(e[0]) if isinstance(e, list) else float(e["value"]) for e in cmap])
            cols_ = np.array([parse_color(e[1] if isinstance(e, list) else e["color"]) for e in cmap])
            for ch in range(3):
                rgb[..., ch] = np.interp(vals, ks, cols_[:, ch]) / 255.0
        else:
            rgb[:] = np.clip(vals[..., None] / 1.0, 0, 1)
        alpha = np.ones((v.H, v.W), np.float32)
        hs = sym.get("hillShading")
        if hs and float(val(hs.get("factor", 0), Ctx({}, {})) or 0) > 0:
            factor = float(hs["factor"])
            sun = hs.get("sun", {"azimuth": 315, "elevation": 45})
            az, el = math.radians(sun.get("azimuth", 315)), math.radians(sun.get("elevation", 45))
            z = np.where(data == nod, np.nan, data)
            zp = np.pad(z, 1, mode="edge")
            dzdx = (zp[1:-1, 2:] - zp[1:-1, :-2]) / (2 * cs)           # east
            dzdy = -(zp[2:, 1:-1] - zp[:-2, 1:-1]) / (2 * cs)          # rows run north->south
            nx, ny, nz = -factor * dzdx, -factor * dzdy, np.ones_like(dzdx)
            ln = np.sqrt(nx * nx + ny * ny + nz * nz)
            sx_, sy_, sz_ = math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)
            shade = np.clip((nx * sx_ + ny * sy_ + nz * sz_) / ln, 0, 1)
            shade = np.nan_to_num(shade, nan=1.0)
            rgb = rgb * shade[rc[:, None], cc[None, :]][..., None]
        alpha = alpha * valid.astype(np.float32) * float(val(sym.get("opacity", 1), Ctx({}, {})))
        self.surf.paint_premult(rgb * alpha[..., None], alpha, 0, 0, 1.0)

    # ---- vector
    def load_vector(self, li, name, path):
        gj = json.load(open(path, encoding="utf-8"))
        feats = gj["features"]
        dims = set()
        for f in feats:
            t = f["geometry"]["type"]
            dims.add(0 if "Point" in t else 1 if "Line" in t else 2)
        dim = dims.pop() if len(dims) == 1 else None
        v = self.view
        for fi, f in enumerate(feats):
            g = f["geometry"]
            t = g["type"]
            fdim = 0 if "Point" in t else 1 if "Line" in t else 2
            sysv = self.layer_sys(name, "vector", dim)
            sysv["feature.geometryDimension"] = fdim
            sysv["feature.pass"] = 1
            ctx = Ctx(f.get("properties", {}), sysv)
            sym = resolve_style(self.style["stylingRules"], ctx)
            if not val(sym.get("visibility", True), ctx):
                continue
            # geometry in px
            def P(c):
                return [v.to_px(x, y) for x, y in c]
            if t == "Point":
                geoms = [("pt", [P([g["coordinates"]])[0]])]
            elif t == "MultiPoint":
                geoms = [("pt", P(g["coordinates"]))]
            elif t == "LineString":
                geoms = [("line", [np.array(P(g["coordinates"]))])]
            elif t == "MultiLineString":
                geoms = [("line", [np.array(P(l)) for l in g["coordinates"]])]
            elif t == "Polygon":
                geoms = [("poly", [[np.array(P(r)) for r in g["coordinates"]]])]
            elif t == "MultiPolygon":
                geoms = [("poly", [[np.array(P(r)) for r in pl] for pl in g["coordinates"]])]
            else:
                continue
            z = int(round(float(val(sym.get("zOrder", 1), ctx) or 0)))
            self.items.append({"kind": "vec", "layer": li, "z": z, "sym": sym, "ctx": ctx, "geoms": geoms,
                               "ord": fi, "name": name})
            if sym.get("label"):
                self.labels.append({"layer": li, "ord": fi, "name": name, "geoms": geoms, "sym": sym, "ctx": ctx})

    # ---- drawing
    def sym_opacity(self, it):
        return float(val(it["sym"].get("opacity", 1), it["ctx"]) or 0)

    def draw_items(self):
        zs = sorted(set(it["z"] for it in self.items))
        for z in zs:
            group = [it for it in self.items if it["z"] == z]
            group.sort(key=lambda it: (it["layer"], it["ord"]))
            # phase 1: fills (and coverage)
            for it in group:
                if it["kind"] == "coverage":
                    self.draw_coverage(it)
                else:
                    self.draw_fill(it)
            for it in group:
                if it["kind"] == "vec":
                    self.draw_stroke(it)
            for it in group:
                if it["kind"] == "vec":
                    self.draw_markers(it)

    def draw_fill(self, it):
        sym, ctx = it["sym"], it["ctx"]
        fill = sym.get("fill") or {}
        col = parse_color(val(fill.get("color", "white"), ctx))
        a = float(val(fill.get("opacity", 1), ctx) or 0) * self.sym_opacity(it)
        for kind, parts in it["geoms"]:
            if kind == "poly":
                for rings in parts:
                    fill_polygon(self.surf, rings, col, a)

    def draw_stroke(self, it):
        sym, ctx = it["sym"], it["ctx"]
        stroke = sym.get("stroke")
        if stroke is None:
            stroke = {}
        w = self.view.length_px(val(stroke.get("width", {"px": 1}), ctx))
        if w is None or w <= 0:
            return
        col = parse_color(val(stroke.get("color", "black"), ctx))
        a = float(val(stroke.get("opacity", 1), ctx) or 0) * self.sym_opacity(it)
        for kind, parts in it["geoms"]:
            if kind == "line":
                for ln in parts:
                    stroke_polyline(self.surf, ln, w, col, a)
            elif kind == "poly":
                for rings in parts:
                    for r in rings:
                        stroke_polyline(self.surf, np.vstack([r, r[:1]]) if not np.allclose(r[0], r[-1]) else r,
                                        w, col, a)

    def anchors(self, it_geoms):
        out = []
        for kind, parts in it_geoms:
            if kind == "pt":
                out += [tuple(p) for p in parts]
            elif kind == "line":
                for ln in parts:
                    out += [tuple(p) for p in ln]
            elif kind == "poly":
                for rings in parts:
                    out.append(poly_centroid(rings[0]))
        return out

    def draw_markers(self, it):
        sym, ctx = it["sym"], it["ctx"]
        if "marker" in sym:
            mk = sym["marker"]
        else:
            mk = {}  # default Marker: a single default Dot (C7)
        if mk is None:
            return
        elems = mk.get("elements")
        if elems is None:
            elems = [{"type": "Dot"}]
        if len(elems) == 0:
            return
        opa = self.sym_opacity(it)
        for (ax, ay) in self.anchors(it["geoms"]):
            self.draw_graphics(self.surf, elems, mk, sym, ctx, (ax, ay), opa)

    def draw_graphics(self, surf, elems, mg, sym, ctx, anchor, opa):
        v = self.view
        for e in elems:
            t = e.get("type", "Dot")
            eop = float(val(e.get("opacity", 1), ctx) or 0) * opa
            pos = e.get("position") or {"x": 0, "y": 0}
            font_here = None
            if t == "Text":
                fs = build_font(v, e.get("font"), mg.get("font"), sym.get("font"))
                em = fs.size
            else:
                fs0 = build_font(v, mg.get("font"), sym.get("font"))
                em = fs0.size
            px_ = v.length_px(pos.get("x", 0), em=em) if isinstance(pos, dict) else v.length_px(pos[0], em=em)
            py_ = v.length_px(pos.get("y", 0), em=em) if isinstance(pos, dict) else v.length_px(pos[1], em=em)
            P = (anchor[0] + px_, anchor[1] + py_)
            if t == "Dot":
                stroke = e.get("stroke") or {}
                size = e.get("size", stroke.get("width", {"px": 10}))
                col = e.get("color", stroke.get("color", "white"))
                d = v.length_px(val(size, ctx), em=em)
                fill_circle(surf, P[0], P[1], d, parse_color(val(col, ctx)), eop)
            elif t == "Text":
                self.draw_text_straight(surf, e, fs, ctx, P, eop)
            elif t == "Image":
                self.draw_image(surf, e, ctx, P, eop, em)

    def draw_text_straight(self, surf, e, fs, ctx, P, opa):
        text = val(e.get("text"), ctx)
        text = tostr(text)
        if not text:
            return
        al = e.get("alignment") or ["left", "top"]
        if isinstance(al, dict):
            al = [al.get("horzAlignment", "left"), al.get("vertAlignment", "top")]
        w = fs.advance(text)
        acc = TextAcc(self.view.W, self.view.H)
        acc.add(text, fs, halign_ref(w, al[0]), valign_ref(fs, al[1]), P, 0.0)
        acc.paint(surf, fs, alpha_mul=opa, outline_alpha_mul=opa)

    def draw_image(self, surf, e, ctx, P, opa, em):
        v = self.view
        img = e.get("image", {})
        path = img.get("path")
        im = None
        if path:
            p = os.path.normpath(os.path.join(self.dir, path))
            if os.path.exists(p) and not p.lower().endswith(".svg"):
                im = Image.open(p).convert("RGBA")
        if im is None:
            self.notes.append("image not drawn: %s" % path)
            return
        a = np.asarray(im, np.float32) / 255.0
        tint = np.array(parse_color(val(e.get("tint", "white"), ctx)), np.float32) / 255.0
        btint = np.array(parse_color(val(e.get("blackTint", "black"), ctx)), np.float32) / 255.0
        rgb = a[..., :3] * tint + (1 - a[..., :3]) * btint
        al = a[..., 3]
        iw, ih = im.size
        size = e.get("size")
        if size is None:
            w, h = float(iw), float(ih)
        else:
            if isinstance(size, list):
                sx_ = v.length_px(size[0], em=em) if size[0] is not None else None
                sy_ = v.length_px(size[1], em=em) if size[1] is not None else None
            elif isinstance(size, dict) and ("x" in size or "y" in size):
                sx_ = v.length_px(size["x"], em=em) if "x" in size else None
                sy_ = v.length_px(size["y"], em=em) if "y" in size else None
            else:
                sx_ = sy_ = v.length_px(size, em=em)
            if sx_ is None:
                sx_ = sy_ * iw / ih
            if sy_ is None:
                sy_ = sx_ * ih / iw
            w, h = sx_, sy_
        hs = e.get("hotSpot") or [{"pc": 50}, {"pc": 50}]
        hx = self._hot(hs[0], w, iw, em)
        hy = self._hot(hs[1], h, ih, em)
        # premultiplied, resample at supersampled size
        pm = np.concatenate([rgb * al[..., None], al[..., None]], axis=2)
        wss, hss = max(1, int(round(w * SS))), max(1, int(round(h * SS)))
        chans = []
        for c in range(4):
            ch = Image.fromarray(pm[..., c].astype(np.float32), mode="F").resize((wss, hss), Image.BICUBIC)
            chans.append(np.asarray(ch, np.float32))
        big = np.stack(chans, axis=2).clip(0, 1)
        x0 = P[0] - hx
        y0 = P[1] - hy
        ox, oy = int(math.floor(x0)), int(math.floor(y0))
        # place into a supersampled canvas covering the image bbox
        cw, ch_ = int(math.ceil(w)) + 2, int(math.ceil(h)) + 2
        canvas = np.zeros((ch_ * SS, cw * SS, 4), np.float32)
        offx = int(round((x0 - ox) * SS))
        offy = int(round((y0 - oy) * SS))
        hh, ww = big.shape[:2]
        hh2, ww2 = min(hh, canvas.shape[0] - offy), min(ww, canvas.shape[1] - offx)
        canvas[offy:offy + hh2, offx:offx + ww2] = big[:hh2, :ww2]
        small = canvas.reshape(ch_, SS, cw, SS, 4).mean(axis=(1, 3))
        surf.paint_premult(small[..., :3], small[..., 3], ox, oy, opa)

    def _hot(self, h, size_px, size_img, em):
        if isinstance(h, dict):
            (u, n), = list(h.items())[:1]
            if u == "pc":
                return size_px * n / 100.0
            return self.view.length_px(h, em=em)
        return float(h) * size_px / size_img  # unit-less: pixels of the image file, scaled

    # ---- labels
    def place_labels(self):
        v = self.view
        W, H = v.W, v.H
        occ = np.zeros((H, W), bool)
        reqs = []
        for L in self.labels:
            sym, ctx = L["sym"], L["ctx"]
            lab = sym.get("label")
            if lab is None or not lab.get("elements"):
                continue
            pl = lab.get("placement") or {}
            prio = val(pl.get("priority", 0), ctx)
            prio = 0.0 if prio is None else float(prio)
            mins = v.length_px(val(pl.get("minSpacing"), ctx)) if pl.get("minSpacing") is not None else None
            kinds = set(k for k, _ in L["geoms"])
            text_key = None
            for e in lab["elements"]:
                if e.get("type") == "Text":
                    text_key = tostr(val(e.get("text"), ctx))
                    break
            r = {"L": L, "lab": lab, "prio": prio, "mins": mins, "key": (L["layer"], text_key), "kinds": kinds}
            reqs.append(r)
        # join lines (C12)
        line_reqs = [r for r in reqs if "line" in r["kinds"]]
        other = [r for r in reqs if "line" not in r["kinds"]]
        chains = []
        groups = {}
        for r in line_reqs:
            for kind, parts in r["L"]["geoms"]:
                if kind == "line":
                    for ln in parts:
                        groups.setdefault(r["key"], []).append((r, ln))
        for key, lst in groups.items():
            chains += self.join_lines(lst)
        items = []
        for r in other:
            items.append({"prio": r["prio"], "layer": r["L"]["layer"], "ord": r["L"]["ord"], "r": r, "type": "pt"})
        for r, path in chains:
            items.append({"prio": r["prio"], "layer": r["L"]["layer"], "ord": r["L"]["ord"], "r": r, "type": "line",
                          "path": path})
        items.sort(key=lambda x: (-x["prio"], x["layer"], x["ord"]))
        placed = {}  # key -> list of anchors
        for it in items:
            r = it["r"]
            if it["type"] == "pt":
                for (ax, ay) in self.anchors(r["L"]["geoms"]):
                    self.try_point(r, (ax, ay), occ, placed)
            else:
                self.try_line(r, it["path"], occ, placed)

    def label_fonts(self, r):
        sym, lab, ctx = r["L"]["sym"], r["lab"], r["L"]["ctx"]
        out = []
        for e in lab["elements"]:
            if e.get("type") == "Text":
                out.append(build_font(self.view, e.get("font"), lab.get("font"), sym.get("font")))
            else:
                out.append(build_font(self.view, lab.get("font"), sym.get("font")))
        return out

    def commit(self, lsurf, occ):
        occ |= lsurf.a > 0.02
        self.surf.blend(lsurf)
        self.nlabels = getattr(self, "nlabels", 0) + 1

    def try_point(self, r, P, occ, placed):
        v = self.view
        if not (-50 <= P[0] <= v.W + 50 and -50 <= P[1] <= v.H + 50):
            return
        key = r["key"]
        if r["mins"]:
            for q in placed.get(key, []):
                if math.hypot(q[0] - P[0], q[1] - P[1]) < r["mins"]:
                    return
        lsurf = Surface(v.W, v.H)
        ctx = r["L"]["ctx"]
        self.draw_graphics(lsurf, r["lab"]["elements"], r["lab"], r["L"]["sym"], ctx, P, 1.0)
        fp = lsurf.a > 0.02
        if not fp.any():
            return
        if (fp & occ).any():
            return
        self.commit(lsurf, occ)
        placed.setdefault(key, []).append(P)

    def join_lines(self, lst):
        """Join line geometries with the same label that meet at end points (C12)."""
        def k(p):
            return (round(p[0] * 2), round(p[1] * 2))  # half-pixel tolerance
        lines = [(r, np.array(ln)) for r, ln in lst]
        used = [False] * len(lines)
        ends = {}
        for i, (r, ln) in enumerate(lines):
            ends.setdefault(k(ln[0]), []).append((i, 0))
            ends.setdefault(k(ln[-1]), []).append((i, 1))
        out = []
        for i in range(len(lines)):
            if used[i]:
                continue
            used[i] = True
            path = lines[i][1].copy()
            for _ in range(2):
                while True:
                    tail = k(path[-1])
                    nxt = None
                    for (j, e) in ends.get(tail, []):
                        if not used[j]:
                            nxt = (j, e)
                            break
                    if nxt is None:
                        break
                    j, e = nxt
                    used[j] = True
                    seg = lines[j][1] if e == 0 else lines[j][1][::-1]
                    path = np.vstack([path, seg[1:]])
                path = path[::-1].copy()
            out.append((lines[i][0], path))
        return out

    def try_line(self, r, path, occ, placed):
        v = self.view
        lab = r["lab"]
        fonts = self.label_fonts(r)
        ctx = r["L"]["ctx"]
        sym = r["L"]["sym"]
        seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
        cum = np.concatenate([[0], np.cumsum(seg)])
        Ltot = cum[-1]
        if Ltot <= 0:
            return
        # element layout in label frame (x along, y up)
        els = []
        for e, fs in zip(lab["elements"], fonts):
            t = e.get("type")
            pos = e.get("position") or {"x": 0, "y": 0}
            x = v.length_px(pos["x"] if isinstance(pos, dict) else pos[0], em=fs.size)
            y = v.length_px(pos["y"] if isinstance(pos, dict) else pos[1], em=fs.size)
            if t == "Text":
                text = tostr(val(e.get("text"), ctx))
                if not text:
                    continue
                al = e.get("alignment") or ["left", "top"]
                w = fs.advance(text)
                x0 = x - halign_ref(w, al[0])
                # glyph advances
                adv = []
                before = 0.0
                for i, ch in enumerate(text):
                    full = fs.advance(text[:i + 1])
                    adv.append((ch, before, full - before))
                    before = full
                els.append({"t": "Text", "e": e, "fs": fs, "x0": x0, "x1": x0 + w, "y": y, "glyphs": adv, "al": al,
                            "text": text})
            elif t == "Dot":
                stroke = e.get("stroke") or {}
                d = v.length_px(val(e.get("size", stroke.get("width", {"px": 10})), ctx), em=fs.size)
                els.append({"t": "Dot", "e": e, "x0": x - d / 2, "x1": x + d / 2, "x": x, "y": y, "d": d,
                            "col": parse_color(val(e.get("color", stroke.get("color", "white")), ctx))})
        if not els:
            return
        xmin = min(el["x0"] for el in els)
        xmax = max(el["x1"] for el in els)
        key = r["key"]
        mins = r["mins"]
        a_h = max(el["fs"].metrics()[0] + el["fs"].metrics()[1] for el in els if el["t"] == "Text") if any(
            el["t"] == "Text" for el in els) else 8
        margin = a_h / 2 + 1
        cands = []
        step = 3.0
        d = -xmin
        ds = []
        while d <= Ltot - xmax + 1e-6:
            ds.append(d)
            d += step
        for d in ds:
            pl = self.line_layout(path, cum, Ltot, d, xmin, xmax, els, margin)
            if pl is not None:
                cands.append((d, pl))
        if not cands:
            return
        mid = sorted(c[0] for c in cands)[len(cands) // 2]
        cands.sort(key=lambda c: abs(c[0] - mid))
        n_placed = 0
        for d, pl in cands:
            if n_placed >= 1 and not mins:
                break
            P = pl["anchor"]
            if mins:
                if any(math.hypot(q[0] - P[0], q[1] - P[1]) < mins for q in placed.get(key, [])):
                    continue
            lsurf = Surface(v.W, v.H)
            self.render_line_label(lsurf, pl, els)
            fp = lsurf.a > 0.02
            if not fp.any() or (fp & occ).any():
                continue
            self.commit(lsurf, occ)
            placed.setdefault(key, []).append(P)
            n_placed += 1

    def line_layout(self, path, cum, Ltot, d, xmin, xmax, els, margin):
        v = self.view

        def pt(s):
            if s < -1e-6 or s > Ltot + 1e-6:
                return None
            s = min(max(s, 0), Ltot)
            i = int(np.searchsorted(cum, s, side="right") - 1)
            i = min(max(i, 0), len(path) - 2)
            t = (s - cum[i]) / max(cum[i + 1] - cum[i], 1e-9)
            return path[i] + (path[i + 1] - path[i]) * t

        # reading direction (C13): never upside down
        p0, p1 = pt(d + xmin), pt(d + xmax)
        if p0 is None or p1 is None:
            return None
        dirn = 1 if (p1[0] - p0[0]) >= -1e-9 else -1
        S = lambda x: d + dirn * x
        anchor = pt(d)
        if anchor is None:
            return None
        inst = []
        angs = []
        for el in els:
            if el["t"] == "Text":
                fs = el["fs"]
                for ch, before, adv in el["glyphs"]:
                    xc = el["x0"] + before + adv / 2
                    sc = S(xc)
                    hw = max(adv, 3.0) / 2
                    a, b = pt(sc - dirn * hw), pt(sc + dirn * hw)
                    c = pt(sc)
                    if a is None or b is None or c is None:
                        return None
                    th = math.atan2(b[1] - a[1], b[0] - a[0])
                    if dirn == -1:
                        pass
                    if ch != " ":
                        angs.append(th)
                    inst.append(("glyph", ch, el, c, th, before, adv))
                    if not (margin <= c[0] <= v.W - margin and margin <= c[1] <= v.H - margin):
                        return None
            else:
                c = pt(S(el["x"]))
                if c is None:
                    return None
                th = math.atan2(*(pt(S(el["x"] + 1.5))[::-1] - pt(S(el["x"] - 1.5))[::-1])) if (
                    pt(S(el["x"] + 1.5)) is not None and pt(S(el["x"] - 1.5)) is not None) else 0.0
                up = (math.sin(th), -math.cos(th))
                c = (c[0] + up[0] * el["y"], c[1] + up[1] * el["y"])
                if not (0 <= c[0] <= v.W and 0 <= c[1] <= v.H):
                    return None
                inst.append(("dot", el, c))
        # bend limit (C14): at most 30 degrees between neighbouring glyphs
        for i in range(1, len(angs)):
            dd = (angs[i] - angs[i - 1] + math.pi) % (2 * math.pi) - math.pi
            if abs(dd) > math.radians(30):
                return None
        for th in angs:
            if abs(th) > math.radians(100):
                return None
        return {"anchor": (float(anchor[0]), float(anchor[1])), "inst": inst}

    def render_line_label(self, lsurf, pl, els):
        v = self.view
        # group text elements to keep per-element outline/glyph masks
        by_el = {}
        for it in pl["inst"]:
            if it[0] == "glyph":
                by_el.setdefault(id(it[2]), []).append(it)
        done = set()
        for it in pl["inst"]:
            if it[0] == "dot":
                el, c = it[1], it[2]
                fill_circle(lsurf, c[0], c[1], el["d"], el["col"], float(val(el["e"].get("opacity", 1), Ctx({}, {}))))
            else:
                el = it[2]
                if id(el) in done:
                    continue
                done.add(id(el))
                fs = el["fs"]
                acc = TextAcc(v.W, v.H)
                ref = valign_ref(fs, el["al"][1]) + el["y"]
                for (_, ch, _e, c, th, before, adv) in by_el[id(el)]:
                    if ch == " ":
                        continue
                    acc.add(ch, fs, adv / 2.0, ref, c, th)
                acc.paint(lsurf, fs)


def render_case(case_dir, out_path):
    r = Renderer(case_dir)
    surf = r.run()
    rgb = (np.clip(surf.rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(rgb, "RGB").save(out_path)
    if getattr(r, "nlabels", 0) or r.labels:
        r.notes.append("labels placed %d of %d candidates" % (getattr(r, "nlabels", 0), len(r.labels)))
    return r.notes


if __name__ == "__main__":
    notes = render_case(sys.argv[1], sys.argv[2])
    for n in notes:
        print("NOTE", n)
