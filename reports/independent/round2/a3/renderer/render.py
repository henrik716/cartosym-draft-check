"""Independent CartoSym renderer, written from the requirement text only.

Usage: python render.py <case-name> [<case-name> ...]
Writes out/<case>-1.png at the view's width and height.
"""
import copy
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont
from shapely.geometry import (LineString, MultiLineString, MultiPoint, MultiPolygon,
                              Point, Polygon, shape)
from shapely.ops import substring, transform, unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "cases")
OUT = os.path.join(ROOT, "out")
SS = 4            # supersampling factor for anti-aliasing
MM_PER_PX = 0.28  # standard pixel (view pixelSize_mm)
PT_MM = 25.4 / 72.0

NOTES = []        # (case, text) implementation notes collected during rendering


def note(case, text):
    NOTES.append((case, text))


# ---------------------------------------------------------------- units
class Unit:
    """Converts uom-qualified values to device pixels (map pixels times SS)."""

    def __init__(self, scale_den):
        self.scale_den = scale_den

    def dev(self, v):
        """v is {unit: value} or a plain number (pixels). Returns device px or None."""
        if v is None:
            return None
        if isinstance(v, dict):
            if not v:
                return None
            unit, val = next(iter(v.items()))
        else:
            unit, val = "px", v
        if val is None:
            return None
        if unit in ("px", "pixel", "pixels"):
            px = float(val)
        elif unit in ("mm", "millimeter", "screenMM"):
            px = float(val) / MM_PER_PX
        elif unit in ("cm", "screenCM"):
            px = float(val) * 10.0 / MM_PER_PX
        elif unit in ("inch", "in", "screenInches"):
            px = float(val) * 25.4 / MM_PER_PX
        elif unit in ("pt", "points"):
            px = float(val) * PT_MM / MM_PER_PX
        elif unit in ("m", "meter", "meters"):
            px = float(val) / (MM_PER_PX * 1e-3 * self.scale_den)
        elif unit in ("ft", "feet", "foot"):
            px = float(val) * 0.3048 / (MM_PER_PX * 1e-3 * self.scale_den)
        else:
            note("*", f"unsupported unit '{unit}' treated as unsupported value")
            return None
        return px * SS


# ---------------------------------------------------------------- expressions
def _like(text, pattern):
    out = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\" and i + 1 < len(pattern):
            out.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        if c == "%":
            out.append(".*")
        elif c == "_":
            out.append(".")
        else:
            out.append(re.escape(c))
        i += 1
    return re.fullmatch("".join(out), text, re.S) is not None


def ev(node, ctx):
    """Evaluate a CartoSym-JSON expression. Null (None) propagates as CQL2 does."""
    if isinstance(node, list):
        return [ev(x, ctx) for x in node]
    if not isinstance(node, dict):
        return node
    if "property" in node:
        return ctx["props"].get(node["property"])
    if "sysId" in node:
        return ctx["sys"].get(node["sysId"])
    if "op" not in node:
        return node
    op = node["op"]
    a = node.get("args", [])
    if op == "and":
        vals = [ev(x, ctx) for x in a]
        if any(v is False for v in vals):
            return False
        if all(v is True for v in vals):
            return True
        return None
    if op == "or":
        vals = [ev(x, ctx) for x in a]
        if any(v is True for v in vals):
            return True
        if all(v is False for v in vals):
            return False
        return None
    if op == "?:":
        c = ev(a[0], ctx)
        if c is True:
            return ev(a[1], ctx)
        if c is False:
            return ev(a[2], ctx)
        return None
    if op == "isNull":
        return ev(a[0], ctx) is None
    if op == "not":
        v = ev(a[0], ctx)
        return None if v is None else (not v)
    if op == "in":
        x = ev(a[0], ctx)
        if len(a) == 2 and isinstance(a[1], list):
            items = [ev(e, ctx) for e in a[1]]
        else:
            items = [ev(e, ctx) for e in a[1:]]
        if x is None:
            return None
        return x in items
    vals = [ev(x, ctx) for x in a]
    if op == "abs":
        return None if vals[0] is None else abs(vals[0])
    if any(v is None for v in vals):
        return None
    x = vals[0] if vals else None
    y = vals[1] if len(vals) > 1 else None
    if op == "=":
        return x == y
    if op in ("!=", "<>"):
        return x != y
    if op == "<":
        return x < y
    if op == "<=":
        return x <= y
    if op == ">":
        return x > y
    if op == ">=":
        return x >= y
    if op == "like":
        return _like(str(x), str(y))
    if op == "notLike":
        return not _like(str(x), str(y))
    if op == "contains":
        return str(y) in str(x)
    if op == "startsWith":
        return str(x).startswith(str(y))
    if op == "endsWith":
        return str(x).endswith(str(y))
    if op == "+":
        return x + y
    if op == "-":
        return x - y
    if op == "*":
        return x * y
    if op == "/":
        return None if y == 0 else x / y
    note("*", f"operator '{op}' not implemented; evaluated to null")
    return None


