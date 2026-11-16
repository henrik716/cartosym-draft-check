"""CartoSym-JSON renderer written from the requirement text in spec/ only.

Implementation choices are listed in notes.md. Every choice is marked in code
with a comment "CHOICE <id>" that refers to the notes.
"""
import glob
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASES = os.path.join(ROOT, "cases")
OUT = os.path.join(ROOT, "out")

SS = 4                       # supersampling factor for all drawing
MM_PER_PX = 0.28             # spec: standard pixel 0.28 mm (view pixelSize_mm)
FONT_DIR = "C:/Windows/Fonts"
FONT_FILES = {
    (False, False): "arial.ttf",
    (True, False): "arialbd.ttf",
    (False, True): "ariali.ttf",
    (True, True): "arialbi.ttf",
}
UNIT_KEYS = ["px", "mm", "cm", "in", "pt", "em", "pc", "m", "ft"]

# CHOICE C-colours: the spec lists web colour names (schema webColorName) but gives no RGB values.
# CSS / SVG values are used.
NAMED = {
    "black": "000000", "white": "ffffff", "gray": "808080", "grey": "808080",
    "dimgray": "696969", "dimgrey": "696969", "darkgray": "a9a9a9", "darkgrey": "a9a9a9",
    "silver": "c0c0c0", "lightgray": "d3d3d3", "lightgrey": "d3d3d3", "gainsboro": "dcdcdc",
    "whitesmoke": "f5f5f5", "navy": "000080", "darkblue": "00008b", "mediumblue": "0000cd",
    "blue": "0000ff", "steelblue": "4682b4", "lightsteelblue": "b0c4de", "cornflowerblue": "6495ed",
    "royalblue": "4169e1", "midnightblue": "191970", "dodgerblue": "1e90ff", "deepskyblue": "00bfff",
    "skyblue": "87ceeb", "lightblue": "add8e6", "powderblue": "b0e0e6", "cadetblue": "5f9ea0",
    "aliceblue": "f0f8ff", "crimson": "dc143c", "darkred": "8b0000", "red": "ff0000",
    "firebrick": "b22222", "indianred": "cd5c5c", "maroon": "800000", "brown": "a52a2a",
    "saddlebrown": "8b4513", "sienna": "a0522d", "chocolate": "d2691e", "darkorange": "ff8c00",
    "orange": "ffa500", "tan": "d2b48c", "peru": "cd853f", "sandybrown": "f4a460",
    "burlywood": "deb887", "goldenrod": "daa520", "darkgoldenrod": "b8860b", "gold": "ffd700",
    "yellow": "ffff00", "khaki": "f0e68c", "darkkhaki": "bdb76b", "olive": "808000",
    "olivedrab": "6b8e23", "darkolivegreen": "556b2f", "green": "008000", "darkgreen": "006400",
    "forestgreen": "228b22", "limegreen": "32cd32", "lightgreen": "90ee90", "palegreen": "98fb98",
    "seagreen": "2e8b57", "mediumseagreen": "3cb371", "darkseagreen": "8fbc8f", "teal": "008080",
    "turquoise": "40e0d0", "aqua": "00ffff", "cyan": "00ffff", "purple": "800080",
    "violet": "ee82ee", "magenta": "ff00ff", "fuschia": "ff00ff", "fuchsia": "ff00ff",
    "pink": "ffc0cb", "plum": "dda0dd", "orchid": "da70d6", "salmon": "fa8072", "coral": "ff7f50",
    "tomato": "ff6347", "hotpink": "ff69b4", "deeppink": "ff1493", "lavender": "e6e6fa",
    "beige": "f5f5dc", "ivory": "fffff0", "wheat": "f5deb3", "linen": "faf0e6", "snow": "fffafa",
    "seashell": "fff5ee", "honeydew": "f0fff0", "azure": "f0ffff", "mintcream": "f5fffa",
    "ghostwhite": "f8f8ff", "floralwhite": "fffaf0", "oldlace": "fdf5e6", "mistyrose": "ffe4e1",
    "lightcoral": "f08080", "rosybrown": "bc8f8f", "darkslategray": "2f4f4f", "slategray": "708090",
    "lightslategray": "778899", "indigo": "4b0082", "darkviolet": "9400d3", "mediumpurple": "9370db",
    "darkorchid": "9932cc", "springgreen": "00ff7f", "lawngreen": "7cfc00", "chartreuse": "7fff00",
    "yellowgreen": "9acd32", "aquamarine": "7fffd4", "lightyellow": "ffffe0",
    "lemonchiffon": "fffacd", "moccasin": "ffe4b5", "navajowhite": "ffdead", "peachpuff": "ffdab9",
    "bisque": "ffe4c4", "antiquewhite": "faebd7", "paleturquoise": "afeeee", "lightcyan": "e0ffff",
    "darkcyan": "008b8b", "darkturquoise": "00ced1", "mediumturquoise": "48d1cc",
    "lightseagreen": "20b2aa", "darkmagenta": "8b008b", "mediumvioletred": "c71585",
    "palevioletred": "db7093", "lightpink": "ffb6c1", "mediumorchid": "ba55d3", "thistle": "d8bfd8",
    "blueviolet": "8a2be2", "slateblue": "6a5acd", "darkslateblue": "483d8b",
    "mediumslateblue": "7b68ee", "lightskyblue": "87cefa", "mediumaquamarine": "66cdaa",
    "mediumspringgreen": "00fa9a", "cornsilk": "fff8dc", "blanchedalmond": "ffebcd",
    "papayawhip": "ffefd5", "lightsalmon": "ffa07a", "darksalmon": "e9967a", "orangered": "ff4500",
    "lightgoldenrodyellow": "fafad2", "palegoldenrod": "eee8aa", "darkseagreen2": "c1ffc1",
    "mediumblue2": "0000cd", "lightslategrey": "778899", "slategrey": "708090",
    "darkslategrey": "2f4f4f", "dimgrey2": "696969", "seagreen2": "2e8b57", "sandybrown2": "f4a460",
}


def hex_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def named_rgb(name):
    key = name.lower()
    if key not in NAMED:
        raise KeyError("unknown colour name: " + name)
    return hex_rgb(NAMED[key])


# ---------------------------------------------------------------- context / expressions

class Ctx:
    def __init__(self, props, sysv, scale):
        self.props = props      # feature properties, or band arrays for coverage
        self.sysv = sysv        # system identifier values
        self.scale = scale


def _tri(v):
    return None if v is None else bool(v)


def ev(node, ctx):
    """Evaluate an expression node of CartoSym-JSON (CQL2-like)."""
    if node is None or isinstance(node, (bool, int, float, str)):
        return node
    if isinstance(node, list):
        return [ev(n, ctx) for n in node]
    if isinstance(node, dict):
        if "property" in node:
            return ctx.props.get(node["property"])
        if "sysId" in node:
            return ctx.sysv.get(node["sysId"])
        if "op" in node:
            return _op(node["op"], node.get("args", []), ctx)
        return node  # structure, handled by the caller
    raise TypeError("unexpected node %r" % (node,))


