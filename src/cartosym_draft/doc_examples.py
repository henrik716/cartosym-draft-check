"""Renders, CartoSym-JSON and AsciiDoc blocks for the examples in the Part 1 document.

Usage: python -m cartosym_draft.doc_examples [--spec ../cartographic-symbology] [name ...]

For each example below, reads ``1-core/examples/<name>.cscss`` from the spec
repository, converts it to CartoSym-JSON with pycartosym (plus the fix-ups in
:func:`to_json` for what pycartosym 0.6.4 loses), validates the JSON against the
spec's schema, renders it with the draft renderer on the Rondane data (Kartverket
N50, the elevation model and a Sentinel-2 scene) and writes:

- ``1-core/examples/<name>.cs.json``: the CartoSym-JSON;
- ``1-core/figures/examples/<name>.png``: the render, one panel per scale;
- ``1-core/examples/<name>.adoc``: the render above a two-column table with the
  CartoSym-CSS and the CartoSym-JSON, for the document to include.

Vector examples are drawn over a light grey context (hill shading and lakes) that
is not part of the style; the figure caption says so.
"""

from __future__ import annotations

import argparse
import base64
import copy
import datetime
import json
import logging
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import pycartosym

from . import n50, sample_data
from .options import Options
from .coverage import Grid
from .render import MM_PER_PX, Layer, View, render

ROOT = Path(__file__).resolve().parent.parent.parent
DRAFT = Options()  # the draft as written, including the default Dot marker

# The view's time, for viz.date and viz.timeInterval (validDate in the N50 layers runs from 1988 to 2026).
VIEW_DATE = datetime.date(2026, 11, 14)
TIME_INTERVAL = (datetime.date(1980, 1, 1), VIEW_DATE)

MYSUSAETER = (15239, 3983)  # local metres from the south-west corner of the Rondane box
MYRTJORNA = (38200, 11700)
RONDVASSBU = (21624, 11147)
WHOLE = (22500, 15000)  # centre of the 45 x 30 km box
WHOLE_SD = 45000 / (900 * MM_PER_PX / 1000)  # 900 px across the whole box: 1:178 571
WHOLE_SD_600 = 45000 / (600 * MM_PER_PX / 1000)  # 600 px across: 1:267 857


@dataclass
class Panel:
    scale: float  # scale denominator
    center: tuple[float, float]
    width: int = 440
    height: int = 300

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        m = self.scale * MM_PER_PX / 1000  # metres per pixel
        cx, cy = self.center
        return (cx - self.width * m / 2, cy - self.height * m / 2, cx + self.width * m / 2, cy + self.height * m / 2)

    @property
    def label(self) -> str:
        return f"1:{round(self.scale):,}".replace(",", " ")


@dataclass
class DocExample:
    name: str  # file stem in 1-core/examples (or in its subdir)
    title: str  # figure caption
    layers: list[str]
    panels: list[Panel]
    context: bool | str = True  # True: land cover, relief and rivers; "relief": the relief shadows only
    notes: list[str] = field(default_factory=list)
    subdir: str = ""  # "requirements" for the examples placed under requirements
    requirements: list[str] = field(default_factory=list)
    time_interval: tuple[datetime.date, datetime.date] = TIME_INTERVAL
    # The CartoSym-JSON is written by hand because pycartosym loses something (see PYCARTOSYM_GAPS);
    # the build checks that pycartosym's output equals it apart from those gaps.
    manual_json: bool = False


# Further anchors, in local metres
OTTA_ROADS = (5000, 6500)  # E6, Rv 15 and county roads near Otta
RONDSLOTTET = (24760, 14925)
RONDVASSBU_WIDE = (22000, 12500)
MYSUSAETER_WIDE = (16000, 6000)
SEL = (7000, 5800)  # the E6, Rv 15 and county roads in the Sel valley
SELSVERKET = (8250, 3600)  # the E6 and the municipal roads of Selsverket
SEL_600 = (8600, 5800)  # SEL for a 600 px panel, inside the data's box
PARK_WEST_EDGE = (12000, 9000)  # the west edge of Rondane national park, above Mysusæter
SELSVERKET_UNITS = (8000, 3800)
SELSVERKET_CASING = (7300, 3300)
DORAALSETER_WIDE = (23900, 24800)  # Dørålseter, Nedre Dørålseter and Ellandkollbua
DORAALSETER = (23130, 24400)
DORAALSETER_4000 = (23200, 24400)


