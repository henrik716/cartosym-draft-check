"""Render vector features to SVG following the draft requirements.

Supports the Part 1 vector capabilities: fill (color, opacity, hatch, stipple,
dot pattern), stroke (color, width, opacity, dashPattern, casing, center),
markers (Dot, Text with font outline, Image), labels (priority, collision,
repetition along lines), coverages (see :mod:`.coverage`), Part 2 gradient
fills, and Symbolizer visibility, opacity and zOrder.
"""

from __future__ import annotations

import functools
import html
import itertools
import math
import random
from dataclasses import dataclass, field
from typing import Any

from .cascade import resolve
from .coverage import Grid, parse_color, portray
from .evaluate import Context
from .options import Options

MM_PER_PX = 0.28  # standard display pixel (OGC API - Maps, SE)


@dataclass
class Layer:
    id: str
    features: list[dict] = field(default_factory=list)  # GeoJSON features
    type: str = "vector"
    grid: Grid | None = None  # for type "coverage"


@dataclass
class View:
    bbox: tuple[float, float, float, float]  # minx, miny, maxx, maxy in metres
    width: int = 300
    height: int = 200
    background: str = "#f4f1ea"
    system: dict[str, Any] = field(default_factory=dict)
    # /req/variables/definition: values the application sets at run time, overriding the style's definitions.
    variables: dict[str, Any] = field(default_factory=dict)

    @property
    def px_per_m(self) -> float:
        return self.width / (self.bbox[2] - self.bbox[0])

    @property
    def scale_denominator(self) -> float:
        return 1000 / (MM_PER_PX * self.px_per_m)

    def xy(self, x: float, y: float) -> tuple[float, float]:
        return ((x - self.bbox[0]) * self.px_per_m, (self.bbox[3] - y) * self.px_per_m)