def ev_num(node, ctx, default=None):
    if node is None:
        return default
    v = ev(node, ctx)
    if v is None:
        return None
    return float(v)


def _op(name, args, ctx):
    if name == "and":
        vals = [_tri(ev(a, ctx)) for a in args]
        if any(v is False for v in vals):
            return False
        return None if any(v is None for v in vals) else True
    if name == "or":
        vals = [_tri(ev(a, ctx)) for a in args]
        if any(v is True for v in vals):
            return True
        return None if any(v is None for v in vals) else False
    if name == "not":
        v = _tri(ev(args[0], ctx))
        return None if v is None else (not v)
    if name in ("=", "<>", "<", ">", "<=", ">="):
        a = ev(args[0], ctx)
        b = ev(args[1], ctx)
        if a is None or b is None:
            return None
        if name == "=":
            return a == b
        if name == "<>":
            return a != b
        try:
            return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[name]
        except TypeError:
            return None
    if name in ("+", "-", "*", "/", "^"):
        a = ev(args[0], ctx)
        b = ev(args[1], ctx)
        if a is None or b is None:
            return None
        if name == "+":
            return a + b
        if name == "-":
            return a - b
        if name == "*":
            return a * b
        if name == "/":
            return None if b == 0 else a / b  # spec: real-valued quotient
        return a ** b
    if name == "in":
        a = ev(args[0], ctx)
        lst = ev(args[1], ctx)
        if a is None or lst is None:
            return None
        return a in lst
    if name == "between":
        v, lo, hi = (ev(a, ctx) for a in args)
        if v is None or lo is None or hi is None:
            return None
        return lo <= v <= hi
    if name == "?:":
        c = _tri(ev(args[0], ctx))
        return ev(args[1], ctx) if c else ev(args[2], ctx)  # CHOICE E-null: not true -> else
    if name == "isNull":
        return ev(args[0], ctx) is None
    raise NotImplementedError("operator " + name)


# ---------------------------------------------------------------- units

def unit_factor(u, scale):
    """Factor from a unit to standard pixels (0.28 mm)."""
    if u == "px":
        return 1.0
    mm = {
        "mm": 1.0,
        "cm": 10.0,
        "in": 25.4,
        "pt": 25.4 / 72.0,          # CHOICE U-pt: typographic point (1/72 inch)
        "em": 12.0 * 25.4 / 72.0,   # CHOICE U-em: undefined by spec, taken as 12 pt
        "m": 1000.0 / scale,        # ground metres to paper mm at the view scale
        "ft": 1000.0 * 0.3048 / scale,
    }[u]
    return mm / MM_PER_PX