def is_expr(d):
    return isinstance(d, dict) and ("op" in d or "property" in d or "sysId" in d)


def evaluate_tree(x, ctx):
    if is_expr(x):
        return ev(x, ctx)
    if isinstance(x, dict):
        return {k: evaluate_tree(v, ctx) for k, v in x.items()}
    if isinstance(x, list):
        return [evaluate_tree(v, ctx) for v in x]
    return x


# ---------------------------------------------------------------- style
DEFAULT_SYM = {
    "visibility": True,
    "opacity": 1,
    "zOrder": 1,
    "fill": {"color": "white", "opacity": 1},
    "stroke": {"color": "black", "opacity": 1, "width": {"px": 1}},
    "marker": {"elements": [{"type": "Dot", "size": {"px": 10}, "color": "white"}]},
}


def merge(dst, src):
    """Override dst with src. Object members merge; a null replaces the value."""
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict) and not is_expr(v):
            merged = dict(dst[k])
            merge(merged, v)
            dst[k] = merged
        else:
            dst[k] = copy.deepcopy(v)
    return dst


def apply_rules(rules, ctx, acc, hits):
    for r in rules:
        sel = r.get("selector")
        if sel is not None:
            v = ev(sel, ctx)
            if v is not True:
                continue
            s = json.dumps(sel)
            if "viz.pass" in s:
                hits.add("viz")
            if "feature.pass" in s:
                hits.add("feat")
        sym = r.get("symbolizer")
        if sym:
            merge(acc, sym)
        if r.get("nestedRules"):
            apply_rules(r["nestedRules"], ctx, acc, hits)


def resolve(style_rules, props, sysv, geom_dim):
    ctx = {"props": props, "sys": dict(sysv)}
    ctx["sys"]["feature.geometryDimension"] = geom_dim
    acc = copy.deepcopy(DEFAULT_SYM)
    hits = set()
    apply_rules(style_rules, ctx, acc, hits)
    sym = evaluate_tree(acc, ctx)
    return sym, hits


def walk_constants(node, key, found):
    if isinstance(node, dict):
        if node.get("op") == "=" and isinstance(node.get("args"), list) and len(node["args"]) == 2:
            a, b = node["args"]
            if isinstance(a, dict) and a.get("sysId") == key and isinstance(b, (int, float)) \
                    and not isinstance(b, bool):
                found.add(int(b))
        for v in node.values():
            walk_constants(v, key, found)
    elif isinstance(node, list):
        for v in node:
            walk_constants(v, key, found)
    return found


def parse_color(v):
    """Returns (r, g, b) in 0..1, or None for null."""
    if v is None:
        return (0.0, 0.0, 0.0)
    if isinstance(v, str):
        if v.startswith("#"):
            rgb = ImageColor.getrgb(v)
        else:
            rgb = ImageColor.getrgb(v.lower())
        return tuple(c / 255.0 for c in rgb[:3])
    if isinstance(v, dict):
        v = [v.get("r", 0), v.get("g", 0), v.get("b", 0)]
    if isinstance(v, list) and len(v) == 3:
        return tuple(min(1.0, max(0.0, float(c) / 255.0)) for c in v)
    note("*", f"unrecognised colour {v!r}; drawn black")
    return (0.0, 0.0, 0.0)


def num(v, default=None):
    if v is None:
        return default
    return float(v)