def to_px(value: Any, view: View, default: float = 0) -> float:
    """Resolve a uom-qualified value (/req/vector/units) to pixels."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict) and len(value) == 1:
        unit, v = next(iter(value.items()))
        factor = {"px": 1, "m": view.px_per_m, "ft": 0.3048 * view.px_per_m, "mm": 1 / MM_PER_PX,
                  "pt": 25.4 / 72 / MM_PER_PX, "inch": 25.4 / MM_PER_PX, "in": 25.4 / MM_PER_PX,
                  "cm": 10 / MM_PER_PX}.get(unit)
        if factor is not None:
            return float(v) * factor
    return default


def color(c: Any) -> str:
    if isinstance(c, dict) and {"r", "g", "b"} <= set(c):
        return f"rgb({c['r']},{c['g']},{c['b']})"
    if isinstance(c, (list, tuple)) and len(c) == 3:
        return f"rgb({c[0]},{c[1]},{c[2]})"
    return str(c) if c is not None else "none"


class _Svg:
    # Shared across renders: ids must stay unique when several SVGs are
    # inlined in one HTML page, or url(#id) resolves to the first SVG's defs.
    _ids = itertools.count(1)

    def __init__(self, view: View):
        self.view = view
        self.defs: list[str] = []
        self.body: list[str] = []
        # The casings (with casing_pass == "all-first") and center lines of the feature being painted;
        # render() draws them for all features of a zOrder at once.
        self.casings: list[str] = []
        self.centers: list[str] = []

    def new_id(self, prefix: str) -> str:
        return f"{prefix}{next(self._ids)}"

    def text(self) -> str:
        v = self.view
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{v.width}" height="{v.height}" '
            f'viewBox="0 0 {v.width} {v.height}"><defs>{"".join(self.defs)}</defs>'
            f'<rect width="100%" height="100%" fill="{v.background}"/>{"".join(self.body)}</svg>'
        )


def _rings_path(rings: list, view: View) -> str:
    parts = []
    for ring in rings:
        pts = [view.xy(*p[:2]) for p in ring]
        parts.append("M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z")
    return " ".join(parts)


def _line_path(coords: list, view: View) -> str:
    pts = [view.xy(*p[:2]) for p in coords]
    return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts)


def _parts(geom: dict) -> tuple[list, list, list]:
    """Split a geometry into (points, lines, polygons)."""
    t, c = geom["type"], geom.get("coordinates")
    if t == "Point":
        return [c], [], []
    if t == "MultiPoint":
        return list(c), [], []
    if t == "LineString":
        return [], [c], []
    if t == "MultiLineString":
        return [], list(c), []
    if t == "Polygon":
        return [], [], [c]
    if t == "MultiPolygon":
        return [], [], list(c)
    if t == "GeometryCollection":
        pts, lns, pls = [], [], []
        for g in geom["geometries"]:
            a, b, d = _parts(g)
            pts += a
            lns += b
            pls += d
        return pts, lns, pls
    return [], [], []


def _centroid(rings: list) -> tuple[float, float]:
    ring = rings[0]
    a = cx = cy = 0.0
    for (x0, y0, *_), (x1, y1, *_) in zip(ring, ring[1:]):
        f = x0 * y1 - x1 * y0
        a += f
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    if a == 0:
        return ring[0][0], ring[0][1]
    return cx / (3 * a), cy / (3 * a)


# ----------------------------------------------------------------- fills

def _fill_paint(svg: _Svg, fill: dict, path: str, opacity_mul: float, opts: Options) -> list[str]:
    view = svg.view
    out = []
    fc = color(fill.get("color"))
    fo = float(fill.get("opacity", 1)) * opacity_mul
    hatch, stipple, dots = fill.get("hatch"), fill.get("stipple"), fill.get("dotpattern")
    gradient = fill.get("gradient")

    if gradient:  # Part 2 /req/gradients/*
        out += _gradient_paint(svg, gradient, path, fo, opts)
        return out

    # An empty object ({}) means "with default values", so test for presence.
    if hatch is None and stipple is None and dots is None:
        out.append(f'<path d="{path}" fill="{fc}" fill-opacity="{fo:g}" fill-rule="evenodd"/>')
        return out

    clip = svg.new_id("clip")
    svg.defs.append(f'<clipPath id="{clip}"><path d="{path}" fill-rule="evenodd"/></clipPath>')

    if hatch is not None:  # /req/hatches/*: defaults 1 px, 45 degrees, 10 px
        w = to_px(hatch.get("width"), view, 1)
        d = to_px(hatch.get("distance"), view, 10)
        angle = float(hatch.get("angle", 45))
        rot = angle if opts.hatch_angle == "clockwise" else -angle
        pid = svg.new_id("hatch")
        svg.defs.append(
            f'<pattern id="{pid}" width="{d:g}" height="{d:g}" patternUnits="userSpaceOnUse" '
            # One line centred on the tile edge (half at the top, half at the bottom), so a line passes
            # through the map's origin: the pattern's phase is not stated, and this is what the three
            # independent renderers chose.
            f'patternTransform="rotate({rot:g})"><g stroke="{fc}" stroke-width="{w:g}">'
            f'<line x1="0" y1="0" x2="{d:g}" y2="0"/><line x1="0" y1="{d:g}" x2="{d:g}" y2="{d:g}"/></g></pattern>'
        )
        out.append(f'<path d="{path}" fill="url(#{pid})" fill-opacity="{fo:g}" fill-rule="evenodd"/>')

    # How a stipple or dot-pattern dot looks is not defined (#84): either small
    # dots in the fill color, or the Dot class defaults (white, 10 px).
    dot_defaults = opts.dots == "dot-defaults"
    dot_color = "white" if dot_defaults else fc
    dot_size = 10.0 if dot_defaults else 1.0

    if stipple is not None:  # /req/stipples/ratio: fraction of the area covered by dots
        ratio = float(stipple.get("ratio", 0.5))
        rng = random.Random(42)
        n = int(ratio * view.width * view.height / (dot_size * dot_size))
        if dot_defaults:
            r = dot_size / 2
            dots_svg = "".join(
                f'<circle cx="{rng.uniform(0, view.width):.1f}" cy="{rng.uniform(0, view.height):.1f}" r="{r:g}"/>'
                for _ in range(n)
            )
        else:
            # Distinct pixels, so that the dots cover the `ratio` fraction of the area.
            cells = rng.sample(range(view.width * view.height), min(n, view.width * view.height))
            dots_svg = "".join(f'<rect x="{i % view.width}" y="{i // view.width}" width="1" height="1"/>'
                               for i in cells)
        out.append(f'<g clip-path="url(#{clip})" fill="{dot_color}" fill-opacity="{fo:g}">{dots_svg}</g>')

    if dots is not None:  # /req/dot-patterns/distance
        dist = dots.get("distance") or {}
        if isinstance(dist, list):
            dist = {"horizontal": dist[0], "vertical": dist[1]}
        dx = to_px(dist.get("horizontal"), view, 8)
        dy = to_px(dist.get("vertical"), view, 8)
        pid = svg.new_id("dots")
        r = dot_size / 2 if dot_defaults else 1.0  # /req/dot-patterns/dotpattern: 2 pixels across
        svg.defs.append(
            f'<pattern id="{pid}" width="{dx:g}" height="{dy:g}" patternUnits="userSpaceOnUse">'
            f'<circle cx="{dx / 2:g}" cy="{dy / 2:g}" r="{r:g}" fill="{dot_color}"/></pattern>'
        )
        out.append(f'<path d="{path}" fill="url(#{pid})" fill-opacity="{fo:g}" fill-rule="evenodd"/>')
    return out


def _path_bbox(path: str) -> tuple[float, float, float, float]:
    nums = [float(v) for v in path.replace("M", " ").replace("L", " ").replace("Z", " ").replace(",", " ").split()]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def _gradient_paint(svg: _Svg, g: dict, path: str, fo: float, opts: Options) -> list[str]:
    """Part 2 gradient fill. Angle convention and reference frame are options."""
    view = svg.view
    if opts.gradient_frame == "feature":
        x0, y0, x1, y1 = _path_bbox(path)
    else:
        x0, y0, x1, y1 = 0.0, 0.0, float(view.width), float(view.height)
    w, h = x1 - x0, y1 - y0
    keys = g.get("keys") or []
    n = len(keys)
    stops = []
    for i, k in enumerate(keys):
        pct = k.get("percent", i / (n - 1) if n > 1 else 0)
        stops.append((float(pct), color(k.get("color")), float(k.get("opacity", 1))))
    stops_svg = "".join(f'<stop offset="{p:g}" stop-color="{c}" stop-opacity="{o:g}"/>' for p, c, o in stops)
    pos = g.get("position") or [0.5, 0.5]
    cx, cy = x0 + float(pos[0]) * w, y0 + float(pos[1]) * h
    size = float(g.get("size", 1))
    kind = g.get("type", "linear")
    angle = math.radians(float(g.get("angle", 0)))
    if opts.gradient_angle == "css":  # 0 = towards the top, clockwise
        dx, dy = math.sin(angle), -math.cos(angle)
    else:  # 0 = towards the right, counter-clockwise (screen y is down)
        dx, dy = math.cos(angle), -math.sin(angle)
    gid = svg.new_id("grad")

    if kind == "conic":  # no SVG primitive: wedges around the centre
        r = math.hypot(w, h)
        start = math.atan2(dy, dx)
        wedges = []
        for i in range(72):
            t0, t1 = i / 72, (i + 1) / 72
            a0, a1 = start + t0 * 2 * math.pi, start + t1 * 2 * math.pi
            c = _interp_stop(stops, (t0 + t1) / 2)
            wedges.append(f'<path d="M{cx:.1f},{cy:.1f} L{cx + r * math.cos(a0):.1f},{cy + r * math.sin(a0):.1f} '
                          f'L{cx + r * math.cos(a1):.1f},{cy + r * math.sin(a1):.1f} Z" fill="{c}" '
                          f'stroke="{c}" stroke-width="1"/>')  # the stroke hides antialiasing seams
        clip = svg.new_id("clip")
        svg.defs.append(f'<clipPath id="{clip}"><path d="{path}" fill-rule="evenodd"/></clipPath>')
        return [f'<g clip-path="url(#{clip})" opacity="{fo:g}">{"".join(wedges)}</g>']

    if kind == "radial":
        rad = size * max(w, h) / 2
        svg.defs.append(f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{cx:.1f}" cy="{cy:.1f}" '
                        f'r="{rad:.1f}">{stops_svg}</radialGradient>')
    else:  # linear, or repeating (a linear gradient repeated every size)
        half = size * (abs(dx) * w + abs(dy) * h) / 2
        spread = ' spreadMethod="repeat"' if kind == "repeating" else ""
        if kind == "repeating":
            half = size * (abs(dx) * w + abs(dy) * h) / 2 / 4  # four repetitions across the frame
        svg.defs.append(f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse"{spread} '
                        f'x1="{cx - dx * half:.1f}" y1="{cy - dy * half:.1f}" '
                        f'x2="{cx + dx * half:.1f}" y2="{cy + dy * half:.1f}">{stops_svg}</linearGradient>')
    return [f'<path d="{path}" fill="url(#{gid})" fill-opacity="{fo:g}" fill-rule="evenodd"/>']


def _interp_stop(stops: list[tuple[float, str, float]], t: float) -> str:
    """Color at position t between gradient stops."""
    pts = [(p, parse_color(c) or (0.0, 0.0, 0.0)) for p, c, _ in stops]
    if not pts:
        return "none"
    if t <= pts[0][0]:
        rgb = pts[0][1]
    elif t >= pts[-1][0]:
        rgb = pts[-1][1]
    else:
        (p0, c0), (p1, c1) = next((a, b) for a, b in zip(pts, pts[1:]) if a[0] <= t <= b[0])
        f = (t - p0) / (p1 - p0) if p1 > p0 else 0
        rgb = tuple(a + (b - a) * f for a, b in zip(c0, c1))
    return "rgb({},{},{})".format(*(round(v * 255) for v in rgb))


# ---------------------------------------------------------------- strokes

def _stroke_paint(svg: _Svg, stroke: dict, path: str, opacity_mul: float, opts: Options) -> list[str]:
    view = svg.view
    w = to_px(stroke.get("width"), view, 1)
    # /req/vector/stroke: round caps and round joins (#192, #193); a width of 0 or less draws nothing.
    attrs = 'fill="none" stroke-linejoin="round" stroke-linecap="round"'

    def one(st: dict, width: float, dash: str = "") -> str:
        o = float(st.get("opacity", 1)) * opacity_mul
        return (f'<path d="{path}" {attrs} stroke="{color(st.get("color"))}" '
                f'stroke-width="{width:g}" stroke-opacity="{o:g}"{dash}/>')

    dash = ""
    if stroke.get("dashPattern"):
        # /req/dashes/dash-pattern: lengths are UnitValues, in pixels unless
        # qualified. /per/dashes/dash-pattern-units: `pc` is percent of the
        # stroke width. The "stroke-width" option reads plain numbers as
        # multiples of the width, as MapLibre does.
        k = w if opts.dash_units == "stroke-width" else 1

        def length(v) -> float:
            if isinstance(v, dict) and set(v) == {"pc"}:
                return float(v["pc"]) / 100 * w
            return to_px(v, view, 0) * (k if isinstance(v, (int, float)) else 1)

        offset = length(stroke.get("dashOffset") or 0)
        dash = f' stroke-dasharray="{" ".join(f"{length(v):g}" for v in stroke["dashPattern"])}" stroke-dashoffset="{offset:g}"'

    main = one(stroke, w, dash) if w > 0 else None
    casing = stroke.get("casing")
    out: list[str] = []
    casing_svg = None
    # /req/core/default-values: casing and center lines have a width of 0 (none) unless one is set.
    if casing and to_px(casing.get("width"), view, 0) > 0:
        if opts.casing_width == "extra":
            cw = w + 2 * to_px(casing.get("width"), view, 0)
        else:
            cw = to_px(casing.get("width"), view, 0)
        casing_svg = one(casing, cw)
    if casing_svg and opts.casing == "below":
        if opts.casing_pass == "all-first":
            svg.casings.append(casing_svg)
        else:
            out.append(casing_svg)
    if main:
        out.append(main)
    if casing_svg and opts.casing == "above":
        out.append(casing_svg)
    center = stroke.get("center") or stroke.get("centerLine")
    if center and to_px(center.get("width"), view, 0) > 0:
        # /req/casing/center: the center lines of all features with the same zOrder go on top of
        # the main strokes of all those features.
        svg.centers.append(one(center, to_px(center.get("width"), view, 0)))
    return out


# ---------------------------------------------------------------- markers

def _text_anchor(el: dict) -> str:
    """SVG text-anchor for a Text graphic's horizontal alignment (left by default, /req/vector/text)."""
    align = el.get("alignment") or {}
    if isinstance(align, list):
        h = align[0] if align else "left"
    else:
        h = align.get("horizontal", "left") if align else "left"
    return {"left": "start", "right": "end"}.get(h, "middle")