def length_px(raw, ctx, scale, pc_base=None):
    """Convert a uom-qualified value to standard pixels. None stays None."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        for u in UNIT_KEYS:
            if u in raw:
                v = ev_num(raw[u], ctx)
                if v is None:
                    return None
                if u == "pc":
                    return None if pc_base is None else v / 100.0 * pc_base
                return v * unit_factor(u, scale)
        return ev_num(raw, ctx)  # expression, pixels
    return ev_num(raw, ctx)      # bare number: pixels (spec default unit)


def parse_point(raw, ctx, scale):
    if raw is None:
        return (0.0, 0.0)
    if isinstance(raw, dict) and ("x" in raw or "y" in raw) and "op" not in raw:
        x = length_px(raw.get("x", 0), ctx, scale) or 0.0
        y = length_px(raw.get("y", 0), ctx, scale) or 0.0
        return (x, y)
    if isinstance(raw, list):
        x = length_px(raw[0], ctx, scale) or 0.0
        y = length_px(raw[1], ctx, scale) or 0.0
        return (x, y)
    return (0.0, 0.0)


def parse_color(raw, ctx):
    if raw is None:
        return None
    if isinstance(raw, dict) and "op" in raw or isinstance(raw, dict) and "property" in raw:
        raw = ev(raw, ctx)
        if raw is None:
            return (0.0, 0.0, 0.0)  # table: NULL colour -> black
    if isinstance(raw, str):
        if raw.startswith("#"):
            return hex_rgb(raw)
        return named_rgb(raw)
    if isinstance(raw, list):
        return tuple(float(ev(c, ctx)) / 255.0 for c in raw)
    if isinstance(raw, dict):
        return tuple(float(ev(raw.get(k, 0), ctx)) / 255.0 for k in ("r", "g", "b"))
    raise TypeError("colour %r" % (raw,))


def parse_angle(raw, ctx):
    if raw is None:
        return None
    if isinstance(raw, dict):
        if "deg" in raw:
            return ev_num(raw["deg"], ctx)
        if "rad" in raw:
            return math.degrees(ev_num(raw["rad"], ctx))
    return ev_num(raw, ctx)


# ---------------------------------------------------------------- symbolizer state (raw, cascaded)

def merge_obj(prev, new):
    """Apply an object with alter=true: members not given keep their earlier value."""
    out = dict(prev) if isinstance(prev, dict) else {}
    for k, v in new.items():
        if k in ("alter", "$comment"):
            continue
        if isinstance(v, dict) and v.get("alter") is True:
            out[k] = merge_obj(out.get(k), v)
        elif isinstance(v, dict) and "index" in v and "value" in v and isinstance(out.get(k), list):
            arr = list(out[k])
            arr[int(v["index"])] = v["value"]
            out[k] = arr
        else:
            out[k] = v  # plain object replaces the whole property (defaults fill members)
    return out


def apply_sym(state, sym):
    out = dict(state)
    for k, v in sym.items():
        if k == "$comment":
            continue
        if isinstance(v, dict) and v.get("alter") is True:
            out[k] = merge_obj(state.get(k), v)
        else:
            out[k] = v
    return out


def walk(rules, state, ctx, flag):
    """Cascade the rules in document order (pre-order). flag[0] becomes True if any rule is selected."""
    for r in rules:
        sel = r.get("selector")
        if sel is not None:
            if not _tri(ev(sel, ctx)):
                continue
        flag[0] = True
        if "symbolizer" in r:
            state = apply_sym(state, r["symbolizer"])
        if r.get("nestedRules"):
            state = walk(r["nestedRules"], state, ctx, flag)
    return state


# ---------------------------------------------------------------- parsed symbolizer

DEFAULT_DOT = {"type": "Dot", "size": {"px": 10}, "color": "white"}  # spec default Marker


def parse_stroke_style(raw, ctx, scale, default_width_px=1.0):
    """StrokeStyling (color, opacity, width)."""
    d = raw if isinstance(raw, dict) else {}
    col = parse_color(d.get("color", "black"), ctx)
    op = ev_num(d.get("opacity", 1), ctx, 1.0)
    w = length_px(d.get("width", {"px": default_width_px}), ctx, scale)
    return {"color": col, "opacity": 1.0 if op is None else op, "width": 0.0 if w is None else w}


def parse_stroke(raw, ctx, scale):
    if raw is None:
        return None
    d = raw if isinstance(raw, dict) else {}
    base = parse_stroke_style(d, ctx, scale)
    base["casing"] = None
    base["center"] = None
    base["dashes"] = None
    base["dashoffset"] = 0.0
    if "casing" in d and d["casing"] is not None:
        base["casing"] = parse_stroke_style(d["casing"], ctx, scale)   # CHOICE B-casing-default
    centre = d.get("center", d.get("centerLine"))  # CHOICE B-centre-name: schema uses centerLine
    if centre is not None:
        base["center"] = parse_stroke_style(centre, ctx, scale)
    if "dashPattern" in d and d["dashPattern"] is not None:
        pat = d["dashPattern"]
        vals = []
        pc_base = base["width"]
        for item in pat:
            v = length_px(item, ctx, scale, pc_base=pc_base)
            vals.append(0.0 if v is None else v)
        base["dashes"] = vals
    if "dashOffset" in d and d["dashOffset"] is not None:
        v = length_px(d["dashOffset"], ctx, scale, pc_base=base["width"])
        base["dashoffset"] = 0.0 if v is None else v
    return base


def parse_fill(raw, ctx, scale):
    if raw is None:
        return None
    d = raw if isinstance(raw, dict) else {}
    col = parse_color(d.get("color", "white"), ctx)
    op = ev_num(d.get("opacity", 1), ctx, 1.0)
    fill = {"color": col, "opacity": 1.0 if op is None else op,
            "hatch": None, "dotpattern": None, "stipple": None}
    h = d.get("hatch")
    if isinstance(h, dict):
        fill["hatch"] = {
            "width": length_px(h.get("width", {"px": 1}), ctx, scale),
            "angle": parse_angle(h.get("angle", 45.0), ctx),    # spec caption: default 45 degrees
            "distance": length_px(h.get("distance", {"px": 10}), ctx, scale),  # caption: default 10 px
        }
    dp = d.get("dotpattern")
    if isinstance(dp, dict):
        dist = dp.get("distance", {})
        fill["dotpattern"] = {
            "h": length_px(dist.get("horizontal", {"px": 10}), ctx, scale),
            "v": length_px(dist.get("vertical", {"px": 10}), ctx, scale),
        }
    st = d.get("stipple")
    if isinstance(st, dict):
        fill["stipple"] = {"ratio": ev_num(st.get("ratio", 0.5), ctx, 0.5)}
    return fill


def parse_font(raw, ctx, scale):
    d = raw if isinstance(raw, dict) else {}
    face = ev(d.get("face", "Arial"), ctx) or "Arial"
    size_pt = ev_num(d.get("size", 10), ctx, 10.0)     # CHOICE F-size-default: 10 pt
    bold = bool(ev(d.get("bold", False), ctx))
    italic = bool(ev(d.get("italic", False), ctx))
    col = parse_color(d.get("color", "black"), ctx)    # CHOICE F-colour-default: black
    op = ev_num(d.get("opacity", 1), ctx, 1.0)
    outline = None
    o = d.get("outline")
    if isinstance(o, dict):
        osz = ev_num(o.get("size", 0), ctx, 0.0)
        outline = {
            "size_pt": osz,   # CHOICE O-unit: outline size in points, like the font size
            "opacity": ev_num(o.get("opacity", 1), ctx, 1.0),  # CHOICE O-opacity-default
            "color": parse_color(o.get("color", "black"), ctx),  # CHOICE O-colour-default
        }
    return {"face": str(face), "size_pt": size_pt, "bold": bold, "italic": italic,
            "color": col, "opacity": 1.0 if op is None else op, "outline": outline}


def parse_align(raw):
    h, v = "center", "middle"          # CHOICE T-align-default
    if isinstance(raw, list) and len(raw) == 2:
        h, v = raw[0], raw[1]
    elif isinstance(raw, dict):
        h = raw.get("hAlignment", raw.get("horzAlignment", h))
        v = raw.get("vAlignment", raw.get("vertAlignment", v))
    return h, v


def parse_element(raw, ctx, scale, case_dir):
    t = raw.get("type")
    pos = parse_point(raw.get("position"), ctx, scale)
    if t == "Dot":
        d = {"type": "Dot", "pos": pos}
        size = length_px(raw.get("size", {"px": 10}), ctx, scale)
        col = parse_color(raw.get("color", "white"), ctx)
        st = raw.get("stroke")
        if isinstance(st, dict):
            if "width" in st:
                size = length_px(st["width"], ctx, scale)
            if "color" in st:
                col = parse_color(st["color"], ctx)
        d["size"] = 0.0 if size is None else size
        d["color"] = col
        d["opacity"] = ev_num(raw.get("opacity", 1), ctx, 1.0)
        return d
    if t == "Text":
        txt = ev(raw.get("text"), ctx)
        if txt is None:
            txt = ""
        if isinstance(txt, float) and txt.is_integer():
            txt = int(txt)
        font = parse_font(raw.get("font"), ctx, scale)
        return {"type": "Text", "pos": pos, "text": str(txt), "font": font,
                "align": parse_align(raw.get("alignment")),
                "opacity": ev_num(raw.get("opacity", 1), ctx, 1.0)}
    if t == "Image":
        res = raw.get("image", {}) or {}
        path = ev(res.get("path"), ctx)
        if path is None:
            raise ValueError("image without path (only path is resolvable)")
        full = os.path.normpath(os.path.join(case_dir, path))
        hs = raw.get("hotSpot")
        hot = [("frac", 0.5), ("frac", 0.5)]
        if isinstance(hs, list) and len(hs) == 2:
            hot = []
            for c in hs:
                if isinstance(c, dict) and "pc" in c:
                    hot.append(("frac", ev_num(c["pc"], ctx) / 100.0))  # CHOICE G-hotspot
                else:
                    hot.append(("px", length_px(c, ctx, scale)))
        return {"type": "Image", "pos": pos, "path": full, "hot": hot,
                "tint": parse_color(raw.get("tint", "white"), ctx),
                "black": parse_color(raw.get("blackTint", "black"), ctx),
                "opacity": ev_num(raw.get("opacity", 1), ctx, 1.0)}
    raise NotImplementedError("element type %r" % t)


def parse_map(raw, ctx, kind):
    """colorMap: pairs (value, color[, name]); opacityMap: pairs (value, opacity[, name])."""
    if raw is None:
        return None
    vals, outs = [], []
    for e in raw:
        if isinstance(e, dict):
            v = ev_num(e.get("value"), ctx)
            o = e.get("color") if kind == "color" else e.get("opacity")
        else:
            v = ev_num(e[0], ctx)
            o = e[1]
        vals.append(v)
        outs.append(parse_color(o, ctx) if kind == "color" else ev_num(o, ctx))
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    vals = np.array([vals[i] for i in order], dtype=np.float64)
    if kind == "color":
        outs = np.array([outs[i] for i in order], dtype=np.float64)
    else:
        outs = np.array([outs[i] for i in order], dtype=np.float64)
    return vals, outs


def parse_style(state, ctx, scale, case_dir):
    S = {}
    if "visibility" not in state:
        S["visible"] = True
    else:
        v = ev(state["visibility"], ctx)
        S["visible"] = False if v is None else bool(v)
    op = ev_num(state.get("opacity", 1), ctx, 1.0)
    S["opacity"] = 0.0 if op is None else op
    z = ev_num(state.get("zOrder", 1), ctx, 1.0)
    S["z"] = 0.0 if z is None else z
    S["fill"] = parse_fill({} if "fill" not in state else state["fill"], ctx, scale)
    S["stroke"] = parse_stroke({} if "stroke" not in state else state["stroke"], ctx, scale)
    if "marker" not in state:
        S["marker"] = [parse_element(DEFAULT_DOT, ctx, scale, case_dir)]   # spec default Marker
    elif state["marker"] is None:
        S["marker"] = None
    else:
        m = state["marker"]
        els = m.get("elements") if isinstance(m, dict) else None
        if els is None:
            els = [DEFAULT_DOT]          # spec note: empty {} still gives the default Dot
        S["marker"] = [parse_element(e, ctx, scale, case_dir) for e in els]
    S["label"] = None
    if state.get("label") is not None:
        lab = state["label"]
        els = lab.get("elements", []) or []
        pl = lab.get("placement") or {}
        S["label"] = {
            "elements": [parse_element(e, ctx, scale, case_dir) for e in els],
            "priority": ev_num(pl.get("priority", 0), ctx, 0.0) or 0.0,  # null priority -> 0
            "minSpacing": length_px(pl.get("minSpacing"), ctx, scale) if "minSpacing" in pl else None,
        }
    # coverage
    S["colorMap"] = parse_map(state.get("colorMap"), ctx, "color") if state.get("colorMap") is not None else None
    S["opacityMap"] = parse_map(state.get("opacityMap"), ctx, "opacity") if state.get("opacityMap") is not None else None
    S["single"] = ev(state.get("singleChannel"), ctx) if state.get("singleChannel") is not None else None
    S["alpha"] = ev_num(state.get("alphaChannel", 1), ctx, 1.0)
    hs = state.get("hillShading")
    S["hill"] = None
    if isinstance(hs, dict):
        sun = hs.get("sun") or {}
        az = parse_angle(sun.get("azimuth", 315.0), ctx)      # CHOICE H-sun-default
        el = parse_angle(sun.get("elevation", 45.0), ctx)
        f = ev_num(hs.get("factor", 1.0), ctx, 1.0)           # CHOICE H-factor-default
        S["hill"] = {
            "factor": f, "az": az, "el": el,
            "colorMap": parse_map(hs.get("colorMap"), ctx, "color") if hs.get("colorMap") is not None else None,
            "opacityMap": parse_map(hs.get("opacityMap"), ctx, "opacity") if hs.get("opacityMap") is not None else None,
        }
    return S


# ---------------------------------------------------------------- raster helpers (SS device pixels)

def geom_alpha(geom, CW, CH):
    """Alpha mask of a (Multi)Polygon in SS device coordinates, cropped to canvas."""
    if geom is None or geom.is_empty:
        return None
    minx, miny, maxx, maxy = geom.bounds
    x0 = max(0, int(math.floor(minx)) - 1)
    y0 = max(0, int(math.floor(miny)) - 1)
    x1 = min(CW, int(math.ceil(maxx)) + 2)
    y1 = min(CH, int(math.ceil(maxy)) + 2)
    if x1 <= x0 or y1 <= y0:
        return None
    img = Image.new("L", (x1 - x0, y1 - y0), 0)
    dr = ImageDraw.Draw(img)
    polys = geom.geoms if hasattr(geom, "geoms") else [geom]
    for p in polys:
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        dr.polygon([(x - x0, y - y0) for x, y in p.exterior.coords], fill=255)
        for hole in p.interiors:
            dr.polygon([(x - x0, y - y0) for x, y in hole.coords], fill=0)
    return x0, y0, np.asarray(img, dtype=np.float32) / 255.0


def prim(alpha, x0, y0, colour, opacity):
    a = (alpha * opacity).astype(np.float32)
    h, w = a.shape
    arr = np.empty((h, w, 4), np.float32)
    arr[..., 0] = colour[0] * a
    arr[..., 1] = colour[1] * a
    arr[..., 2] = colour[2] * a
    arr[..., 3] = a
    return (x0, y0, arr)


def disc_alpha(cx, cy, r, CW, CH):
    x0 = max(0, int(math.floor(cx - r)) - 1)
    y0 = max(0, int(math.floor(cy - r)) - 1)
    x1 = min(CW, int(math.ceil(cx + r)) + 2)
    y1 = min(CH, int(math.ceil(cy + r)) + 2)
    if x1 <= x0 or y1 <= y0 or r <= 0:
        return None
    X = np.arange(x0, x1, dtype=np.float32)[None, :] + 0.5
    Y = np.arange(y0, y1, dtype=np.float32)[:, None] + 0.5
    d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    return x0, y0, np.clip(r - d + 0.5, 0, 1).astype(np.float32)


def hatch_alpha(x0, y0, alpha, width, angle, dist):
    h, w = alpha.shape
    X = (x0 + np.arange(w, dtype=np.float32) + 0.5)[None, :]
    Y = (y0 + np.arange(h, dtype=np.float32) + 0.5)[:, None]
    th = math.radians(angle)
    # CHOICE P-hatch: angle clockwise on screen (y down) from the x axis; 0 = horizontal
    nx, ny = -math.sin(th), math.cos(th)
    t = X * nx + Y * ny
    r = np.mod(t, dist)
    m = np.minimum(r, dist - r)
    a = np.clip(width / 2.0 - m + 0.5, 0, 1)
    return a * alpha


def dot_grid_alpha(x0, y0, alpha, sx, sy, radius, CW, CH):
    """Discs at grid nodes (multiples of sx, sy in device pixels), clipped to the polygon."""
    h, w = alpha.shape
    out = np.zeros((h, w), np.float32)
    if sx <= 0 or sy <= 0 or radius <= 0:
        return out
    i0 = int(math.floor((x0 - radius) / sx))
    i1 = int(math.ceil((x0 + w + radius) / sx))
    j0 = int(math.floor((y0 - radius) / sy))
    j1 = int(math.ceil((y0 + h + radius) / sy))
    for j in range(j0, j1 + 1):
        gy = j * sy
        for i in range(i0, i1 + 1):
            gx = i * sx
            wx0 = int(math.floor(gx - radius)) - 1
            wy0 = int(math.floor(gy - radius)) - 1
            wx1 = int(math.ceil(gx + radius)) + 2
            wy1 = int(math.ceil(gy + radius)) + 2
            ax0, ay0 = max(wx0, x0), max(wy0, y0)
            ax1, ay1 = min(wx1, x0 + w), min(wy1, y0 + h)
            if ax1 <= ax0 or ay1 <= ay0:
                continue
            X = np.arange(ax0, ax1, dtype=np.float32)[None, :] + 0.5
            Y = np.arange(ay0, ay1, dtype=np.float32)[:, None] + 0.5
            d = np.sqrt((X - gx) ** 2 + (Y - gy) ** 2)
            a = np.clip(radius - d + 0.5, 0, 1)
            sub = out[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
            np.maximum(sub, a, out=sub)
    return out * alpha


def dilate(mask, r):
    """Dilate a mask with a disc of radius r pixels (integer)."""
    if r <= 0:
        return mask
    H, W = mask.shape
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if (dx == 0 and dy == 0) or dx * dx + dy * dy > r * r:
                continue
            ys_d = slice(max(0, dy), H + min(0, dy))
            xs_d = slice(max(0, dx), W + min(0, dx))
            ys_s = slice(max(0, -dy), H + min(0, -dy))
            xs_s = slice(max(0, -dx), W + min(0, -dx))
            np.maximum(out[ys_d, xs_d], mask[ys_s, xs_s], out=out[ys_d, xs_d])
    return out


def over(dst, dorg, src, sorg):
    dx0, dy0 = dorg
    sx0, sy0 = sorg
    h, w = src.shape[:2]
    ys, ye = max(sy0, dy0), min(sy0 + h, dy0 + dst.shape[0])
    xs, xe = max(sx0, dx0), min(sx0 + w, dx0 + dst.shape[1])
    if ye <= ys or xe <= xs:
        return
    s = src[ys - sy0:ye - sy0, xs - sx0:xe - sx0]
    d = dst[ys - dy0:ye - dy0, xs - dx0:xe - dx0]
    d[:] = s + d * (1.0 - s[..., 3:4])


def composite_group(canvas, prims, opacity):
    """Render a group of premultiplied RGBA pieces together, then apply the group opacity."""
    prims = [p for p in prims if p is not None]
    if not prims:
        return
    x0 = min(p[0] for p in prims)
    y0 = min(p[1] for p in prims)
    x1 = max(p[0] + p[2].shape[1] for p in prims)
    y1 = max(p[1] + p[2].shape[0] for p in prims)
    grp = np.zeros((y1 - y0, x1 - x0, 4), np.float32)
    for px, py, arr in prims:
        over(grp, (x0, y0), arr, (px, py))
    if opacity < 1.0:
        grp *= opacity
    over(canvas, (0, 0), grp, (x0, y0))


# ---------------------------------------------------------------- text

_font_cache = {}


def get_font(face, bold, italic, size_ss):
    # CHOICE F-face: only Arial is available with styles; other faces fall back to Arial
    key = (round(size_ss, 3), bold, italic)
    if key not in _font_cache:
        path = os.path.join(FONT_DIR, FONT_FILES[(bold, italic)])
        _font_cache[key] = ImageFont.truetype(path, size_ss)
    return _font_cache[key]


def text_geom(el, ax, ay):
    """Layout of a Text element at anchor (SS device coords). Returns font, text, x0, y0, W, H, radius."""
    f = el["font"]
    size_ss = f["size_pt"] * (25.4 / 72.0) / MM_PER_PX * SS
    font = get_font(f["face"], f["bold"], f["italic"], size_ss)
    asc, desc = font.getmetrics()
    W = font.getlength(el["text"])
    H = asc + desc
    h, v = el["align"]
    x = ax + el["pos"][0] * SS
    y = ay - el["pos"][1] * SS         # CHOICE Y-up: positive y offsets point up on the image
    x0 = x - (W / 2.0 if h == "center" else (W if h == "right" else 0.0))
    y0 = y - (H / 2.0 if v == "middle" else (H if v == "bottom" else 0.0))
    r = 0.0
    if f["outline"] and f["outline"]["size_pt"] > 0:
        r = f["outline"]["size_pt"] * (25.4 / 72.0) / MM_PER_PX * SS
    return font, x0, y0, W, H, r


def text_prims(el, ax, ay, CW, CH):
    if el["text"] == "":
        return []
    font, x0, y0, W, H, r = text_geom(el, ax, ay)
    f = el["font"]
    pad = int(math.ceil(r)) + 3
    gw = int(math.ceil(W)) + 2 * pad
    gh = int(math.ceil(H)) + 2 * pad
    img = Image.new("L", (gw, gh), 0)
    ImageDraw.Draw(img).text((pad, pad), el["text"], font=font, fill=255)
    glyph = np.asarray(img, dtype=np.float32) / 255.0
    ox = int(round(x0)) - pad
    oy = int(round(y0)) - pad
    out = []
    if r > 0:
        halo = dilate(glyph, int(round(r)))
        out.append(prim(halo, ox, oy, f["outline"]["color"], f["outline"]["opacity"] * el["opacity"]))
    out.append(prim(glyph, ox, oy, f["color"], f["opacity"] * el["opacity"]))
    return out


def text_box(el, ax, ay):
    font, x0, y0, W, H, r = text_geom(el, ax, ay)
    return (x0 - r, y0 - r, x0 + W + r, y0 + H + r)


_img_cache = {}


def image_prims(el, ax, ay):
    if el["path"] not in _img_cache:
        im = Image.open(el["path"]).convert("RGBA")
        _img_cache[el["path"]] = np.asarray(im, dtype=np.float32) / 255.0
    base = _img_cache[el["path"]]
    h, w = base.shape[:2]
    tint = np.array(el["tint"], np.float32)
    black = np.array(el["black"], np.float32)
    v = base[..., :3]
    rgb = tint[None, None, :] * v + black[None, None, :] * (1.0 - v)   # spec recolour formula
    a = base[..., 3]
    big = np.empty((h, w, 4), np.float32)
    big[..., :3] = rgb * a[..., None]
    big[..., 3] = a
    big = np.repeat(np.repeat(big, SS, axis=0), SS, axis=1)              # 1 image px = 1 px, nearest
    H2, W2 = big.shape[:2]
    hs = []
    for kind, val in el["hot"]:
        if kind == "frac":
            hs.append(val * (W2 if len(hs) == 0 else H2))
        else:
            hs.append(val * SS)
    # CHOICE G-hotspot: hotSpot measured from the image's top-left corner, y downwards
    tx = int(round(ax + el["pos"][0] * SS - hs[0]))
    ty = int(round(ay - el["pos"][1] * SS - hs[1]))
    return [(tx, ty, big)]


# ---------------------------------------------------------------- dash pattern

def dash_intervals(total, pattern, offset):
    """On-intervals along a line of length total, pattern in device pixels; CHOICE D-offset."""
    if total <= 0:
        return []
    pat = [p for p in pattern]
    if not pat or sum(pat) <= 0:
        return [(0.0, total)]
    if len(pat) % 2 == 1:
        pat = pat * 2   # odd arrays repeat with on/off swapped (SVG-like)
    L = sum(pat)
    ph = offset % L
    idx = 0
    while ph >= pat[idx] and pat[idx] > 0:
        ph -= pat[idx]
        idx = (idx + 1) % len(pat)
    rem = pat[idx] - ph
    s = 0.0
    out = []
    guard = 0
    while s < total and guard < 1000000:
        guard += 1
        seg_end = min(total, s + rem)
        if idx % 2 == 0 and seg_end > s:
            out.append((s, seg_end))
        s = seg_end
        idx = (idx + 1) % len(pat)
        rem = pat[idx]
    return out


def stroke_shape(rings, width_ss, dashes_ss, offset_ss):
    if width_ss <= 0:
        return None
    geoms = []
    for coords in rings:
        if len(coords) < 2:
            continue
        ls = LineString(coords)
        if ls.length <= 0:
            continue
        if dashes_ss is None:
            geoms.append(ls.buffer(width_ss / 2.0, cap_style="flat", join_style="mitre", mitre_limit=5.0))
        else:
            parts = []
            for a, b in dash_intervals(ls.length, dashes_ss, offset_ss):
                sub = substring(ls, a, b)
                if sub.geom_type == "LineString" and sub.length > 0:
                    parts.append(sub.buffer(width_ss / 2.0, cap_style="flat", join_style="mitre", mitre_limit=5.0))
            if parts:
                geoms.append(unary_union(parts))
    if not geoms:
        return None
    return unary_union(geoms)


# ---------------------------------------------------------------- coverage

def compute_shade(grid, cs, factor, az, el):
    """Hill shade per cell from neighbouring cell values (grid row 0 is the north row)."""
    nrows, ncols = grid.shape
    P = np.full((nrows + 2, ncols + 2), np.nan)
    P[1:-1, 1:-1] = grid
    zC = P[1:-1, 1:-1]
    zL, zR = P[1:-1, :-2], P[1:-1, 2:]
    zN, zS = P[:-2, 1:-1], P[2:, 1:-1]   # north row is index-1
    vC = ~np.isnan(zC)
    # CHOICE H-edge: central difference when both neighbours exist, else one-sided, else 0
    def slope(zm, zp, sign):
        cen = (zp - zm) / (2 * cs)
        fwd = (zp - zC) / cs
        bwd = (zC - zm) / cs
        vm, vp = ~np.isnan(zm), ~np.isnan(zp)
        s = np.where(vm & vp, cen, np.where(vp, fwd, np.where(vm, bwd, 0.0)))
        return np.where(vC, s * sign, np.nan)
    dzdE = slope(zL, zR, 1.0)                 # x grows to the east
    dzdN = slope(zS, zN, 1.0)                 # z(north) - z(south): north grows upwards
    nx = -factor * dzdE
    ny = -factor * dzdN
    nz = np.ones_like(nx)
    norm = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    nx, ny, nz = nx / norm, ny / norm, nz / norm
    azr, elr = math.radians(az), math.radians(el)
    sx = math.sin(azr) * math.cos(elr)        # east
    sy = math.cos(azr) * math.cos(elr)        # north
    sz = math.sin(elr)
    shade = np.clip(nx * sx + ny * sy + nz * sz, 0.0, 1.0)  # CHOICE H-clamp
    return shade


def interp_map(x, vals, outs):
    if outs.ndim == 1:
        return np.interp(x, vals, outs)
    return np.stack([np.interp(x, vals, outs[:, c]) for c in range(outs.shape[1])], axis=-1)


# ---------------------------------------------------------------- main renderer

def render_case(case_dir, view_path, out_path):
    style = json.load(open(os.path.join(case_dir, "style.cs.json"), encoding="utf-8"))
    view = json.load(open(view_path, encoding="utf-8"))
    W, H = int(view["width"]), int(view["height"])
    CW, CH = W * SS, H * SS
    minx, miny, maxx, maxy = view["bbox"]
    scale = float(view["scaleDenominator"])
    sysv = {
        "viz.sd": scale, "visualization.scaleDenominator": scale,
        "viz.date": view["visualization"]["date"],
        "viz.timeInterval.start.date": view["visualization"]["timeInterval"]["start"],
        "viz.timeInterval.end.date": view["visualization"]["timeInterval"]["end"],
    }

    def to_dev(x, y):
        return ((x - minx) / (maxx - minx) * CW, (maxy - y) / (maxy - miny) * CH)

    # layers
    files = {}
    for f in glob.glob(os.path.join(case_dir, "*.geojson")):
        files[os.path.basename(f)[:-8]] = ("vector", f)
    grids = {}
    for f in glob.glob(os.path.join(case_dir, "*.asc")):
        parts = os.path.basename(f).split(".")
        lid, band = parts[0], parts[1]
        grids.setdefault(lid, {})[band] = f
    canvas = np.zeros((CH, CW, 4), np.float32)
    items = []           # drawable vector / coverage items
    labels = []          # label candidates
    seq = 0

    for li, lid in enumerate(view["layers"]):
        if lid in grids:
            kind = "coverage"
        elif lid in files:
            kind = "vector"
        else:
            raise FileNotFoundError("layer " + lid)
        if kind == "vector":
            gj = json.load(open(files[lid][1], encoding="utf-8"))
            for fi, feat in enumerate(gj["features"]):
                props = feat.get("properties") or {}
                sv = dict(sysv)
                sv.update({"dataLayer.id": lid, "dataLayer.identifier": lid,
                           "dataLayer.type": "vector", "feature.id": fi,
                           "feature.geometryDimensions": {"Point": 0, "LineString": 1, "Polygon": 2}[feat["geometry"]["type"]]})
                ctx = Ctx(props, sv, scale)
                flag = [False]
                state = walk(style["stylingRules"], {}, ctx, flag)
                if not flag[0]:
                    continue  # CHOICE R-unselected: no selecting rule -> not drawn
                S = parse_style(state, ctx, scale, case_dir)
                if not S["visible"]:
                    continue
                g = feat["geometry"]
                gt = g["type"]
                if gt == "Point":
                    geom = Point(*to_dev(*g["coordinates"]))
                    anchors = [(geom.x, geom.y)]
                    rings, lines = [], []
                elif gt == "LineString":
                    coords = [to_dev(x, y) for x, y in g["coordinates"]]
                    geom = LineString(coords)
                    rings, lines = [], [coords]
                elif gt == "Polygon":
                    ext = [to_dev(x, y) for x, y in g["coordinates"][0]]
                    holes = [[to_dev(x, y) for x, y in r] for r in g["coordinates"][1:]]
                    geom = Polygon(ext, holes)
                    rings = [ext] + holes
                    lines = []
                else:
                    raise NotImplementedError(gt)
                # bbox culling
                bx0, by0, bx1, by1 = geom.bounds
                if bx1 < 0 or by1 < 0 or bx0 > CW or by0 > CH:
                    if S["label"] is None:
                        continue
                items.append({"z": S["z"], "li": li, "fi": fi, "S": S, "geom": geom,
                              "gt": gt, "rings": rings, "lines": lines, "kind": "vector"})
                if S["label"] is not None and S["label"]["elements"]:
                    # label anchors (CHOICE L-anchor for polygons: centroid)
                    lab = S["label"]
                    if gt == "Point":
                        anc_list = [[(geom.x, geom.y)]]
                    elif gt == "LineString":
                        L = geom.length
                        ms = lab["minSpacing"]
                        if ms and ms > 0:
                            ms_ss = ms * SS          # minSpacing is in pixels; geometry is in SS pixels
                            K = int(math.floor((L / 2.0) / ms_ss))
                            ds = [L / 2.0 + k * ms_ss for k in range(-K, K + 1)]
                        else:
                            ds = [L / 2.0]   # CHOICE L-line-single: one label at mid-length
                        anc_list = []
                        for d in ds:
                            p = geom.interpolate(d)
                            anc_list.append([(p.x, p.y)])
                    else:
                        c = geom.centroid
                        anc_list = [[(c.x, c.y)]]
                    for anc in anc_list:
                        seq += 1
                        labels.append({"prio": lab["priority"], "seq": seq,
                                       "anchor": anc[0], "elements": lab["elements"]})
        else:
            # coverage layer: one raster per band set
            bands = grids[lid]
            band_name = sorted(bands.keys())[0]
            grid, cs, xll, yll, nrows, ncols, nodata = read_asc(bands[band_name])
            top = yll + nrows * cs
            Xs = minx + (np.arange(CW) + 0.5) / CW * (maxx - minx)
            Ys = maxy - (np.arange(CH) + 0.5) / CH * (maxy - miny)
            col = np.floor((Xs - xll) / cs).astype(int)
            row = np.floor((top - Ys) / cs).astype(int)
            cvalid = (col >= 0) & (col < ncols)
            rvalid = (row >= 0) & (row < nrows)
            colc = np.clip(col, 0, ncols - 1)
            rowc = np.clip(row, 0, nrows - 1)
            sampled = grid[np.ix_(rowc, colc)].astype(np.float64)
            sampled[~(rvalid[:, None] & cvalid[None, :])] = np.nan
            sampled[sampled == nodata] = np.nan
            sv = dict(sysv)
            sv.update({"dataLayer.id": lid, "dataLayer.identifier": lid, "dataLayer.type": "coverage"})
            ctx = Ctx({}, sv, scale)
            flag = [False]
            state = walk(style["stylingRules"], {}, ctx, flag)
            if not flag[0]:
                continue
            ctx_c = Ctx({band_name: sampled}, sv, scale)
            S = parse_style(state, ctx_c, scale, case_dir)
            if not S["visible"]:
                continue
            items.append({"z": S["z"], "li": li, "fi": 0, "S": S, "kind": "coverage",
                          "sampled": sampled, "grid": grid, "cs": cs, "xll": xll, "top": top,
                          "nodata": nodata, "colc": colc, "rowc": rowc,
                          "valid": rvalid[:, None] & cvalid[None, :]})

    # drawing passes per zOrder value
    zs = sorted(set(it["z"] for it in items))
    for z in zs:
        group = sorted([it for it in items if it["z"] == z], key=lambda it: (it["li"], it["fi"]))
        # pass 1: casings beneath main strokes (spec: casings of all features of the same zOrder)
        for it in group:
            if it["kind"] != "vector":
                continue
            st = it["S"]["stroke"]
            if st and st["casing"] and st["width"] + 2 * st["casing"]["width"] > 0:
                c = st["casing"]
                w = (st["width"] + 2 * c["width"]) * SS  # total width = main + 2 * casing width
                shape = stroke_shape(it["rings"] if it["gt"] == "Polygon" else it["lines"], w, None, 0)
                pr = geom_alpha(shape, CW, CH)
                if pr:
                    composite_group(canvas, [prim(pr[2], pr[0], pr[1], c["color"], c["opacity"])], it["S"]["opacity"])
        # pass 2: fills, main strokes and markers, feature by feature
        for it in group:
            if it["kind"] == "coverage":
                composite_group(canvas, coverage_prims(it, CW, CH, scale), it["S"]["opacity"])
                continue
            S = it["S"]
            prims = []
            if it["gt"] == "Polygon" and S["fill"] is not None:
                fl = S["fill"]
                pg = geom_alpha(it["geom"], CW, CH)
                if pg is not None:
                    x0, y0, al = pg
                    if fl["hatch"] is not None:
                        h = fl["hatch"]
                        al2 = hatch_alpha(x0, y0, al, h["width"] * SS, h["angle"], h["distance"] * SS)
                        prims.append(prim(al2, x0, y0, fl["color"], fl["opacity"]))
                    elif fl["dotpattern"] is not None:
                        dp = fl["dotpattern"]
                        al2 = dot_grid_alpha(x0, y0, al, dp["h"] * SS, dp["v"] * SS, 1.0 * SS, CW, CH)
                        prims.append(prim(al2, x0, y0, fl["color"], fl["opacity"]))
                    elif fl["stipple"] is not None:
                        ratio = fl["stipple"]["ratio"]
                        pitch = 4.0 * SS
                        rad = pitch * math.sqrt(max(ratio, 0.0) / math.pi)  # CHOICE S-stipple
                        al2 = dot_grid_alpha(x0, y0, al, pitch, pitch, rad, CW, CH)
                        prims.append(prim(al2, x0, y0, fl["color"], fl["opacity"]))
                    else:
                        prims.append(prim(al, x0, y0, fl["color"], fl["opacity"]))
            st = S["stroke"]
            if st is not None and st["width"] > 0 and it["gt"] in ("Polygon", "LineString"):
                rings = it["rings"] if it["gt"] == "Polygon" else it["lines"]
                dashes = None
                if st["dashes"] is not None:
                    dashes = [d * SS for d in st["dashes"]]
                shape = stroke_shape(rings, st["width"] * SS, dashes, st["dashoffset"] * SS)
                pr = geom_alpha(shape, CW, CH)
                if pr:
                    prims.append(prim(pr[2], pr[0], pr[1], st["color"], st["opacity"]))
            if S["marker"]:
                if it["gt"] == "Point":
                    anchors = [(it["geom"].x, it["geom"].y)]
                elif it["gt"] == "LineString":
                    anchors = list(it["lines"][0])          # CHOICE M-vertices
                else:
                    c = it["geom"].centroid                 # CHOICE M-centroid
                    anchors = [(c.x, c.y)]
                for ax, ay in anchors:
                    for el in S["marker"]:
                        prims.extend(element_prims(el, ax, ay, CW, CH))
            composite_group(canvas, prims, S["opacity"])
        # pass 3: centre lines on top of the main strokes of this zOrder
        for it in group:
            if it["kind"] != "vector":
                continue
            st = it["S"]["stroke"]
            if st and st["center"] and st["center"]["width"] > 0 and it["gt"] in ("Polygon", "LineString"):
                c = st["center"]
                rings = it["rings"] if it["gt"] == "Polygon" else it["lines"]
                shape = stroke_shape(rings, c["width"] * SS, None, 0)
                pr = geom_alpha(shape, CW, CH)
                if pr:
                    composite_group(canvas, [prim(pr[2], pr[0], pr[1], c["color"], c["opacity"])], it["S"]["opacity"])

    # labels: a pass on top of all features, placed by priority without overlap
    placed = []
    lab_prims = []
    cands = sorted(labels, key=lambda c: (-c["prio"], c["seq"]))
    for c in cands:
        ax, ay = c["anchor"]
        if ax < 0 or ay < 0 or ax > CW or ay > CH:
            continue  # CHOICE L-outside: anchor outside the map -> omitted
        boxes = []
        for el in c["elements"]:
            if el["type"] == "Text":
                boxes.append(text_box(el, ax, ay))
            elif el["type"] == "Dot":
                r = el["size"] * SS / 2.0
                boxes.append((ax + el["pos"][0] * SS - r, ay - el["pos"][1] * SS - r,
                              ax + el["pos"][0] * SS + r, ay - el["pos"][1] * SS + r))
        if not boxes:
            continue
        bx0 = min(b[0] for b in boxes)
        by0 = min(b[1] for b in boxes)
        bx1 = max(b[2] for b in boxes)
        by1 = max(b[3] for b in boxes)
        if any(not (bx1 <= p[0] or bx0 >= p[2] or by1 <= p[1] or by0 >= p[3]) for p in placed):
            continue  # rec/labels/overlap: omit labels that would overlap a placed label
        placed.append((bx0, by0, bx1, by1))
        for el in c["elements"]:
            if el["type"] == "Text":
                lab_prims.extend(text_prims(el, ax, ay, CW, CH))
            else:
                lab_prims.extend(element_prims(el, ax, ay, CW, CH))
    composite_group(canvas, lab_prims, 1.0)

    # downsample and composite on white
    img = canvas.reshape(H, SS, W, SS, 4).mean(axis=(1, 3))
    a = img[..., 3:4]
    rgb = img[..., :3] + (1.0 - a)   # background white
    out = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(out, "RGB").save(out_path)


def element_prims(el, ax, ay, CW, CH):
    if el["type"] == "Dot":
        if el["size"] <= 0:
            return []   # CHOICE D-negative: a non-positive size draws nothing
        cx = ax + el["pos"][0] * SS
        cy = ay - el["pos"][1] * SS
        pr = disc_alpha(cx, cy, el["size"] * SS / 2.0, CW, CH)
        if pr is None:
            return []
        return [prim(pr[2], pr[0], pr[1], el["color"], el["opacity"])]
    if el["type"] == "Text":
        return text_prims(el, ax, ay, CW, CH)
    if el["type"] == "Image":
        return [(p[0], p[1], p[2] * np.float32(el["opacity"])) for p in image_prims(el, ax, ay)]
    raise NotImplementedError(el["type"])


def coverage_prims(it, CW, CH, scale):
    S = it["S"]
    val = it["sampled"]
    if S["single"] is None:
        return []
    single = np.asarray(S["single"], dtype=np.float64)
    if single.shape != val.shape:
        single = np.broadcast_to(single, val.shape)
    nanm = np.isnan(single)
    hill = S["hill"]
    shade = None
    if hill is not None:
        shade_grid = compute_shade(it["grid"], it["cs"], hill["factor"], hill["az"], hill["el"])
        shade = shade_grid[np.ix_(it["rowc"], it["colc"])]
        shade = np.where(it["valid"], shade, np.nan)
    if S["colorMap"] is not None:
        rgb = interp_map(np.where(nanm, 0.0, single), S["colorMap"][0], S["colorMap"][1])
    else:
        rgb = np.ones(val.shape + (3,))   # CHOICE H-base: no colour map -> white base
    if hill is not None:
        if hill["colorMap"] is not None:
            sh = np.where(np.isnan(shade), 0.0, shade)
            rgb = interp_map(sh, hill["colorMap"][0], hill["colorMap"][1])   # CHOICE H-replace
        else:
            sh = np.where(np.isnan(shade), 0.0, shade)
            rgb = rgb * sh[..., None]                                       # spec: multiply
    alpha = np.ones(val.shape)
    if S["opacityMap"] is not None:
        alpha = alpha * interp_map(np.where(nanm, 0.0, single), S["opacityMap"][0], S["opacityMap"][1])
    if hill is not None and hill["opacityMap"] is not None:
        sh = np.where(np.isnan(shade), 0.0, shade)
        alpha = alpha * interp_map(sh, hill["opacityMap"][0], hill["opacityMap"][1])
    alpha = alpha * S["alpha"]
    alpha = np.where(nanm | np.isnan(alpha), 0.0, alpha)
    if hill is not None:
        alpha = np.where(np.isnan(shade), 0.0, alpha)
    arr = np.empty(val.shape + (4,), np.float32)
    a = np.clip(alpha, 0, 1).astype(np.float32)
    arr[..., :3] = (np.clip(rgb, 0, 1) * a[..., None]).astype(np.float32)
    arr[..., 3] = a
    return [(0, 0, arr)]


def read_asc(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        header = {}
        for _ in range(6):
            k, v = fh.readline().split()
            header[k.lower()] = v
        data = np.loadtxt(fh, dtype=np.float64)
    ncols = int(header["ncols"])
    nrows = int(header["nrows"])
    cs = float(header["cellsize"])
    xll = float(header["xllcorner"])
    yll = float(header["yllcorner"])
    nodata = float(header["nodata_value"])
    return data.reshape(nrows, ncols), cs, xll, yll, nrows, ncols, nodata


def main():
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:]
    done = 0
    for case in sorted(os.listdir(CASES)):
        cdir = os.path.join(CASES, case)
        if not os.path.isfile(os.path.join(cdir, "style.cs.json")):
            continue
        if only and case not in only:
            continue
        for vf in sorted(glob.glob(os.path.join(cdir, "view-*.json"))):
            n = os.path.basename(vf)[5:-5]
            out_path = os.path.join(OUT, "%s-%s.png" % (case, n))
            render_case(cdir, vf, out_path)
            done += 1
            print("rendered", out_path, flush=True)
    print("total images", done)


if __name__ == "__main__":
    main()