EXAMPLES = [
    DocExample("1-core", "Land cover with the default symbolizer (Rondane, N50 Kartdata)", ["Landcover"],
               [Panel(50000, MYSUSAETER_WIDE, 900, 600)],
               notes=["No fill, stroke or marker is set, so the default values apply: each polygon is drawn with "
                      "the default fill and stroke and the default Dot at its centroid, all at 50 % opacity."]),
    DocExample("2-vector-polygon", "Land cover in Rondane (N50 Kartdata) around Myrtjørna", ["Landcover"],
               [Panel(50000, MYRTJORNA), Panel(8000, MYRTJORNA)]),
    DocExample("3-vector-line", "Roads in Sel by road class, with the E6 through Selsverket (N50 Kartdata)", ["Roads"],
               [Panel(100000, SEL), Panel(5000, SELSVERKET)]),
    DocExample("4-vector-point", "Tourist cabins in Dørålen, Rondane (N50 Kartdata)", ["Huts"],
               [Panel(50000, DORAALSETER_WIDE, 280), Panel(8000, DORAALSETER, 280),
                Panel(4000, DORAALSETER_4000, 340)]),
    DocExample("5-coverage-dem", "Elevation of Rondane with a color map", ["Elevation"],
               [Panel(WHOLE_SD, WHOLE, 900, 600)], context="relief"),
    DocExample("6-coverage-sentinel2", "Sentinel-2 L2A over Rondane (1 September 2024) in natural color", ["sentinel2-l2a"],
               [Panel(WHOLE_SD, WHOLE, 900, 600)], context=False),
    DocExample("7-coverage-ndvi", "NDVI of the same Sentinel-2 scene with a color map", ["sentinel2-l2a"],
               [Panel(WHOLE_SD, WHOLE, 900, 600)], context="relief"),
    DocExample("8-coverage-hillshading", "Elevation of Rondane with hill shading and a color map", ["Elevation"],
               [Panel(WHOLE_SD, WHOLE, 900, 600)], context=False),
    DocExample("9-coverage-hillshading-opacity", "Hill shading of Rondane with an opacity map", ["Elevation"],
               [Panel(WHOLE_SD, WHOLE, 900, 600)], context=False),
    DocExample("10-protected-areas", "Protected areas around Rondane by kind of protection (N50 Kartdata)",
               ["ProtectedAreas"], [Panel(WHOLE_SD, WHOLE, 900, 600)]),
    DocExample("11-rondane-overview", "Overview map of Rondane from several N50 layers and the elevation model",
               ["Elevation", "Landcover", "Rivers", "Roads", "ProtectedAreas", "Municipalities", "Places"],
               [Panel(WHOLE_SD, WHOLE, 900, 600)], context=False),
]


def _req(name, title, requirements, layers, panels, **kw) -> DocExample:
    return DocExample(name, title, layers, panels, subdir="requirements", requirements=requirements, **kw)