def _text(el: dict, x: float, y: float, view: View, opacity_mul: float, opts: Options) -> str:
    font = el.get("font") or {}
    size = to_px({"pt": font["size"]} if isinstance(font.get("size"), (int, float)) else font.get("size"), view, 16)
    anchor = _text_anchor(el)
    align = el.get("alignment") or {}
    v = (align[1] if len(align) > 1 else "top") if isinstance(align, list) else align.get("vertical", "top")
    baseline = {"top": "hanging", "bottom": "text-after-edge"}.get(v, "middle")
    style = (f'font-family="{html.escape(str(font.get("face", "sans-serif")))}" font-size="{size:g}" '
             f'font-weight="{"bold" if font.get("bold") else "normal"}" '
             f'font-style="{"italic" if font.get("italic") else "normal"}" text-anchor="{anchor}" '
             f'dominant-baseline="{baseline}"')
    fo = float(font.get("opacity", 1)) * opacity_mul
    outline = font.get("outline")
    paint = ""
    if outline:
        ow = to_px(outline.get("size", outline.get("width")), view, 2)
        oo = float(outline.get("opacity", 1)) * opacity_mul
        order = "stroke" if opts.font_outline == "below" else "fill"
        paint = (f' stroke="{color(outline.get("color", "white"))}" stroke-width="{2 * ow:g}" '
                 f'stroke-opacity="{oo:g}" stroke-linejoin="round" paint-order="{order}"')
    return (f'<text x="{x:.2f}" y="{y:.2f}" {style} fill="{color(font.get("color", "black"))}" '
            f'fill-opacity="{fo:g}"{paint}>{html.escape(str(el.get("text", "")))}</text>')