# ---------------------------------------------------------------- raster helpers
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w * SS, h * SS
        self.a = np.empty((self.h, self.w, 3), dtype=np.float32)
        self.a[:] = np.array(parse_color(bg), dtype=np.float32)

    def comp(self, mask, color, alpha):
        if alpha <= 0 or mask is None:
            return
        m = (mask * alpha)[..., None]
        self.a *= (1.0 - m)
        self.a += m * np.array(color, dtype=np.float32)

    def out(self, w, h):
        v = self.a.reshape(h, SS, w, SS, 3).mean(axis=(1, 3))
        return Image.fromarray(np.clip(v * 255 + 0.5, 0, 255).astype(np.uint8), "RGB")


def polys_of(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon) or g.geom_type == "GeometryCollection":
        out = []
        for x in g.geoms:
            out += polys_of(x)
        return out
    return []


def lines_of(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    if isinstance(g, MultiLineString) or g.geom_type == "GeometryCollection":
        out = []
        for x in g.geoms:
            out += lines_of(x)
        return out
    return []


def raster(canvas, geom):
    arr = np.zeros((canvas.h, canvas.w), dtype=np.float32)
    for p in polys_of(geom):
        im = Image.new("L", (canvas.w, canvas.h), 0)
        d = ImageDraw.Draw(im)
        d.polygon(list(p.exterior.coords), fill=255)
        for r in p.interiors:
            d.polygon(list(r.coords), fill=0)
        arr = np.maximum(arr, np.asarray(im, dtype=np.float32) / 255.0)
    return arr


CAP = {"round": "round", "butt": "flat", "square": "square"}
JOIN = {"round": "round", "bevel": "bevel", "miter": "mitre"}


def stroke_geom(lines, width, cap, join, dash, offset):
    """Union of the buffered line pieces (device px)."""
    pieces = []
    for ln in lines:
        if dash:
            pieces += dash_pieces(ln, dash, offset)
        else:
            pieces.append(ln)
    bufs = []
    for p in pieces:
        if p.length <= 0 or p.is_empty:
            continue
        bufs.append(p.buffer(width / 2.0, quad_segs=8, cap_style=CAP.get(cap, "round"),
                             join_style=JOIN.get(join, "round")))
    if not bufs:
        return None
    return unary_union(bufs)


def dash_pieces(line, pattern, offset):
    total = line.length
    pat = list(pattern)
    if len(pat) % 2 == 1:
        pat = pat * 2
    period = sum(pat)
    if period <= 0 or total <= 0:
        return [line]
    out = []
    x = -offset
    i = 0
    guard = 0
    while x < total and guard < 1000000:
        L = pat[i % len(pat)]
        a, b = x, x + L
        if i % 2 == 0:
            lo, hi = max(a, 0.0), min(b, total)
            if hi - lo > 1e-9:
                out.append(substring(line, lo, hi))
        x = b
        i += 1
        guard += 1
    return out


# ---------------------------------------------------------------- rendering
class Renderer:
    def __init__(self, case, case_dir):
        self.case = case
        self.dir = case_dir
        self.view = json.load(open(os.path.join(case_dir, "view-1.json"), encoding="utf-8"))
        self.style = json.load(open(os.path.join(case_dir, "style.cs.json"), encoding="utf-8"))
        self.rules = self.style["stylingRules"]
        self.W = int(self.view["width"])
        self.H = int(self.view["height"])
        minx, miny, maxx, maxy = self.view["bbox"]
        self.bbox = (minx, miny, maxx, maxy)
        self.unit = Unit(float(self.view["scaleDenominator"]))
        rx = (maxx - minx) / self.W
        ry = (maxy - miny) / self.H
        if abs(rx - ry) > 1e-9 * max(rx, ry):
            note(case, "view bbox aspect differs from width/height; used separate x and y scales")
        self.canvas = Canvas(self.W, self.H, self.view.get("background", "#ffffff"))
        self.layers = []
        for L in self.view["layers"]:
            self.layers.append(L["id"])
        self.feat_pass_consts = set()
        self.viz_consts = set()
        walk_constants(self.rules, "feature.pass", self.feat_pass_consts)
        walk_constants(self.rules, "viz.pass", self.viz_consts)
        self.labels = []     # (device anchor etc)
        self.label_keys = set()

    # map -> device
    def to_dev(self, x, y):
        minx, miny, maxx, maxy = self.bbox
        X = (x - minx) / (maxx - minx) * self.W * SS
        Y = (maxy - y) / (maxy - miny) * self.H * SS
        return X, Y

    def geom_dev(self, g):
        return transform(lambda xs, ys: self.to_dev_arr(xs, ys), g)

    def to_dev_arr(self, xs, ys):
        minx, miny, maxx, maxy = self.bbox
        X = [(x - minx) / (maxx - minx) * self.W * SS for x in xs]
        Y = [(maxy - y) / (maxy - miny) * self.H * SS for y in ys]
        return X, Y

    def load_layer(self, lid):
        path = os.path.join(self.dir, lid + ".geojson")
        if not os.path.exists(path):
            note(self.case, f"layer '{lid}' has no data file; skipped")
            return []
        d = json.load(open(path, encoding="utf-8"))
        feats = []
        for i, f in enumerate(d["features"]):
            if f.get("geometry") is None:
                continue
            g = shape(f["geometry"])
            feats.append({"idx": i, "props": f.get("properties") or {}, "geom": self.geom_dev(g),
                          "gtype": g.geom_type, "id": f.get("id", i)})
        return feats

    @staticmethod
    def dim_of(gtype):
        if "Point" in gtype:
            return 0
        if "Line" in gtype:
            return 1
        return 2

    def run(self):
        layer_feats = {lid: self.load_layer(lid) for lid in self.layers}
        # layer-level dimension
        layer_dim = {}
        for lid, feats in layer_feats.items():
            dims = {self.dim_of(f["gtype"]) for f in feats}
            layer_dim[lid] = dims.pop() if len(dims) == 1 else None
        viz_list = sorted(self.viz_consts) if self.viz_consts else []
        feat_list = sorted(self.feat_pass_consts) if self.feat_pass_consts else []

        items = []   # dicts with vp, z, layer index, feature index, fp, sym
        for li, lid in enumerate(self.layers):
            for f in layer_feats[lid]:
                dim = self.dim_of(f["gtype"])
                base = {"dataLayer.id": lid, "dataLayer.featuresGeometryDimensions": layer_dim[lid],
                        "feature.identifier": f["id"]}
                vps = []
                for c in viz_list:
                    for fpc in feat_list + [None]:
                        _, hits = resolve(self.rules, f["props"],
                                          dict(base, **{"viz.pass": c, "feature.pass": fpc}), dim)
                        if "viz" in hits:
                            vps.append(c)
                            break
                if not vps:
                    vps = [None]
                for vp in vps:
                    fps = []
                    for c in feat_list:
                        _, hits = resolve(self.rules, f["props"],
                                          dict(base, **{"viz.pass": vp, "feature.pass": c}), dim)
                        if "feat" in hits:
                            fps.append(c)
                    if not fps:
                        fps = [None]
                    for fp in fps:
                        sysv = dict(base, **{"viz.pass": vp, "feature.pass": fp})
                        sym, _ = resolve(self.rules, f["props"], sysv, dim)
                        if sym.get("visibility") is False:
                            continue
                        z = sym.get("zOrder")
                        z = 0 if z is None else int(z)
                        items.append({"vp": vp, "z": z, "li": li, "f": f, "fp": fp, "sym": sym,
                                      "dim": dim, "lid": lid})

        vp_order = sorted({it["vp"] for it in items}, key=lambda v: (v is not None, v if v is not None else 0))
        for vp in vp_order:
            sub_vp = [it for it in items if it["vp"] == vp]
            for z in sorted({it["z"] for it in sub_vp}):
                sub = sorted([it for it in sub_vp if it["z"] == z],
                             key=lambda it: (it["li"], it["f"]["idx"], -1 if it["fp"] is None else it["fp"]))
                for it in sub:
                    self.draw_casing(it)
                for it in sub:
                    self.draw_main(it)
                for it in sub:
                    self.draw_center(it)
        # labels: separate pass on top of all features
        self.draw_labels(items)
        return self.canvas.out(self.W, self.H)

    # ---- strokes
    def stroke_params(self, st, which):
        if not st:
            return None
        width = self.unit.dev(st.get("width"))
        if which == "casing" or which == "center":
            pass
        if width is None:
            width = 0.0
        if width <= 0:
            return None
        color = parse_color(st.get("color"))
        alpha = num(st.get("opacity"), 1.0)
        dash = []
        pat = st.get("dashPattern")
        if pat:
            dash = [self.unit.dev(p if isinstance(p, dict) else {"px": p}) or 0.0 for p in pat]
            if not any(d > 0 for d in dash):
                dash = []
        off = self.unit.dev(st.get("dashOffset")) or 0.0
        return {"w": width, "color": color, "alpha": alpha, "dash": dash, "off": off,
                "cap": st.get("cap", "round"), "join": st.get("join", "round")}

    def lines_for(self, it):
        g = it["f"]["geom"]
        if it["dim"] == 1:
            return lines_of(g)
        if it["dim"] == 2:
            out = []
            for p in polys_of(g):
                out.append(p.exterior)
                out += list(p.interiors)
            return [LineString(r.coords) for r in out]
        return []

    def draw_stroke_layer(self, it, which):
        sym = it["sym"]
        st = sym.get("stroke")
        if not st:
            return
        if which == "casing":
            inner = st.get("casing")
            if not inner:
                return
            p = self.stroke_params(inner, which)
            if p is None:
                return
            # the casing extends beyond each side of the main stroke
            main = self.stroke_params(st, "main")
            if main is None:
                return
            p = dict(p)
            p["w"] = main["w"] + 2 * p["w"]
            p["dash"], p["off"] = main["dash"], main["off"]
        elif which == "center":
            inner = st.get("center")
            if not inner:
                return
            p = self.stroke_params(inner, which)
            if p is None:
                return
        else:
            p = self.stroke_params(st, "main")
            if p is None:
                return
        lines = self.lines_for(it)
        if not lines:
            return
        g = stroke_geom(lines, p["w"], p["cap"], p["join"], p["dash"], p["off"])
        if g is None:
            return
        alpha = p["alpha"] * num(sym.get("opacity"), 1.0)
        self.canvas.comp(raster(self.canvas, g), p["color"], alpha)

    def draw_casing(self, it):
        self.draw_stroke_layer(it, "casing")

    def draw_center(self, it):
        self.draw_stroke_layer(it, "center")

    def draw_main(self, it):
        sym = it["sym"]
        op = num(sym.get("opacity"), 1.0)
        # fill (polygons only)
        fill = sym.get("fill")
        if fill and it["dim"] == 2:
            if fill.get("pattern"):
                if (it["lid"], "pattern") not in getattr(self, "_noted", set()):
                    self._noted = getattr(self, "_noted", set()) | {(it["lid"], "pattern")}
                    note(self.case, "fill with an SVG image pattern (fill.pattern) is not implemented; "
                                    "the fill is skipped for those features")
            else:
                col = parse_color(fill.get("color"))
                mask = raster(self.canvas, it["f"]["geom"])
                self.canvas.comp(mask, col, num(fill.get("opacity"), 1.0) * op)
        # stroke
        self.draw_stroke_layer(it, "main")
        # marker
        mk = sym.get("marker")
        if mk and mk.get("elements"):
            anchors = self.marker_anchors(it)
            for el in mk["elements"]:
                self.draw_dot_marker(el, anchors, op)

    def marker_anchors(self, it):
        g = it["f"]["geom"]
        if it["dim"] == 0:
            pts = []
            for p in (g.geoms if hasattr(g, "geoms") else [g]):
                pts.append(p)
            return [(p.x, p.y) for p in pts]
        if it["dim"] == 1:
            out = []
            for ln in lines_of(g):
                out += list(ln.coords)
            return out
        c = g.centroid
        return [(c.x, c.y)]

    def draw_dot_marker(self, el, anchors, op):
        if el.get("type") != "Dot":
            note(self.case, f"marker element type '{el.get('type')}' not implemented")
            return
        size = el.get("size")
        if size is None:
            size = (el.get("stroke") or {}).get("width")
        d = self.unit.dev(size)
        if d is None or d <= 0:
            return
        col = el.get("color")
        if col is None:
            col = (el.get("stroke") or {}).get("color")
        color = parse_color(col)
        alpha = num((el.get("stroke") or {}).get("opacity"), 1.0) * op
        r = d / 2.0
        for (x, y) in anchors:
            X, Y = x, y
            im = Image.new("L", (self.canvas.w, self.canvas.h), 0)
            ImageDraw.Draw(im).ellipse([X - r, Y - r, X + r, Y + r], fill=255)
            self.canvas.comp(np.asarray(im, dtype=np.float32) / 255.0, color, alpha)

    # ---- labels
    def draw_labels(self, items):
        boxes = []
        done = set()
        for it in items:
            lab = it["sym"].get("label")
            if not lab or not lab.get("elements"):
                continue
            key = (it["lid"], it["f"]["idx"], json.dumps(lab, sort_keys=True))
            if key in done:
                continue
            done.add(key)
            anchor = self.label_anchor(it)
            if anchor is None:
                continue
            for el in lab["elements"]:
                if el.get("type") != "Text":
                    note(self.case, f"label element '{el.get('type')}' not implemented")
                    continue
                boxes = self.draw_text(el, anchor, boxes, it)

    def label_anchor(self, it):
        g = it["f"]["geom"]
        if it["dim"] == 0:
            p = g if isinstance(g, Point) else g.geoms[0]
            return (p.x, p.y)
        if it["dim"] == 1:
            ls = lines_of(g)
            if not ls:
                return None
            ln = max(ls, key=lambda l: l.length)
            m = ln.interpolate(0.5, normalized=True)
            return (m.x, m.y)
        rp = g.representative_point()
        return (rp.x, rp.y)

    def draw_text(self, el, anchor, boxes, it):
        text = el.get("text")
        if text is None:
            return boxes
        text = str(text)
        font_spec = el.get("font") or {}
        size_pt = num(font_spec.get("size"), 10.0)
        px = size_pt * PT_MM / MM_PER_PX * SS
        try:
            font = ImageFont.load_default(size=px)
        except TypeError:
            font = ImageFont.load_default()
        color = parse_color(font_spec.get("color"))
        al = el.get("alignment") or ["left", "top"]
        if isinstance(al, str):
            al = al.split()
        horz = al[0] if len(al) > 0 else "left"
        vert = al[1] if len(al) > 1 else "top"
        hmap = {"left": "l", "center": "m", "right": "r"}
        vmap = {"top": "a", "middle": "m", "bottom": "d"}
        anchor_code = hmap.get(horz, "l") + vmap.get(vert, "a")
        pos = el.get("position") or [{"px": 0}, {"px": 0}]
        ox = self.unit.dev(pos[0]) or 0.0
        oy = self.unit.dev(pos[1]) or 0.0
        X, Y = anchor  # already device coordinates
        X += ox
        Y += oy
        im = Image.new("L", (self.canvas.w, self.canvas.h), 0)
        d = ImageDraw.Draw(im)
        d.text((X, Y), text, font=font, fill=255, anchor=anchor_code)
        bb = d.textbbox((X, Y), text, font=font, anchor=anchor_code)
        for b in boxes:
            if not (bb[2] < b[0] or bb[0] > b[2] or bb[3] < b[1] or bb[1] > b[3]):
                note(self.case, "a label overlapped an earlier label and was omitted")
                return boxes
        boxes.append(bb)
        self.canvas.comp(np.asarray(im, dtype=np.float32) / 255.0, color, 1.0)
        return boxes


def render_case(case):
    case_dir = os.path.join(CASES, case)
    r = Renderer(case, case_dir)
    img = r.run()
    os.makedirs(OUT, exist_ok=True)
    img.save(os.path.join(OUT, f"{case}-1.png"))
    return img.size


if __name__ == "__main__":
    targets = sys.argv[1:] or sorted(os.listdir(CASES))
    for c in targets:
        try:
            size = render_case(c)
            print(c, "ok", size)
        except Exception as e:  # keep going; report
            import traceback
            traceback.print_exc()
            print(c, "FAILED", e)
    for c, t in NOTES:
        print("NOTE", c, t)
