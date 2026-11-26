"""Independent CartoSym-JSON renderer written from the text of the OGC CartoSym 2.0 Part 1 draft only.

Usage: python renderer/render.py <case-dir> [<out.png>]
       python renderer/render.py --all <cases-dir> <out-dir>

The labels N-... in comments refer to the numbered choices in notes.md.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colors import NAMED  # noqa: E402
from expr import Context, evaluate, is_expression, collect_pass_values, references_vendor_sysid  # noqa: E402
from raster import Canvas, stroke_coverage, fill_coverage, dash_polyline  # noqa: E402

MISSING = object()

# Requirements classes this renderer implements (for capabilities.* System Identifiers)
CAPABILITIES = {
    "capabilities.vector": True, "capabilities.labels": True, "capabilities.dashes": True,
    "capabilities.casing": True, "capabilities.conditional": True, "capabilities.parametervalues": True,
    "capabilities.coverage": False, "capabilities.hillshading": False, "capabilities.fontoutlines": False,
    "capabilities.hatches": False, "capabilities.stipples": False, "capabilities.dotpatterns": False,
    "capabilities.functions": False, "capabilities.math": False, "capabilities.arrayrelations": False,
    "capabilities.textmanipulation": False, "capabilities.arithmetic": False, "capabilities.textrelation": False,
    "capabilities.righthand": True, "capabilities.variables": False,
}

# Members of Symbolizer objects that belong to requirements classes this renderer does not implement.
# They are ignored, member by member (N-UNKNOWN-MEMBERS).
IGNORED_MEMBERS = {"pattern", "patternGap", "patternInitialGap", "cap", "join", "transform"}


# --------------------------------------------------------------------------------------------
# Symbolizer resolution (/req/core/rules, /req/core/nested, /req/json/partial-update)
# --------------------------------------------------------------------------------------------

def merge(old, new):
    """Value of a property after a rule assigns `new` over `old`."""
    if isinstance(new, dict) and not is_expression(new):
        if "index" in new and "value" in new and len(new) == 2:
            # /req/json/array-element-update
            base = list(old) if isinstance(old, list) else []
            i = int(new["index"])
            while len(base) <= i:
                base.append(None)
            base[i] = merge(base[i], new["value"])
            return base
        if new.get("alter") is True:
            # /req/json/partial-update: preserve what is not specified
            base = dict(old) if isinstance(old, dict) and not is_expression(old) else {}
            for k, v in new.items():
                if k == "alter":
                    continue
                base[k] = merge(base.get(k, MISSING), v)
            return base
    return new  # complete replacement (a new instance; unspecified members take their defaults)


def apply_symbolizer(sym, s):
    for k, v in s.items():
        if k.startswith("$") or k.startswith("vendor."):
            continue  # comments, vendor extensions not understood (clause 7, Vendor Extensions)
        sym[k] = merge(sym.get(k, MISSING), v)


def resolve_rules(rules, ctx, sym):
    for r in rules:
        sel = r.get("selector")
        if sel is not None:
            if references_vendor_sysid(sel):
                continue  # whole rule ignored (clause 7, Vendor Extensions)
            if evaluate(sel, ctx) is not True:  # null does not select (NOTE under /req/core/selector)
                continue
        if "symbolizer" in r and r["symbolizer"] is not None:
            apply_symbolizer(sym, r["symbolizer"])
        if r.get("nestedRules"):
            resolve_rules(r["nestedRules"], ctx, sym)  # N-RULE-ORDER: depth first, document order
    return sym


# --------------------------------------------------------------------------------------------
# Values
# --------------------------------------------------------------------------------------------

class Env:
    def __init__(self, view):
        self.view = view
        self.W, self.H = int(view["width"]), int(view["height"])
        self.minx, self.miny, self.maxx, self.maxy = view["bbox"]
        self.sx = self.W / (self.maxx - self.minx)
        self.sy = self.H / (self.maxy - self.miny)
        self.px_per_m = self.sx  # N-GROUND-UNITS
        self.pixel_mm = float(view.get("pixelSize_mm", 0.28))

    def to_px(self, xy):
        return ((xy[0] - self.minx) * self.sx, (self.maxy - xy[1]) * self.sy)


def rv(v, ctx):
    """Resolve a Parameter Value (an expression or a literal)."""
    return evaluate(v, ctx) if is_expression(v) else v


def to_px(v, env, ctx, font_pt=10.0):
    """uom-qualified value -> pixels (/req/vector/units); a number without unit is in pixels."""
    v = rv(v, ctx)
    if v is None:
        return 0.0  # /req/parameter-values/null: number -> 0
    if isinstance(v, bool):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        for unit, x in v.items():
            x = rv(x, ctx)
            if x is None:
                return 0.0
            x = float(x)
            if unit == "px":
                return x
            if unit == "m":
                return x * env.px_per_m
            if unit == "ft":
                return x * 0.3048 * env.px_per_m
            if unit == "mm":
                return x / env.pixel_mm
            if unit == "cm":
                return x * 10.0 / env.pixel_mm
            if unit == "inch":
                return x * 25.4 / env.pixel_mm
            if unit == "pt":
                return x * 25.4 / 72.0 / env.pixel_mm
            if unit == "em":
                return x * font_pt * 25.4 / 72.0 / env.pixel_mm
            # 'pc' has no meaning for a length outside hotSpot/scaling
            return 0.0
    return 0.0


def to_color(v, ctx):
    v = rv(v, ctx)
    if v is None:
        return (0, 0, 0)  # /req/parameter-values/null: Color -> black
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("#") and len(s) == 7:
            return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))
        c = NAMED.get(s.lower())
        if c is not None:
            return c
        return (0, 0, 0)
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        return tuple(float(rv(x, ctx) or 0) for x in v[:3])
    if isinstance(v, dict):
        return tuple(float(rv(v.get(k, 0), ctx) or 0) for k in ("r", "g", "b"))
    return (0, 0, 0)


def to_num(v, ctx, default):
    v = rv(v, ctx)
    if v is MISSING:
        return default
    if v is None or isinstance(v, bool):
        return 0.0
    try:
        return float(v)
    except Exception:
        return 0.0


def sym_get(sym, key, ctx, default):
    if key not in sym:
        return default
    return rv(sym[key], ctx)


# Default values (clause 7, "Default class member values")
def default_dot():
    return {"type": "Dot"}


def get_fill(sym, ctx):
    f = sym_get(sym, "fill", ctx, {})
    if f is None or not isinstance(f, dict):
        return None
    return {
        "color": to_color(f.get("color", "white"), ctx),
        "opacity": to_num(f.get("opacity", MISSING), ctx, 1.0),
    }


def get_styling(s, ctx, env, default_width, default_color="black"):
    return {
        "color": to_color(s.get("color", default_color), ctx),
        "opacity": to_num(s.get("opacity", MISSING), ctx, 1.0),
        "width": to_px(s["width"], env, ctx) if "width" in s else default_width,
    }


def get_stroke(sym, ctx, env):
    s = sym_get(sym, "stroke", ctx, {})
    if s is None or not isinstance(s, dict):
        return None
    st = get_styling(s, ctx, env, 1.0)
    cas = rv(s.get("casing"), ctx) if "casing" in s else None
    cen = rv(s.get("center"), ctx) if "center" in s else None
    st["casing"] = get_styling(cas, ctx, env, 0.0) if isinstance(cas, dict) else None  # N-CASING-DEFAULT
    st["center"] = get_styling(cen, ctx, env, 0.0) if isinstance(cen, dict) else None
    dp = rv(s.get("dashPattern"), ctx) if "dashPattern" in s else None
    st["dash"] = [to_px(x, env, ctx) for x in dp] if isinstance(dp, list) and dp else None
    st["dashOffset"] = to_px(s["dashOffset"], env, ctx) if "dashOffset" in s else 0.0
    return st


def get_graphics(sym, key, ctx, default):
    m = sym_get(sym, key, ctx, default)
    if m is None:
        return []
    if isinstance(m, dict):
        if "elements" in m:
            els = rv(m["elements"], ctx)
            return [rv(e, ctx) for e in (els or []) if e is not None]
        # an empty marker object still yields the default Dot (NOTE under /req/core/default-values)
        return [default_dot()] if key == "marker" else []
    return []


# --------------------------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------------------------

def geom_dim(g):
    t = g["type"]
    return {"Point": 0, "MultiPoint": 0, "LineString": 1, "MultiLineString": 1, "Polygon": 2, "MultiPolygon": 2}.get(t)


def geom_parts(g, env):
    """Returns (points, lines, polygons) in pixel coordinates."""
    t, c = g["type"], g["coordinates"]
    P = lambda seq: np.array([env.to_px(p) for p in seq], dtype=np.float64)
    if t == "Point":
        return [np.array(env.to_px(c))], [], []
    if t == "MultiPoint":
        return [np.array(env.to_px(p)) for p in c], [], []
    if t == "LineString":
        return [], [P(c)], []
    if t == "MultiLineString":
        return [], [P(l) for l in c], []
    if t == "Polygon":
        return [], [], [[P(r) for r in c]]
    if t == "MultiPolygon":
        return [], [], [[P(r) for r in poly] for poly in c]
    return [], [], []


def ring_area_centroid(r):
    x, y = r[:, 0], r[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y1 - x1 * y
    a = cr.sum() / 2.0
    if a == 0:
        return 0.0, r.mean(axis=0)
    cx = ((x + x1) * cr).sum() / (6 * a)
    cy = ((y + y1) * cr).sum() / (6 * a)
    return a, np.array([cx, cy])


def polygon_centroid(rings):
    """Area centroid of a polygon with holes (exterior minus interiors)."""
    A, S = 0.0, np.zeros(2)
    for i, r in enumerate(rings):
        a, c = ring_area_centroid(r)
        a = abs(a) * (1 if i == 0 else -1)
        A += a
        S += a * c
    return S / A if A != 0 else rings[0].mean(axis=0)


def line_midpoint(line):
    seg = np.hypot(*(line[1:] - line[:-1]).T)
    total = seg.sum()
    if total == 0:
        return line[0]
    half = total / 2
    cum = np.concatenate([[0], np.cumsum(seg)])
    i = int(np.searchsorted(cum, half, side="right") - 1)
    i = min(i, len(seg) - 1)
    t = (half - cum[i]) / seg[i] if seg[i] else 0
    return line[i] + t * (line[i + 1] - line[i])


# --------------------------------------------------------------------------------------------
# Graphics
# --------------------------------------------------------------------------------------------

_FONT_DIR = None


def font_file(face, bold, italic):
    global _FONT_DIR
    if _FONT_DIR is None:
        import matplotlib
        _FONT_DIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    face = (face or "").lower()
    fam = "DejaVuSans"
    if "mono" in face or "courier" in face:
        fam = "DejaVuSansMono"
    elif ("serif" in face and "sans" not in face) or "times" in face:
        fam = "DejaVuSerif"
    style = ("Bold" if bold else "") + (("Italic" if fam == "DejaVuSerif" else "Oblique") if italic else "")
    name = fam + ("-" + style if style else "") + ".ttf"
    p = os.path.join(_FONT_DIR, name)
    return p if os.path.exists(p) else os.path.join(_FONT_DIR, "DejaVuSans.ttf")


def text_layout(el, ctx, env):
    """Returns (font, text, color, opacity, dx_left, dy_baseline, width, ascent, descent) relative to the anchor."""
    txt = rv(el.get("text"), ctx)
    txt = "" if txt is None else (str(txt) if not isinstance(txt, float) or not txt.is_integer() else str(int(txt)))
    f = rv(el.get("font", {}), ctx) or {}
    size_pt = to_num(f.get("size", MISSING), ctx, 10.0)  # N-FONT-DEFAULTS
    bold = rv(f.get("bold", False), ctx) is True
    italic = rv(f.get("italic", False), ctx) is True
    color = to_color(f.get("color", "black"), ctx)
    opacity = to_num(f.get("opacity", MISSING), ctx, 1.0)
    size_px = size_pt * 25.4 / 72.0 / env.pixel_mm
    font = ImageFont.truetype(font_file(rv(f.get("face"), ctx), bold, italic), size_px)
    asc, desc = font.getmetrics()
    width = font.getlength(txt)
    al = rv(el.get("alignment", ["left", "top"]), ctx)
    if isinstance(al, dict):
        h = al.get("hAlignment", al.get("horzAlignment", al.get("horizontal", "left")))
        v = al.get("vAlignment", al.get("vertAlignment", al.get("vertical", "top")))
    elif isinstance(al, list) and len(al) == 2:
        h, v = al
    else:
        h, v = "left", "top"
    dx = {"left": 0.0, "center": -width / 2.0, "right": -width}.get(h, 0.0)
    dy = {"top": asc, "middle": (asc - desc) / 2.0, "bottom": -desc}.get(v, asc)  # baseline offset
    return font, txt, color, opacity, dx, dy, width, asc, desc


def draw_text(canvas, x, y, el, ctx, env, opacity_mult=1.0):
    font, txt, color, op, dx, dy, width, asc, desc = text_layout(el, ctx, env)
    if not txt:
        return
    mask = Image.new("L", (canvas.w, canvas.h), 0)
    ImageDraw.Draw(mask).text((x + dx, y + dy), txt, font=font, fill=255, anchor="ls")
    cov = np.asarray(mask, dtype=np.float64) / 255.0
    canvas.paint(cov, color, op * opacity_mult)


def graphic_offset(el, ctx, env):
    pos = rv(el.get("position"), ctx) if "position" in el else None
    if isinstance(pos, list) and len(pos) >= 2:
        return to_px(pos[0], env, ctx), to_px(pos[1], env, ctx)
    if isinstance(pos, dict):
        return to_px(pos.get("x", 0), env, ctx), to_px(pos.get("y", 0), env, ctx)
    return 0.0, 0.0


def draw_graphic(canvas, x, y, el, ctx, env, opacity_mult, warnings):
    if not isinstance(el, dict):
        return
    ox, oy = graphic_offset(el, ctx, env)
    x, y = x + ox, y + oy  # /req/vector/graphics: +x right, +y down
    gop = to_num(el.get("opacity", MISSING), ctx, 1.0) * opacity_mult
    t = el.get("type", "Dot")
    if t == "Dot":
        st = rv(el.get("stroke"), ctx) if "stroke" in el else None
        st = st if isinstance(st, dict) else {}
        size = to_px(el["size"], env, ctx) if "size" in el else (to_px(st["width"], env, ctx) if "width" in st else 10.0)
        color = to_color(el["color"], ctx) if "color" in el else (to_color(st["color"], ctx) if "color" in st else (255, 255, 255))
        sop = to_num(st.get("opacity", MISSING), ctx, 1.0)
        cov, win = stroke_coverage([np.array([[x, y]])], size, canvas.w, canvas.h)
        canvas.paint(cov, color, gop * sop, win)
    elif t == "Text":
        draw_text(canvas, x, y, el, ctx, env, gop)
    elif t == "Image":
        warnings.add("Image graphic not drawn (no image graphics in these cases were implemented)")


# --------------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------------

def load_case(case_dir):
    with open(os.path.join(case_dir, "view-1.json"), encoding="utf-8") as f:
        view = json.load(f)
    with open(os.path.join(case_dir, "style.cs.json"), encoding="utf-8") as f:
        style = json.load(f)
    layers = []
    for L in view["layers"]:
        p = os.path.join(case_dir, L["id"] + ".geojson")
        with open(p, encoding="utf-8") as f:
            fc = json.load(f)
        layers.append((L["id"], L.get("type", "vector"), fc["features"]))
    return view, style, layers


def layer_dimension(features):
    dims = {geom_dim(f["geometry"]) for f in features if f.get("geometry")}
    return dims.pop() if len(dims) == 1 else None  # null (mixed)


def render(case_dir, out_path):
    view, style, layers = load_case(case_dir)
    env = Env(view)
    bg = to_color(view.get("background", "white"), Context({}, {}))
    canvas = Canvas(env.W, env.H, bg)
    variables = style.get("$variables", {})
    warnings = set()

    # N-PASS-SET: the passes are 0 and every integer a selector compares a pass identifier with
    viz_passes = sorted({0} | collect_pass_values(style, {"viz.pass", "visualization.pass"}))
    feat_passes = sorted({0} | collect_pass_values(style, {"feature.pass"}))

    prepared = []
    for li, (lid, ltype, feats) in enumerate(layers):
        ldim = layer_dimension(feats)
        for fi, ft in enumerate(feats):
            g = ft.get("geometry")
            if not g:
                continue
            prepared.append((li, lid, ltype, ldim, fi, ft, geom_parts(g, env), geom_dim(g)))

    label_candidates = []

    for vp in viz_passes:
        items = []
        for (li, lid, ltype, ldim, fi, ft, parts, gdim) in prepared:
            for fp in feat_passes:
                sysids = dict(CAPABILITIES)
                sysids.update({
                    "viz.pass": vp, "visualization.pass": vp,
                    "viz.sd": view.get("scaleDenominator"), "visualization.scaleDenominator": view.get("scaleDenominator"),
                    "dataLayer.id": lid, "dataLayer.identifier": lid, "dataLayer.type": ltype,
                    "dataLayer.featuresGeometryDimensions": ldim, "dataLayer.featuresGeometryDimension": ldim,
                    "feature.pass": fp, "feature.geometryDimensions": gdim, "feature.geometryDimension": gdim,
                    "feature.id": ft.get("id"), "feature.identifier": ft.get("id"),
                })
                ctx = Context(ft.get("properties") or {}, sysids, variables)
                sym = resolve_rules(style.get("stylingRules", []), ctx, {})
                vis = sym_get(sym, "visibility", ctx, True)
                if vis is not True:
                    continue  # /req/core/visibility (null -> false)
                z = to_num(sym.get("zOrder", MISSING), ctx, 1.0)
                items.append((z, li, fi, fp, sym, ctx, parts, gdim))
                labels = get_graphics(sym, "label", ctx, None)
                if labels:
                    label_candidates.append((vp, li, fi, fp, labels, ctx, parts))
        items.sort(key=lambda it: it[0])  # stable: layer order, feature order, feature pass
        zs = []
        for it in items:
            if not zs or zs[-1][0] != it[0]:
                zs.append((it[0], []))
            zs[-1][1].append(it)
        for z, group in zs:
            draw_group(canvas, group, env, warnings)

    draw_labels(canvas, label_candidates, env, warnings)
    img = canvas.to_image()
    assert img.size == (env.W, env.H)
    img.save(out_path)
    return warnings


def outline_paths(parts):
    points, lines, polys = parts
    paths = list(lines)
    for rings in polys:
        for r in rings:
            if len(r) and not np.array_equal(r[0], r[-1]):
                r = np.vstack([r, r[:1]])
            paths.append(r)
    return paths


def stroke_paths(paths, st):
    if st["dash"]:
        out = []
        for p in paths:
            out.extend(dash_polyline(p, st["dash"], st["dashOffset"]))
        return out
    return paths


def draw_group(canvas, group, env, warnings):
    """One zOrder within one visualization pass: casings, then fills/strokes/markers, then center lines."""
    sym_opacity = {}
    strokes = {}
    for it in group:
        z, li, fi, fp, sym, ctx, parts, gdim = it
        op = to_num(sym.get("opacity", MISSING), ctx, 1.0)
        sym_opacity[id(it)] = op
        strokes[id(it)] = get_stroke(sym, ctx, env) if gdim in (1, 2) else None  # N-POINT-STROKE
    # 1. casings beneath all main strokes of the same zOrder (/req/casing/casing)
    for it in group:
        st = strokes[id(it)]
        if st and st["casing"] and st["casing"]["width"] > 0:
            paths = outline_paths(it[6])
            w = max(st["width"], 0.0) + 2 * st["casing"]["width"]
            cov, win = stroke_coverage(paths, w, canvas.w, canvas.h)
            canvas.paint(cov, st["casing"]["color"], st["casing"]["opacity"] * sym_opacity[id(it)], win)
    # 2. fills, main strokes and markers, one feature (and feature pass) after the other
    for it in group:
        z, li, fi, fp, sym, ctx, parts, gdim = it
        op = sym_opacity[id(it)]
        target = canvas if op >= 1.0 else Canvas(canvas.w, canvas.h)  # /rec/core/opacity-together, per feature
        points, lines, polys = parts
        if gdim == 2:
            f = get_fill(sym, ctx)
            if f:
                for rings in polys:
                    cov, win = fill_coverage(rings, canvas.w, canvas.h)
                    target.paint(cov, f["color"], f["opacity"], win)
        st = strokes[id(it)]
        if st and st["width"] > 0:  # /req/vector/stroke: nothing for width <= 0
            paths = stroke_paths(outline_paths(parts), st)
            cov, win = stroke_coverage(paths, st["width"], canvas.w, canvas.h)
            target.paint(cov, st["color"], st["opacity"], win)
        els = get_graphics(sym, "marker", ctx, {"elements": [default_dot()]})
        if els:
            anchors = []
            if gdim == 0:
                anchors = points
            elif gdim == 1:
                for l in lines:
                    anchors.extend(list(l))
            elif gdim == 2:
                anchors = [polygon_centroid(r) for r in polys]
            for (x, y) in anchors:
                for el in els:
                    draw_graphic(target, x, y, el, ctx, env, 1.0, warnings)
        if target is not canvas:
            canvas.composite(target, op)
    # 3. center lines on top of all main strokes of the same zOrder (/req/casing/center)
    for it in group:
        st = strokes[id(it)]
        if st and st["center"] and st["center"]["width"] > 0:
            paths = outline_paths(it[6])
            cov, win = stroke_coverage(paths, st["center"]["width"], canvas.w, canvas.h)
            canvas.paint(cov, st["center"]["color"], st["center"]["opacity"] * sym_opacity[id(it)], win)


def label_anchor(parts):
    points, lines, polys = parts
    if points:
        return points[0]
    if lines:
        longest = max(lines, key=lambda l: np.hypot(*(l[1:] - l[:-1]).T).sum() if len(l) > 1 else 0)
        return line_midpoint(longest)  # N-LINE-LABEL
    if polys:
        return polygon_centroid(polys[0])
    return None


def draw_labels(canvas, candidates, env, warnings):
    """After all passes, on top of everything (/req/labels/label); skip overlapping ones (/rec/labels/overlap)."""
    placed = []
    for (vp, li, fi, fp, els, ctx, parts) in candidates:
        a = label_anchor(parts)
        if a is None:
            continue
        boxes = []
        for el in els:
            if not isinstance(el, dict):
                continue
            ox, oy = graphic_offset(el, ctx, env)
            x, y = a[0] + ox, a[1] + oy
            if el.get("type") == "Text":
                font, txt, color, op, dx, dy, width, asc, desc = text_layout(el, ctx, env)
                if not txt:
                    continue
                top = y + dy - asc
                boxes.append((x + dx, top, x + dx + width, top + asc + desc))
            elif el.get("type", "Dot") == "Dot":
                boxes.append((x - 5, y - 5, x + 5, y + 5))
        if not boxes:
            continue
        overlap = any(b[0] < p[2] and p[0] < b[2] and b[1] < p[3] and p[1] < b[3] for b in boxes for p in placed)
        if overlap:
            continue
        placed.extend(boxes)
        for el in els:
            draw_graphic(canvas, a[0], a[1], el, ctx, env, 1.0, warnings)  # Symbolizer opacity not applied


def main(argv):
    if len(argv) >= 2 and argv[1] == "--all":
        cases_dir, out_dir = argv[2], argv[3]
        os.makedirs(out_dir, exist_ok=True)
        for c in sorted(os.listdir(cases_dir)):
            cd = os.path.join(cases_dir, c)
            if not os.path.isdir(cd):
                continue
            w = render(cd, os.path.join(out_dir, c + "-1.png"))
            print(c, "ok", "; ".join(sorted(w)))
    else:
        cd = argv[1]
        out = argv[2] if len(argv) > 2 else os.path.basename(os.path.normpath(cd)) + "-1.png"
        print(render(cd, out))


if __name__ == "__main__":
    main(sys.argv)