def _offset(el: dict, view: View) -> tuple[float, float]:
    pos = el.get("position")
    # /req/vector/graphics: a positive y is downwards, as screen coordinates (#192).
    if isinstance(pos, list) and len(pos) == 2:
        return to_px(pos[0], view), to_px(pos[1], view)
    if isinstance(pos, dict):
        return to_px(pos.get("x"), view), to_px(pos.get("y"), view)
    return 0.0, 0.0


def _hotspot(value: Any, w: float, h: float, view: View) -> tuple[float, float] | None:
    """An Image hotSpot as fractions of the image size: `pc` is a percentage, other units are lengths
    from the top left corner, and plain numbers are pixels of the image (/req/vector/image, #192)."""
    if value is None:
        return None
    if isinstance(value, dict):
        value = [value.get("x", 0), value.get("y", 0)]
    out = []
    for v, size in zip(value, (w, h)):
        if isinstance(v, dict) and set(v) == {"pc"}:
            out.append(float(v["pc"]) / 100)
        elif isinstance(v, dict):
            out.append(to_px(v, view) / size if size else 0.0)
        else:
            out.append(float(v) / size if size else 0.0)
    return out[0], out[1]


def _marker_paint(marker: dict, x: float, y: float, view: View, opacity_mul: float, opts: Options) -> list[str]:
    out = []
    mo = float(marker.get("opacity", 1))
    for el in marker.get("elements") or []:
        if not isinstance(el, dict):
            continue
        ox, oy = _offset(el, view)
        px, py = x + ox, y + oy
        kind = el.get("type", "Dot")
        if kind == "Dot":  # /req/vector/dot
            size = to_px(el.get("size", (el.get("stroke") or {}).get("width")), view, 10)
            c = el.get("color", (el.get("stroke") or {}).get("color", "white"))
            if size <= 0:
                continue  # /req/vector/dot: nothing for a size of 0 or less
            out.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="{size / 2:g}" fill="{color(c)}" '
                       f'fill-opacity="{mo * opacity_mul:g}"/>')
        elif kind == "Text":  # /req/vector/text, /req/font-outlines/*
            out.append(_text(el, px, py, view, mo * opacity_mul, opts))
        elif kind == "Image":  # /req/vector/image
            w = to_px(el.get("width", {"px": 24}), view, 24)
            h = to_px(el.get("height", {"px": 24}), view, 24)
            hx, hy = _hotspot(el.get("hotSpot"), w, h, view) or opts.image_hotspot
            href = (el.get("image") or {}).get("uri") if isinstance(el.get("image"), dict) else el.get("image")
            # tint × v + blackTint × (1 − v) per channel; the defaults (white, black) leave the image unchanged.
            tint = parse_color(el.get("tint")) or (1.0, 1.0, 1.0)
            black = parse_color(el.get("blackTint")) or (0.0, 0.0, 0.0)
            filt = ""
            threshold = float(el.get("alphaThreshold") or 0)
            if threshold > 0:  # /per/vector/image-alpha-test: an alpha test, kept pixels become opaque
                steps = 100
                table = " ".join("0" if i / steps < threshold else "1" for i in range(steps + 1))
                aid = f"alpha{round(threshold * 1000)}"
                out.append(f'<filter id="{aid}"><feComponentTransfer><feFuncA type="discrete" '
                           f'tableValues="{table}"/></feComponentTransfer></filter>')
            if (tint, black) != ((1.0, 1.0, 1.0), (0.0, 0.0, 0.0)):
                # Same colors give the same filter, so a repeated id is harmless.
                fid = "tint" + "".join(f"{round(c * 255):02x}" for c in (*tint, *black))
                rows = [" ".join(f"{t - b:g}" if j == i else "0" for j in range(4)) + f" {b:g}"
                        for i, (t, b) in enumerate(zip(tint, black))]
                out.append(f'<filter id="{fid}" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" '
                           f'values="{" ".join(rows)} 0 0 0 1 0"/></filter>')
                filt = f' filter="url(#{fid})"'
            img = (f'<image href="{html.escape(str(href))}" x="{px - hx * w:.2f}" y="{py - hy * h:.2f}" '
                   f'width="{w:g}" height="{h:g}" opacity="{mo * opacity_mul:g}"{filt}/>')
            if threshold > 0:
                img = f'<g filter="url(#{aid})">{img}</g>'
            out.append(img)
    return out