REQUIREMENT_EXAMPLES = [
    _req("core-rules", "Rules, nested rules and visibility on the land cover around Myrtjørna",
         ["/req/core/rules", "/req/core/selector", "/req/core/nested", "/req/core/symbolizer", "/req/core/visibility",
          "/req/core/layers", "/req/core/expressions-field-identifiers"],
         ["Landcover"], [Panel(25000, MYRTJORNA, 600, 400)],
         notes=["Open land is not drawn (visibility false); the light grey shapes under it are the context."]),
    _req("core-opacity", "Symbolizer opacity on Rondane national park, fill and wide stroke together",
         ["/req/core/opacity", "/rec/core/opacity-together"], ["ProtectedAreas"],
         [Panel(100000, PARK_WEST_EDGE, 600, 400)]),
    _req("core-z-order", "zOrder: rivers above roads at Mysusæter", ["/req/core/z-order"], ["Roads", "Rivers"],
         [Panel(20000, MYSUSAETER, 600, 400)]),
    _req("core-instances", "Changing one member of the stroke in a nested rule", ["/req/core/instances"], ["Roads"],
         [Panel(100000, SEL_600, 600, 400)]),
    _req("core-parameters", "Dot size computed from the elevation of each spot height", ["/req/core/parameters"],
         ["SpotHeights"], [Panel(100000, RONDSLOTTET, 600, 400)],
         notes=["The size is an arithmetic expression, so this style also needs the \"Parameter Values\" and "
                "\"Arithmetic\" requirements classes."]),
    _req("core-time", "Roads updated in the visualization's time interval (1 January 2020 to 14 November 2026)",
         ["/req/core/time"], ["Roads"], [Panel(50000, OTTA_ROADS, 600, 400)],
         time_interval=(datetime.date(2020, 1, 1), VIEW_DATE)),
    _req("vector-fill-stroke", "Fill and stroke of forest, bogs and lakes at Mysusæter",
         ["/req/vector/fill", "/req/vector/stroke"], ["Landcover"], [Panel(25000, MYSUSAETER, 600, 400)]),
    _req("vector-units", "Stroke widths in metres, pixels and millimetres at two scales", ["/req/vector/units"],
         ["Roads"], [Panel(8000, SELSVERKET_UNITS), Panel(20000, SELSVERKET_UNITS)]),
    _req("vector-marker-dot", "Dot markers on cabins (points), marked paths (line vertices) and lakes (centroids)",
         ["/req/vector/marker", "/req/vector/dot", "/req/vector/graphics"], ["Landcover", "Roads", "Huts"],
         [Panel(30000, RONDVASSBU, 600, 400)]),
    _req("vector-image", "An Image marker on the tourist cabins, colored by service", ["/req/vector/image"], ["Huts"],
         [Panel(WHOLE_SD_600, WHOLE, 600, 400)]),
    _req("vector-text", "Text markers on the peaks above 1900 m", ["/req/vector/text", "/req/vector/fonts"], ["Places"],
         [Panel(100000, RONDSLOTTET, 600, 400)]),
    _req("casing", "Casing and center line of the roads at Selsverket, Sel", ["/req/casing/casing", "/req/casing/center"],
         ["Roads"], [Panel(25000, SELSVERKET_CASING, 600, 400)], manual_json=True),
    _req("dashes", "Dashed paths around Rondvassbu", ["/req/dashes/dash-pattern", "/req/dashes/dash-offset"],
         ["Roads"], [Panel(30000, RONDVASSBU, 600, 400)], manual_json=True),
    _req("hatches", "Hatch fills on the land cover around Myrtjørna", ["/req/hatches/hatch", "/req/hatches/width",
         "/req/hatches/angle", "/req/hatches/distance"], ["Landcover"], [Panel(20000, MYRTJORNA, 600, 400)]),
    _req("stipples-dot-patterns", "Stipple and dot pattern fills on the land cover around Myrtjørna",
         ["/req/stipples/ratio", "/req/dot-patterns/dotpattern", "/req/dot-patterns/distance"], ["Landcover"],
         [Panel(20000, MYRTJORNA, 600, 400)]),
    _req("font-outlines", "Font outlines on peak names over the relief", ["/req/font-outlines/outline",
         "/req/font-outlines/size", "/req/font-outlines/opacity", "/req/font-outlines/color"], ["Elevation", "Places"],
         [Panel(100000, RONDSLOTTET, 600, 400)], context=False),
    _req("labels-priority", "Peak labels placed by priority (elevation), overlapping labels left out",
         ["/req/labels/label", "/req/labels/placement", "/rec/labels/overlap"], ["Places"],
         [Panel(150000, RONDSLOTTET, 600, 400)], manual_json=True),
    _req("labels-spacing", "Road numbers repeated along the roads near Otta", ["/req/labels/placement"], ["Roads"],
         [Panel(50000, OTTA_ROADS, 600, 400)]),
    _req("coverage-opacity-map", "An opacity map on the elevation of Rondane", ["/req/coverage/opacity-map",
         "/rec/coverage/map-interpolation"], ["Elevation"], [Panel(WHOLE_SD_600, WHOLE, 600, 400)], context=False),
    _req("hill-shading-sun", "Hill shading with the sun in the south-east, without a hill-shading color map",
         ["/req/hill-shading/hill-shading", "/req/hill-shading/factor", "/req/hill-shading/sun"], ["Elevation"],
         [Panel(WHOLE_SD_600, WHOLE, 600, 400)], context=False),
]