@dataclass
class _Item:
    """What one feature (or coverage) draws, by drawing step; render() composes these per zOrder."""
    z: float  # zOrder key (negated with z_order == "lower-on-top")
    seq: int  # feature order
    layer: str
    opacity: float  # the resolved Symbolizer opacity
    fills: list[str] = field(default_factory=list)
    casings: list[str] = field(default_factory=list)
    strokes: list[str] = field(default_factory=list)  # main strokes and markers
    centers: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)  # with label_pass == "with-feature"


# ----------------------------------------------------------------- labels

@dataclass
class _Label:
    priority: float
    seq: int  # feature order, to break ties
    item: int  # index of the feature's _Item
    svg: str
    box: tuple[float, float, float, float]
    key: tuple = ()  # (layer, content): labels with the same key are repetitions of one label
    spacing: float = 0.0  # minSpacing in pixels


_FONT_FILES = {"arial": "arial", "tahoma": "tahoma", "times new roman": "times", "verdana": "verdana"}
_FONT_DIRS = ("C:/Windows/Fonts", "/usr/share/fonts/truetype/msttcorefonts", "/Library/Fonts")


@functools.lru_cache(maxsize=64)
def _font(face: str, size: float, bold: bool, italic: bool):
    """The TrueType font for measuring text, or None where Pillow or the font file is not available."""
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    base = _FONT_FILES.get(face.lower(), "arial")
    suffix = {(False, False): "", (True, False): "bd", (False, True): "i", (True, True): "bi"}[(bold, italic)]
    if base == "times":
        suffix = {"": "", "bd": "bd", "i": "i", "bi": "bi"}[suffix]
    for d in _FONT_DIRS:
        for name in (f"{base}{suffix}.ttf", f"{base}.ttf"):
            try:
                return ImageFont.truetype(f"{d}/{name}", max(1, round(size * 4)))  # 4x for sub-pixel accuracy
            except OSError:
                continue
    return None