# What pycartosym 0.6.4 loses in CSS → JSON, for the examples whose JSON is written by hand.
PYCARTOSYM_GAPS = [
    "`center` is written as `centerLine`, the name before the SWG's decision on #120",
    "`dashPattern` lengths with a unit are dropped (only unitless lengths are kept)",
    "`dashOffset` is dropped",
    "a bare identifier in `placement` (e.g. `priority: elevation`) is written as a string, not a property reference",
]


def _pycartosym_view(style):
    """The hand-written JSON as pycartosym 0.6.4 would write it (see PYCARTOSYM_GAPS)."""
    style = copy.deepcopy(style)

    def walk(obj):
        if isinstance(obj, dict):
            placement = obj.get("placement")
            if isinstance(placement, dict):
                for k, v in placement.items():
                    if isinstance(v, dict) and set(v) == {"property"}:
                        placement[k] = v["property"]
            stroke = obj.get("stroke")
            if isinstance(stroke, dict):
                if "center" in stroke:
                    stroke["centerLine"] = stroke.pop("center")
                stroke.pop("dashOffset", None)
                dp = stroke.get("dashPattern")
                if isinstance(dp, list) and any(isinstance(v, dict) for v in dp):
                    del stroke["dashPattern"]
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(style)
    return style


# Keys whose string values are names or keywords, not text literals.
_NAME_KEYS = {"op", "type", "property", "sysId", "color", "tint", "blackTint", "uri", "path", "id", "ext", "$comment",
              "title", "abstract", "description", "keywords", "face", "$ref", "colorMap"}
_KEYWORDS = {"left", "right", "center", "middle", "top", "bottom", "vector", "coverage", "map"}


def unquoted_strings(css: str, style: dict) -> list[str]:
    """Text literals in the JSON that the CSS does not quote: a sign that an identifier became a string."""
    found = []
    layer_names = set(re.findall(r'^\s*"?([\w-]+)"?\s*[\[{]', css, re.M))  # `Roads { ... }` selects dataLayer.id

    def walk(obj, key=None):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, k)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, key)
        elif (isinstance(obj, str) and key not in _NAME_KEYS and obj not in _KEYWORDS and obj not in layer_names
              and not obj.startswith("#")):
            if f"'{obj}'" not in css and f'"{obj}"' not in css:
                found.append(f"{key}: {obj!r}")

    walk(style)
    return found

# A light grey context under the vector examples: hill shading where the grid is fine enough, and lakes.
CONTEXT_STYLE = {"stylingRules": [
    {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Elevation"]},
     # Shadows only: the hill-shading color map is one slate grey, and its opacity map makes slopes facing the
     # sun and flat ground (shade sin 45 degrees = 0.71 and above) transparent.
     "symbolizer": {"singleChannel": {"property": "elevation"},
                    "hillShading": {"factor": 2, "sun": {"azimuth": 315, "elevation": 45},
                                    "colorMap": [[0, [47, 58, 66]], [1, [47, 58, 66]]],
                                    "opacityMap": [[0, 0.4], [0.7, 0.0], [1, 0.0]]}}},
    {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Landcover"]},
     "symbolizer": {"marker": None, "stroke": {"width": 0}, "fill": {"color": [214, 228, 238]}},
     "nestedRules": [{"selector": {"op": "<>", "args": [{"property": "class"}, "lake"]},
                      "symbolizer": {"visibility": False}}]},
]}

_WATER = [214, 228, 238]
_CONTEXT_TINTS = {"forest": [233, 240, 225], "farmland": [246, 243, 228], "urban": [236, 234, 232],
                  "industrial": [236, 234, 232]}


def _context_styles(own: list[str]) -> tuple[dict, dict, dict | None]:
    """The context drawn under an example: pale land cover, relief shadows, then thin rivers.

    Layers the example styles itself are left out (only the lakes stay under its own Landcover), so the
    context never stands in for what the example shows.
    """
    sel = lambda layer: {"op": "=", "args": [{"sysId": "dataLayer.id"}, layer]}  # noqa: E731
    cls = lambda c: {"op": "=", "args": [{"property": "class"}, c]}  # noqa: E731
    water = {"op": "or", "args": [cls("lake"), cls("river")]}
    nested = [{"selector": water, "symbolizer": {"visibility": True, "fill": {"color": _WATER}}}]
    if "Landcover" not in own:
        nested += [{"selector": cls(c), "symbolizer": {"visibility": True, "fill": {"color": rgb}}}
                   for c, rgb in _CONTEXT_TINTS.items()]
    land = {"stylingRules": [{"selector": sel("Landcover"),
                              "symbolizer": {"visibility": False, "marker": None, "stroke": {"width": 0}},
                              "nestedRules": nested}]}
    relief = {"stylingRules": [CONTEXT_STYLE["stylingRules"][0]]}
    rivers = None if "Rivers" in own else {"stylingRules": [{
        "selector": sel("Rivers"),
        "symbolizer": {"marker": None, "stroke": {"color": [160, 192, 216], "width": {"px": 0.6}}},
        "nestedRules": [{"selector": cls("river"),
                         "symbolizer": {"stroke": {"color": [160, 192, 216], "width": {"px": 1.2}}}}]}]}
    return land, relief, rivers

# pycartosym 0.6.4 drops `marker: null`: the CSS is converted with this marker in its place, and then it is set back.
_NULL_MARKER_CSS = "marker: { elements: [ Dot { size: 987.25 } ] }"
_NULL_MARKER_JSON = {"elements": [{"type": "Dot", "size": 987.25}]}