def _label_size(el: dict, view: View) -> tuple[float, float]:
    """Text extent: the advance width and the font's ascent plus descent, measured with the font where
    Pillow and the font are available (as a browser would draw it), else 0.6 em per character."""
    font = el.get("font") or {}
    size = to_px({"pt": font["size"]} if isinstance(font.get("size"), (int, float)) else font.get("size"), view, 16)
    text = str(el.get("text", ""))
    f = _font(str(font.get("face", "Arial")), size, bool(font.get("bold")), bool(font.get("italic")))
    if f is None:
        return 0.6 * size * len(text), size
    ascent, descent = f.getmetrics()
    return f.getlength(text) / 4, (ascent + descent) / 4


def _along(points: list[tuple[float, float]], first: float, step: float) -> list[tuple[float, float, float]]:
    """Positions (x, y, angle in degrees) every *step* px along a polyline, starting at *first*."""
    out, travelled, target = [], 0.0, first
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        while seg > 0 and target <= travelled + seg:
            t = (target - travelled) / seg
            ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
            if ang > 90 or ang < -90:  # keep text upright
                ang += 180
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, ang))
            target += step
        travelled += seg
    return out


def _label_candidates(label: dict, pts, lines, polys, view: View, mul: float, opts: Options) -> list[tuple]:
    """(svg, box) for each place a label would go; repeated along lines."""
    placement = label.get("placement") or {}
    unit = "m" if opts.label_spacing_units == "m" else "px"
    min_sp = placement.get("minSpacing")
    if not isinstance(min_sp, (int, float)):
        min_sp = placement.get("maxSpacing")  # repeat at most every maxSpacing where space allows
    spacing = to_px({unit: min_sp}, view) if isinstance(min_sp, (int, float)) else None
    anchors: list[tuple[float, float, float]] = [(*view.xy(*p[:2]), 0.0) for p in pts]
    anchors += [(*view.xy(*_centroid(poly)), 0.0) for poly in polys]
    for line in lines:
        screen = [view.xy(*p[:2]) for p in line]
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(screen, screen[1:]))
        if spacing:
            anchors += _along(screen, spacing / 2, spacing)
        else:
            anchors += _along(screen, length / 2, length + 1)
    out = []
    elements = [el for el in label.get("elements") or [] if isinstance(el, dict)]
    for x, y, ang in anchors:
        # All of a label's graphics (Text, Dot, Image) are placed together, as one label.
        frags, boxes = [], []
        for el in elements:
            ox, oy = _offset(el, view)
            lx, ly = x + ox, y + oy
            if el.get("type", "Text") == "Text":
                w, h = _label_size(el, view)
                frags.append(_text(el, lx, ly, view, mul, opts))
                left = {"start": lx, "end": lx - w}.get(_text_anchor(el), lx - w / 2)
                c, s_ = abs(math.cos(math.radians(ang))), abs(math.sin(math.radians(ang)))
                bw, bh = w * c + h * s_, w * s_ + h * c
                boxes.append((left, ly - bh / 2, left + bw, ly + bh / 2))
            else:
                frags += _marker_paint({"elements": [el]}, x, y, view, mul, opts)
                size = to_px(el.get("size", (el.get("stroke") or {}).get("width")), view, 10) \
                    if el.get("type", "Dot") == "Dot" else to_px(el.get("width", {"px": 24}), view, 24)
                boxes.append((lx - size / 2, ly - size / 2, lx + size / 2, ly + size / 2))
        if not frags:
            continue
        svg = "".join(frags)
        if ang:
            svg = f'<g transform="rotate({ang:.1f} {x:.1f} {y:.1f})">{svg}</g>'
        out.append((svg, (min(b[0] for b in boxes), min(b[1] for b in boxes),
                          max(b[2] for b in boxes), max(b[3] for b in boxes))))
    return out