def to_json(css: str) -> tuple[dict, list[str]]:
    """Convert CartoSym-CSS to CartoSym-JSON with pycartosym, putting back what it loses."""
    fixups = []
    marked = re.sub(r"(?<![\w.])marker\s*:\s*null\b", _NULL_MARKER_CSS, css)
    warnings: list[str] = []

    class _Collect(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.WARNING:
                warnings.append(record.getMessage())

    handler = _Collect()
    logging.getLogger().addHandler(handler)
    try:
        style = pycartosym.Converter().cscss_to_csjson(marked)
    finally:
        logging.getLogger().removeHandler(handler)
    fixups += [f"pycartosym warning: {w}" for w in warnings]

    def restore(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "marker" and v == _NULL_MARKER_JSON:
                    obj[k] = None
                    fixups.append("marker: null")
                elif k in ("color", "tint", "blackTint") and isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                    # pycartosym writes hex colors of Fill and Stroke as [r, g, b] but keeps those of Dots and
                    # Fonts as strings, which main's schema does not accept as a color: write them all as arrays.
                    obj[k] = [int(v[i:i + 2], 16) for i in (1, 3, 5)]
                    fixups.append("hex color as [r, g, b]")
                else:
                    restore(v)
        elif isinstance(obj, list):
            for v in obj:
                restore(v)

    restore(style)
    if json.dumps(style).find("987.25") >= 0:
        raise ValueError("a marker: null placeholder was not restored")
    return style, fixups


def detail_box(p: Panel) -> tuple[tuple[float, float, float, float], float | None]:
    """The box and cell size of the finer elevation fetched for panel *p* (tools/fetch_hires.py detail).

    About one cell per screen pixel, at least 2 m; None for panels where the 50 m grid is already that fine.
    The box is the panel's plus two cells (hill-shading neighbours), snapped to the cell size.
    """
    m = p.scale * MM_PER_PX / 1000
    cell = max(2, round(m))
    if cell >= 40:
        return p.bbox, None
    x0, y0, x1, y1 = p.bbox
    snap = lambda v, up: (-(-v // cell) if up else v // cell) * cell  # noqa: E731
    return (snap(x0, False) - 2 * cell, snap(y0, False) - 2 * cell, snap(x1, True) + 2 * cell,
            snap(y1, True) + 2 * cell), cell


def _elevation(p: Panel) -> Grid:
    box, cell = detail_box(p)
    grid = sample_data.detail_elevation(box, cell) if cell is not None else None
    if grid is None:
        if cell is not None:
            print(f"  no detail elevation for 1:{p.scale:.0f} at {p.center} (tools/fetch_hires.py detail): 50 m cells")
        grid = sample_data.crop(sample_data.rondane_50m(), p.bbox)
    return grid


def _layers(names: list[str], where: Panel | tuple[float, float, float, float]) -> list[Layer]:
    """The data of *names* for a panel (finer elevation where fetched) or for a box (the 50 m grids)."""
    bbox = where.bbox if isinstance(where, Panel) else where
    out = []
    for name in names:
        if name == "Elevation":
            grid = _elevation(where) if isinstance(where, Panel) else sample_data.crop(sample_data.rondane_50m(), bbox)
            out.append(Layer("Elevation", type="coverage", grid=grid))
        elif name == "sentinel2-l2a":
            out.append(Layer("sentinel2-l2a", type="coverage", grid=sample_data.crop(sample_data.sentinel2_50m(), bbox)))
        else:
            out.append(n50.layer(name, bbox))
    return out


def _local_images(style: dict, base: Path) -> dict:
    """A copy of the style whose Image elements point at the local files named by their `path`."""
    style = copy.deepcopy(style)

    def walk(obj):
        if isinstance(obj, dict):
            img = obj.get("image")
            if obj.get("type") == "Image" and isinstance(img, dict) and img.get("path"):
                data = (base / img["path"]).read_bytes()
                mime = img.get("type") or ("image/svg+xml" if img["path"].endswith(".svg") else "image/png")
                img["uri"] = f"data:{mime};base64," + base64.b64encode(data).decode()
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(style)
    return style


def _strip(svg: str) -> str:
    return re.sub(r"^<\?xml[^>]*>", "", svg).strip()


def _furniture(p: Panel, x: float, layers: list[str]) -> str:
    """Map furniture drawn over each panel, not part of the style: a neat line, a scale bar and a credit."""
    px_per_m = 1000 / (p.scale * MM_PER_PX)
    length = max((m for m in (50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000) if m * px_per_m <= 0.22 * p.width),
                 default=50)
    bar = length * px_per_m
    label = f"{length // 1000} km" if length >= 1000 else f"{length} m"
    bx, by = x + 12, p.height - 14
    halo = 'stroke="#ffffff" stroke-width="3" stroke-linejoin="round" paint-order="stroke"'
    credit = "© Kartverket" + (" · Copernicus Sentinel 2024" if "sentinel2-l2a" in layers else "")
    return (f'<g font-family="Arial, Helvetica, sans-serif" font-size="10" fill="#2f3a42">'
            f'<rect x="{bx - 4}" y="{by - 18}" width="{bar + 8 + 6 * len(label)}" height="24" fill="#ffffff" '
            f'fill-opacity="0.72" rx="2"/>'
            f'<rect x="{bx}" y="{by - 4}" width="{bar / 2:.1f}" height="4" fill="#2f3a42"/>'
            f'<rect x="{bx + bar / 2:.1f}" y="{by - 4}" width="{bar / 2:.1f}" height="4" fill="#ffffff" '
            f'stroke="#2f3a42" stroke-width="0.8"/>'
            f'<rect x="{bx}" y="{by - 4}" width="{bar:.1f}" height="4" fill="none" stroke="#2f3a42" stroke-width="0.8"/>'
            f'<text x="{bx}" y="{by - 8}">0</text><text x="{bx + bar:.1f}" y="{by - 8}" text-anchor="middle">{label}</text>'
            f'<text x="{x + p.width - 8}" y="{p.height - 8}" text-anchor="end" font-size="9" fill="#55636d" {halo}>'
            f'{credit}</text></g>'
            f'<rect x="{x + 0.5}" y="0.5" width="{p.width - 1}" height="{p.height - 1}" fill="none" '
            f'stroke="#3b4650" stroke-width="1"/>')


def render_example(ex: DocExample, style: dict) -> str:
    system = {"viz.date": VIEW_DATE, "visualization.date": VIEW_DATE,
              "viz.timeInterval.start.date": ex.time_interval[0], "viz.timeInterval.end.date": ex.time_interval[1]}
    gap, label_h = 16, 20 if len(ex.panels) > 1 else 0
    width = sum(p.width for p in ex.panels) + gap * (len(ex.panels) - 1)
    height = max(p.height for p in ex.panels) + label_h
    parts, x = [], 0
    for p in ex.panels:
        bbox = p.bbox
        bg = "#ffffff"
        if ex.context:
            # Pale land cover, relief shadows (smoothed) and thin rivers: not part of the style.
            land, relief, rivers = _context_styles(ex.layers)
            ctx = [] if ex.context == "relief" else [(land, [n50.layer("Landcover", bbox)])]
            ctx.append((relief, [Layer("Elevation", type="coverage", grid=_elevation(p))]))
            if rivers and ex.context != "relief":
                ctx.append((rivers, [n50.layer("Rivers", bbox)]))
            for ctx_style, ctx_layers in ctx:
                opacity = 1.0
                ctx_svg = render(ctx_style, ctx_layers, View(bbox, p.width, p.height, background="none"), DRAFT)
                ctx_svg = ctx_svg.replace("image-rendering:pixelated", "image-rendering:optimizeQuality")
                parts.append(f'<g transform="translate({x},0)" opacity="{opacity}">' + _strip(ctx_svg) + "</g>")
            bg = "none"
        view = View(bbox, p.width, p.height, background=bg, system=system)
        parts.append(f'<g transform="translate({x},0)">' + _strip(render(style, _layers(ex.layers, p), view, DRAFT))
                     + "</g>")
        parts.append(_furniture(p, x, ex.layers))
        if label_h:
            parts.append(f'<text x="{x + p.width / 2}" y="{p.height + 15}" text-anchor="middle" '
                         f'font-family="Arial" font-size="12" fill="#444444">{p.label}</text>')
        x += p.width + gap
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#ffffff"/>{"".join(parts)}</svg>')


def adoc_block(ex: DocExample) -> str:
    scales = [p.label for p in ex.panels]
    where = (f"at {scales[0]}" if len(scales) == 1 else
             "at " + ", ".join(scales[:-1]) + f" and {scales[-1]}, from left to right")
    context = (" The grey shadows of the relief, seen through the 80 % opaque coverage, the scale bar and the credit "
               "are context, not part of the style." if ex.context == "relief" else
               " The pale land cover, water and rivers, the grey shadows of the relief, the scale bar and the credit "
               "are context, not part of the style." if ex.context else "")
    notes = "".join(" " + n for n in ex.notes)
    figure = f"figures/examples/{ex.subdir + '/' if ex.subdir else ''}{ex.name}.png"
    reqs = ("Illustrates " + ", ".join(f"`{r}`" for r in ex.requirements) + ".\n\n") if ex.requirements else ""
    return f"""// Generated by cartosym-draft-check (python -m cartosym_draft.doc_examples); edit the .cscss instead.
[[fig-example-{ex.name}]]
.{ex.title}, {where}
image::{figure}[]

{reqs}Rendered by the draft renderer of cartosym-draft-check.{context}{notes} Map data © Kartverket, CC BY 4.0{"; contains modified Copernicus Sentinel data 2024" if "sentinel2-l2a" in ex.layers else ""}.

[cols="1,1",options="header"]
|===
| CartoSym-CSS | CartoSym-JSON

a|
[source,cscss]
----
include::{ex.name}.cscss[]
----

a|
[source,json]
----
include::{ex.name}.cs.json[]
----
|===
"""


def _schema_errors(style: dict, schema: dict) -> list[str]:
    v = jsonschema.validators.validator_for(schema)(schema)
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:160]}" for e in v.iter_errors(style)]


def kit(ex: DocExample, style_css: str, style: dict, css_dir: Path, out: Path) -> None:
    """Write a render kit for the example: the style in both encodings, the data and one view-N.json per panel."""
    d = out / ex.name
    d.mkdir(parents=True, exist_ok=True)
    (d / "style.cscss").write_text(style_css, encoding="utf-8")
    (d / "style.cs.json").write_text(json.dumps(style, indent=2, ensure_ascii=False), encoding="utf-8")
    for icons in (css_dir / "icons", css_dir.parent / "icons"):
        if icons.exists():
            shutil.copytree(icons, d / "icons", dirs_exist_ok=True)
            shutil.copytree(icons, out / "icons", dirs_exist_ok=True)  # for paths like ../icons/x.png
            break
    from .kit import CRS, PRJ, _ascii_grid, _geojson
    union = (min(p.bbox[0] for p in ex.panels), min(p.bbox[1] for p in ex.panels),
             max(p.bbox[2] for p in ex.panels), max(p.bbox[3] for p in ex.panels))
    for layer in _layers(ex.layers, union):
        if layer.grid is not None:
            for band in layer.grid.bands:
                (d / f"{layer.id}.{band}.asc").write_text(_ascii_grid(layer, band, n50.ORIGIN), encoding="utf-8")
                (d / f"{layer.id}.{band}.prj").write_text(PRJ, encoding="utf-8")
        else:
            fc = _geojson(layer, n50.ORIGIN)
            for f in fc["features"]:
                if isinstance(f["properties"].get("validDate"), datetime.date):
                    f["properties"] = {**f["properties"], "validDate": f["properties"]["validDate"].isoformat()}
            (d / f"{layer.id}.geojson").write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    ox, oy = n50.ORIGIN
    for i, p in enumerate(ex.panels, start=1):
        b = p.bbox
        view = {"crs": CRS, "bbox": [b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy], "width": p.width,
                "height": p.height, "scaleDenominator": round(p.scale, 1), "pixelSize_mm": MM_PER_PX,
                "layers": ex.layers, "background": "white",
                "visualization": {"date": VIEW_DATE.isoformat(),
                                  "timeInterval": {"start": ex.time_interval[0].isoformat(),
                                                   "end": ex.time_interval[1].isoformat()}}}
        (d / f"view-{i}.json").write_text(json.dumps(view, indent=2), encoding="utf-8")


def build(spec: Path, names: list[str] | None = None, extra_schema: Path | None = None,
          kits: Path | None = None) -> int:
    core = spec / "1-core"
    schemas = {"main": json.loads((core / "schemas" / "CartoSym-JSON.schema.json").read_text(encoding="utf-8"))}
    if extra_schema:
        schemas[extra_schema.stem] = json.loads(extra_schema.read_text(encoding="utf-8"))
    import resvg_py

    failures = 0
    for ex in EXAMPLES + REQUIREMENT_EXAMPLES:
        if names and ex.name not in names:
            continue
        ex_dir = core / "examples" / ex.subdir if ex.subdir else core / "examples"
        figures = core / "figures" / "examples" / ex.subdir if ex.subdir else core / "figures" / "examples"
        figures.mkdir(parents=True, exist_ok=True)
        css_path = ex_dir / f"{ex.name}.cscss"
        css = css_path.read_text(encoding="utf-8")
        style, fixups = to_json(css)
        json_path = ex_dir / f"{ex.name}.cs.json"
        problems = []
        if ex.manual_json:
            hand = json.loads(json_path.read_text(encoding="utf-8"))
            if _pycartosym_view(hand) != style:
                problems.append("the hand-written JSON differs from pycartosym's output beyond the known gaps")
            style = hand
            fixups = [f for f in fixups if "stroke.dashPattern: cannot parse" not in f]
        else:
            json_path.write_text(json.dumps(style, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        problems += [f for f in fixups if f.startswith("pycartosym warning")]
        problems += [f"text literal not quoted in the CSS: {u}" for u in unquoted_strings(css, style)]
        results = {k: _schema_errors(style, sch) for k, sch in schemas.items()}
        if all(results.values()):
            problems += [f"schema {k}: {e}" for k, errs in results.items() for e in errs[:3]]
        svg = render_example(ex, _local_images(style, css_path.parent))
        (figures / f"{ex.name}.png").write_bytes(bytes(resvg_py.svg_to_bytes(svg_string=svg, zoom=2)))
        (ex_dir / f"{ex.name}.adoc").write_text(adoc_block(ex), encoding="utf-8")
        if kits:
            kit(ex, css, style, css_path.parent, kits)
        status = ", ".join(f"{k} {'OK' if not errs else str(len(errs)) + ' errors'}" for k, errs in results.items())
        fixed = sorted({f for f in fixups if not f.startswith("pycartosym warning")})
        print(f"{ex.name}: schema {status}" + (f"; fix-ups: {', '.join(fixed)}" if fixed else "")
              + ("; hand-written JSON" if ex.manual_json else ""))
        for pr in problems:
            print("   PROBLEM:", pr)
        failures += bool(problems)
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", type=Path, default=ROOT.parent / "cartographic-symbology")
    ap.add_argument("--extra-schema", type=Path, help="also validate against this schema (e.g. a schema PR's)")
    ap.add_argument("--kits", type=Path, help="write a render kit per example into this directory")
    ap.add_argument("names", nargs="*")
    args = ap.parse_args(argv)
    return build(args.spec, args.names, args.extra_schema, args.kits)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