def _center(box) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _overlaps(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# ------------------------------------------------------------------ main

# /req/core/expressions-system-identifiers: the requirements classes the draft renderer implements.
CAPABILITIES = {f"capabilities.{c}": True for c in (
    "vector", "coverage", "labels", "hillshading", "fontoutlines", "hatches", "stipples", "dashes", "casing",
    "parametervalues", "functions", "math", "arrayrelations", "textmanipulation", "arithmetic", "textrelation",
    "righthand", "conditional", "variables", "dotpatterns")}

# The NULL reports of the last call to render() (/rec/parameter-values/report-null).
LAST_NULL_REPORTS: list = []

_DIMENSIONS = {"Point": 0, "MultiPoint": 0, "LineString": 1, "MultiLineString": 1, "Polygon": 2, "MultiPolygon": 2}


def _geometry_dimensions(layer: Layer) -> int | None:
    """dataLayer.featuresGeometryDimensions: the dimension of the layer's geometries, if they all have the same one."""
    if layer.type != "vector" or not layer.features:
        return None
    dims = {_DIMENSIONS.get((f.get("geometry") or {}).get("type")) for f in layer.features}
    return dims.pop() if len(dims) == 1 and None not in dims else None


def render(style: dict, layers: list[Layer], view: View, opts: Options | None = None,
           anchors: bool = False) -> str:
    """Render *layers* with *style* to an SVG string.

    With ``anchors=True``, a small cross is drawn at every point feature so the
    position of marker graphics relative to the point can be seen.
    """
    opts = opts or Options()
    svg = _Svg(view)
    null_reports: list = []
    items: list[_Item] = []
    labels: list[_Label] = []
    seq = 0
    for layer in layers:
        system = {"viz.sd": view.scale_denominator, "visualization.scaleDenominator": view.scale_denominator,
                  "dataLayer.id": layer.id, "dataLayer.identifier": layer.id, "dataLayer.type": layer.type,
                  **CAPABILITIES, **view.system}
        dims = _geometry_dimensions(layer)
        if dims is not None:
            system["dataLayer.featuresGeometryDimensions"] = dims
        if layer.type == "coverage" and layer.grid is not None:
            result = portray(style, layer.grid, system, opts)
            if result:
                z, uri = result
                gx0, gy1 = view.xy(layer.grid.bbox[0], layer.grid.bbox[1])
                gx1, gy0 = view.xy(layer.grid.bbox[2], layer.grid.bbox[3])
                frag = (f'<image href="{uri}" x="{gx0:.2f}" y="{gy0:.2f}" width="{gx1 - gx0:.2f}" '
                        f'height="{gy1 - gy0:.2f}" preserveAspectRatio="none" style="image-rendering:pixelated"/>')
                items.append(_Item(z if opts.z_order == "higher-on-top" else -z, seq, layer.id, 1.0, fills=[frag]))
                seq += 1
            continue
        for feat in layer.features:
            ctx = Context(properties=feat.get("properties") or {}, system=system, options=opts,
                          variables=view.variables, null_reports=null_reports)
            sym = resolve(style, ctx)
            if sym.get("visibility") is False:
                continue
            op = float(sym.get("opacity", 1))
            mul = op if opts.opacity == "per-element" else 1.0
            z = float(sym.get("zOrder", 1))
            svg.casings, svg.centers = [], []
            fills: list[str] = []
            frags: list[str] = []  # main strokes and markers
            pts, lines, polys = _parts(feat["geometry"])
            for poly in polys:
                path = _rings_path(poly, view)
                fills += _fill_paint(svg, sym.get("fill") or {}, path, mul, opts)
                frags += _stroke_paint(svg, sym.get("stroke") or {}, path, mul, opts)
            for line in lines:
                frags += _stroke_paint(svg, sym.get("stroke") or {}, _line_path(line, view), mul, opts)
            marker = sym.get("marker")
            if marker and marker.get("elements"):
                at = [view.xy(*p[:2]) for p in pts]
                at += [view.xy(*p[:2]) for line in lines for p in line]  # vertices of lines
                at += [view.xy(*_centroid(poly)) for poly in polys]  # centroid of polygons
                for x, y in at:
                    frags += _marker_paint(marker, x, y, view, mul, opts)
            if anchors:
                for p in pts:
                    x, y = view.xy(*p[:2])
                    cross = f"M{x - 7:.1f},{y:.1f} H{x + 7:.1f} M{x:.1f},{y - 7:.1f} V{y + 7:.1f}"
                    frags.append(f'<path d="{cross}" stroke="white" stroke-width="4"/>'
                                 f'<path d="{cross}" stroke="black" stroke-width="1.5"/>')
            label = sym.get("label")
            if isinstance(label, dict) and label.get("elements"):
                placement = label.get("placement") or {}
                prio = float(placement.get("priority", 0) or 0)
                min_sp = placement.get("minSpacing")
                spacing = to_px({"m" if opts.label_spacing_units == "m" else "px": min_sp}, view) \
                    if isinstance(min_sp, (int, float)) else 0.0
                content = tuple(str(el.get("text")) for el in label["elements"] if isinstance(el, dict))
                # The Symbolizer opacity does not apply to labels (NOTE in /req/core/opacity).
                for text, box in _label_candidates(label, pts, lines, polys, view, 1.0, opts):
                    labels.append(_Label(prio, seq, len(items), text, box, (layer.id, content), spacing))
            items.append(_Item(z if opts.z_order == "higher-on-top" else -z, seq, layer.id, op,
                               fills, svg.casings, frags, svg.centers))
            seq += 1

    # /req/labels/*: place in priority order, dropping labels that would overlap.
    sign = -1 if opts.label_priority == "higher-wins" else 1
    placed: list[_Label] = []
    for lb in sorted(labels, key=lambda lb: (sign * lb.priority, lb.seq)):
        x0, y0, x1, y1 = lb.box
        if x0 < 0 or y0 < 0 or x1 > view.width or y1 > view.height:
            continue  # would be cut off at the edge of the map
        if any(_overlaps(lb.box, p.box) for p in placed):
            continue
        if lb.spacing and any(p.key == lb.key and math.dist(_center(p.box), _center(lb.box)) < lb.spacing
                              for p in placed):
            continue  # /req/labels/placement: a repetition closer than minSpacing
        placed.append(lb)
        if opts.label_pass == "with-feature":
            items[lb.item].labels.append(lb.svg)

    # Within a zOrder: the fills of all features, then their casings, main strokes (with markers)
    # and center lines (/req/casing/casing, /req/casing/center; the order is Jérôme's on #198). So a
    # bridge's casing covers the roads below it, and the casings of joining lines merge.
    # /rec/core/opacity-together: with "whole", translucent features are made transparent as one
    # group per data layer, zOrder and opacity, drawn in the same order inside the group; labels
    # stay outside it (NOTE in /req/core/opacity).
    for z in sorted({it.z for it in items}):
        groups: dict[tuple | None, list[_Item]] = {}
        for it in sorted((it for it in items if it.z == z), key=lambda it: it.seq):
            key = (it.layer, it.opacity) if opts.opacity == "whole" and it.opacity < 1 else None
            groups.setdefault(key, []).append(it)
        for key, group in groups.items():
            body = ("".join(f for it in group for f in it.fills)
                    + "".join(c for it in group for c in it.casings)
                    + "".join("".join(it.strokes) + ("" if key else "".join(it.labels)) for it in group)
                    + "".join(c for it in group for c in it.centers))
            if key:
                # The same as opacity="…" on the group, but as a filter whose region is the map: resvg
                # (0.5.0) drops the tinted images of an opacity group reaching far beyond a nested
                # <svg>, as each panel of the document figures is.
                fid = svg.new_id("op")
                svg.defs.append(f'<filter id="{fid}" filterUnits="userSpaceOnUse" x="0" y="0" width="{view.width}" '
                                f'height="{view.height}" color-interpolation-filters="sRGB"><feComponentTransfer>'
                                f'<feFuncA type="linear" slope="{key[1]:g}"/></feComponentTransfer></filter>')
                body = f'<g filter="url(#{fid})">{body}</g>' + "".join(lb for it in group for lb in it.labels)
            svg.body.append(body)
    if opts.label_pass == "on-top":
        svg.body.extend(lb.svg for lb in sorted(placed, key=lambda lb: lb.seq))
    LAST_NULL_REPORTS[:] = null_reports
    if null_reports:
        # /rec/parameter-values/report-null: reported in the SVG, one line per property.
        keys = sorted({str(k) for k, _ in null_reports})
        svg.body.append(f"<!-- NULL values: {len(null_reports)} for {', '.join(keys)} -->")
    return svg.text()


__all__ = ["Grid", "Layer", "View", "render", "to_px"]
