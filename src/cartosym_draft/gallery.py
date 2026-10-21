"""Build an HTML page rendering each draft judgement call side by side.

Usage: python -m cartosym_draft.gallery [gallery/index.html]
"""

from __future__ import annotations

import copy
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from . import sample_data
from .kit import export, zip_all
from .nav import NAV_CSS, NAV_SCRIPT, permalink, toc, topbar
from .review import EXTRA_ROWS, ISSUES, MATRIX, SOURCES
from .options import Options
from .render import Layer, View, render

# The draft, except that the default Marker is left out so the cards and samples
# stay readable; the default-marker card shows it.
DRAFT = Options(default_marker="none")

# ------------------------------------------------------------------ scenes


def _feature(geom_type: str, coords, **props) -> dict:
    return {"type": "Feature", "properties": props, "geometry": {"type": geom_type, "coordinates": coords}}


def _square(x0, y0, size):
    return [[[x0, y0], [x0 + size, y0], [x0 + size, y0 + size], [x0, y0 + size], [x0, y0]]]


VIEW = View(bbox=(0, 0, 300, 200), width=300, height=200)

PIN = "data:image/svg+xml," + quote(
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
    '<path d="M12 23 C12 23 3 13 3 8 A9 9 0 0 1 21 8 C21 13 12 23 12 23 Z" fill="#c0392b" stroke="#fff" stroke-width="1.5"/>'
    '<circle cx="12" cy="8" r="3.2" fill="#fff"/></svg>'
)


@dataclass
class Variant:
    label: str
    options: Options
    is_draft: bool = False
    note: str = ""
    style: dict | None = None  # overrides the decision's style


@dataclass
class Decision:
    key: str
    title: str
    requirements: list[str]
    question: str
    style: dict
    layers: list[Layer]
    variants: list[Variant]
    evidence: str = ""
    view: View = field(default_factory=lambda: VIEW)
    anchors: bool = False
    group: str = "Part 1: vector styling"


def _vector_decisions() -> list[Decision]:
    background = Layer("Background", [_feature("Polygon", [[[0, 0], [150, 0], [150, 200], [0, 200], [0, 0]]])])
    return [
        Decision(
            key="opacity",
            title="Symbolizer opacity: whole symbol or each part",
            requirements=["/req/core/opacity"],
            question="With `opacity: 0.5`, is the symbol made translucent as a whole, or are fill and stroke made translucent separately? "
                     "Separately, the stroke and fill overlap shows through.",
            style={"stylingRules": [
                {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Background"]},
                 "symbolizer": {"fill": {"color": [46, 134, 222]}, "stroke": {"width": {"px": 0}}}},
                {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Parcels"]},
                 "symbolizer": {"opacity": 0.5, "fill": {"color": [243, 156, 18]},
                                "stroke": {"color": [110, 44, 0], "width": {"px": 14}}}},
            ]},
            layers=[background, Layer("Parcels", [_feature("Polygon", _square(80, 50, 130))])],
            variants=[
                Variant("Whole symbol (group opacity)", DRAFT, is_draft=True),
                Variant("Fill and stroke separately", DRAFT.with_(opacity="per-element"), note="Where the stroke overlaps the fill, a darker band shows inside the stroke."),
            ],
            evidence="The draft says the opacity applies to the portrayal as a whole, as SVG and CSS group opacity do. Applied to fill and stroke separately, the overlap shows through.",
        ),
        Decision(
            key="casing-order",
            title="Casing beneath or above the stroke",
            requirements=["/req/casing/casing", "/req/casing/center"],
            question="A road with a 14 px yellow stroke, a 22 px red casing at 60 % opacity (so what lies under it shows through) "
                     "and a thin white centre line. Is the casing drawn beneath the stroke (an outline) or on top of it?",
            style={"stylingRules": [{"symbolizer": {"stroke": {
                "color": [247, 220, 111], "width": {"px": 14},
                "casing": {"color": [192, 57, 43], "opacity": 0.6, "width": {"px": 22}},
                "centerLine": {"color": "white", "width": {"px": 2}}}}}]},
            layers=[Layer("Roads", [_feature("LineString", [[20, 40], [150, 160], [280, 60]])])],
            variants=[
                Variant("Casing beneath", DRAFT, is_draft=True,
                        note="The yellow stroke lies on top; the casing shows as red edges."),
                Variant("Casing above", DRAFT.with_(casing="above"),
                        note="The casing lies over the stroke: the yellow shows through only as orange."),
            ],
            evidence="The draft says the casing is drawn beneath the main stroke. libCartoSym models `casing` and `center` as StrokeStyling, like the draft.",
        ),
        Decision(
            key="casing-crossing",
            title="Casing at crossings",
            requirements=["/req/casing/casing"],
            question="Two cased roads crossing. Does each road draw its casing together with its own stroke, "
                     "or are all casings drawn before any stroke, so the crossing merges?",
            style={"stylingRules": [{"symbolizer": {"stroke": {
                "color": [247, 220, 111], "width": {"px": 12},
                "casing": {"color": [77, 77, 77], "width": {"px": 16}}}}}]},
            layers=[Layer("Roads", [
                _feature("LineString", [[20, 40], [150, 160], [280, 60]]),
                _feature("LineString", [[20, 150], [280, 120]]),
            ])],
            variants=[
                Variant("All casings first (draft renderer's choice)", DRAFT,
                        note="The crossing merges, as in most road maps."),
                Variant("Each road with its own casing", DRAFT.with_(casing_pass="with-feature"),
                        note="The second road's casing cuts across the first road."),
            ],
            evidence="The draft does not say. Drawing every casing before any stroke is the usual way to draw road networks "
                     "(QGIS calls this symbol levels); drawing each feature on its own is simpler but breaks crossings.",
        ),
        Decision(
            key="casing-width",
            title="What casing width means",
            requirements=["/req/casing/casing"],
            question="The stroke is 12 px wide and `casing.width` is 3 px. Is 3 px the casing's total width, or how far it extends beyond each side of the stroke?",
            style={"stylingRules": [{"symbolizer": {"stroke": {
                "color": [247, 220, 111], "width": {"px": 12},
                "casing": {"color": [77, 77, 77], "width": {"px": 3}}}}}]},
            layers=[Layer("Roads", [_feature("LineString", [[20, 40], [150, 160], [280, 60]])])],
            variants=[
                Variant("Total width (draft renderer's choice): 3 px, hidden under the stroke", DRAFT),
                Variant("Extra on each side (12 + 2 × 3 px)", DRAFT.with_(casing_width="extra")),
            ],
            evidence="The draft does not say. This rendering is why it matters: with the total-width reading, a casing thinner than the stroke is invisible.",
        ),
        Decision(
            key="font-outline",
            title="Font outline beneath or above the glyphs",
            requirements=["/req/font-outlines/outline", "/req/font-outlines/size"],
            question="Text with a 2 px white outline over a dark background. Is the outline drawn beneath the glyphs (a halo) or on top of them?",
            style={"stylingRules": [
                {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Background"]},
                 "symbolizer": {"fill": {"color": [52, 73, 94]}, "stroke": {"width": {"px": 0}}}},
                {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Places"]},
                 "symbolizer": {"marker": {"elements": [{"type": "Text", "text": "Trondheim", "font": {
                     "face": "Georgia", "size": 22, "bold": True, "color": [27, 38, 49],
                     "outline": {"size": 2, "color": "white"}}}]}}},
            ]},
            layers=[background, Layer("Places", [_feature("Point", [150, 100])])],
            variants=[
                Variant("Outline beneath (halo)", DRAFT, is_draft=True),
                Variant("Outline above", DRAFT.with_(font_outline="above"), note="The outline is drawn over the glyphs and hides their shapes."),
            ],
            evidence="Outlines beneath the glyphs are the convention: SE draws a Halo on the backgrounds of the glyphs, QGIS a text buffer, MapLibre a text-halo.",
        ),
        Decision(
            key="z-order",
            title="Which zOrder is drawn on top",
            requirements=["/req/core/z-order"],
            question="Two overlapping features. Lakes come first in the data but have `zOrder: 2`; Forest has `zOrder: 1`. Is the higher zOrder drawn on top?",
            style={"stylingRules": [
                {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Lakes"]},
                 "symbolizer": {"zOrder": 2, "fill": {"color": [93, 173, 226]}, "stroke": {"color": [31, 97, 141], "width": {"px": 2}}}},
                {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Forest"]},
                 "symbolizer": {"zOrder": 1, "fill": {"color": [88, 214, 141]}, "stroke": {"color": [29, 131, 72], "width": {"px": 2}}}},
            ]},
            layers=[Layer("Lakes", [_feature("Polygon", _square(60, 40, 110))]),
                    Layer("Forest", [_feature("Polygon", _square(130, 60, 110))])],
            variants=[
                Variant("Higher zOrder on top", DRAFT, is_draft=True),
                Variant("Lower zOrder on top", DRAFT.with_(z_order="lower-on-top")),
            ],
            evidence="The draft says portrayals with a higher zOrder are drawn on top. The earlier clause 7 text only said that zOrder modifies the default order, not in which direction.",
        ),
        Decision(
            key="hatch-angle",
            title="Hatch angle direction",
            requirements=["/req/hatches/angle"],
            question="A hatch fill with `angle: 30`. Clockwise or counter-clockwise from horizontal?",
            style={"stylingRules": [{"symbolizer": {"fill": {"color": [125, 60, 152], "hatch": {
                "angle": 30, "width": {"px": 1.5}, "distance": {"px": 9}}},
                "stroke": {"color": [74, 35, 90], "width": {"px": 2}}}}]},
            layers=[Layer("Zones", [_feature("Polygon", _square(70, 25, 150))])],
            variants=[
                Variant("Clockwise (draft table: \"clockwise degree\")", DRAFT, is_draft=True),
                Variant("Counter-clockwise (mathematical convention)", DRAFT.with_(hatch_angle="counter-clockwise")),
            ],
            evidence="The Part 1 Hatch table says \"Hatches orientation clockwise degree\". libCartoSym still uses the older forward/backward/cross hatch model.",
        ),
        Decision(
            key="dash-units",
            title="Units of dashPattern",
            requirements=["/req/dashes/dash-pattern"],
            question="A 6 px wide line with `dashPattern: [4, 2]`. Are the values pixels, or multiples of the stroke width?",
            style={"stylingRules": [{"symbolizer": {"stroke": {
                "color": [192, 57, 43], "width": {"px": 6}, "dashPattern": [4, 2]}}}]},
            layers=[Layer("Boundaries", [_feature("LineString", [[20, 60], [280, 60]]),
                                         _feature("LineString", [[20, 140], [280, 140]])])],
            variants=[
                Variant("Pixels", DRAFT, is_draft=True),
                Variant("Multiples of stroke width", DRAFT.with_(dash_units="stroke-width")),
            ],
            evidence="Jérôme: units are as in Graphical Units of Measure, pixels unless qualified with another unit. The PR "
                     "now says so for dashPattern, as SE does for `stroke-dasharray`; MapLibre's `line-dasharray` is in "
                     "multiples of the line width.",
        ),
        Decision(
            key="image-hotspot",
            title="Default hot spot of an Image",
            requirements=["/req/vector/image"],
            question="A pin icon on a point (black cross = the point's location). Without an explicit `hotSpot`, which part of the image sits on the point?",
            style={"stylingRules": [{"symbolizer": {"marker": {"elements": [
                {"type": "Image", "image": {"uri": PIN}, "width": {"px": 36}, "height": {"px": 36}}]}}}]},
            layers=[Layer("POI", [_feature("Point", [90, 100]), _feature("Point", [210, 100])])],
            variants=[
                Variant("Centre (0.5, 0.5)", DRAFT, is_draft=True),
                Variant("Top left (0, 0)", DRAFT.with_(image_hotspot=(0.0, 0.0))),
                Variant("Bottom centre (0.5, 1)", DRAFT.with_(image_hotspot=(0.5, 1.0))),
            ],
            evidence="Jérôme: the default hot spot is the centre `{ 0.5, 0.5 }`, since centred icons are by far the most "
                     "common case (after first saying top-left). This is what the draft says and what libCartoSym does "
                     "(GraphicalElement.ec). Pin-shaped icons need the bottom centre, so styles would set it explicitly.",
            anchors=True,
        ),
    ]


EXAMPLES = Path(__file__).parent / "examples"
COVERAGE_VIEW = View(bbox=sample_data.BBOX, width=300, height=200)
# Rondane, 45 x 30 km: 900 px wide keeps the same 1:178 571 as COVERAGE_VIEW, within the examples' viz.sd < 200000.
RELIEF_VIEW = View(bbox=(0.0, 0.0, sample_data.rondane_data.COLS * sample_data.rondane_data.CELL,
                         sample_data.rondane_data.ROWS * sample_data.rondane_data.CELL), width=900, height=600)
RAMP = (500, 2000)  # the examples' 0–2500 m color map, stretched to Rondane's elevations


def _example(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.cs.json").read_text(encoding="utf-8"))


def _changed(style: dict, change: str) -> dict:
    """Record in the style's metadata that a gallery card changed the spec example (shown in the kits)."""
    meta = style.setdefault("metadata", {})
    abstract = meta.get("abstract", "")
    marker = "Changed for the cartosym-draft-check gallery:"
    if marker not in abstract:
        abstract = (abstract.rstrip(". ") + ". " if abstract else "") + marker
    else:
        abstract = abstract.rstrip(".") + ";"
    meta["abstract"] = f"{abstract} {change}."
    return style


def _describe(changes: dict, prefix: str = "") -> list[str]:
    out = []
    for key, value in changes.items():
        if isinstance(value, dict):
            out += _describe(value, f"{prefix}{key}.")
        else:
            out.append(f"{prefix}{key} set to {json.dumps(value)}")
    return out


def _tweak(style: dict, *, note: str = "", **changes) -> dict:
    """Copy of a spec example with properties of its innermost symbolizer changed (described by *note*, if given)."""
    out = _changed(copy.deepcopy(style), note or ", ".join(_describe(changes)))
    sym = out["stylingRules"][0]["nestedRules"][0]["symbolizer"]
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(sym.get(key), dict):
            sym[key] = {**sym[key], **value}
        else:
            sym[key] = value
    return out


def _without_hillshading(style: dict) -> dict:
    """Copy of a spec example with the hillShading of its innermost symbolizer removed."""
    out = _changed(copy.deepcopy(style), "hillShading removed")
    out["stylingRules"][0]["nestedRules"][0]["symbolizer"].pop("hillShading", None)
    return out


def _stretch_color_map(style: dict, lo: float, hi: float) -> dict:
    """Copy of a spec example with its innermost colorMap's values moved linearly onto lo..hi."""
    out = copy.deepcopy(style)
    sym = out["stylingRules"][0]["nestedRules"][0]["symbolizer"]
    v0, v1 = sym["colorMap"][0][0], sym["colorMap"][-1][0]
    sym["colorMap"] = [[round(lo + (e[0] - v0) * (hi - lo) / (v1 - v0)), *e[1:]] for e in sym["colorMap"]]
    return _changed(out, f"colorMap stretched from {v0:g}–{v1:g} m to {lo:g}–{hi:g} m, keeping its colors")


def _retarget(style: dict, old: str, new: str) -> dict:
    """Copy of a style whose selectors compare dataLayer.id with *new* instead of *old*."""
    def walk(o):
        if isinstance(o, dict):
            args = o.get("args")
            if o.get("op") == "=" and isinstance(args, list) and args[:2] == [{"sysId": "dataLayer.id"}, old]:
                return {**o, "args": [args[0], new]}
            return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return o
    return _changed(walk(copy.deepcopy(style)), f"applies to the layer {new} instead of {old}")


def _by_layer(rules: dict[str, dict]) -> dict:
    return {"stylingRules": [
        {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, lid]}, "symbolizer": sym}
        for lid, sym in rules.items()]}


def _more_vector_decisions() -> list[Decision]:
    ground = Layer("Ground", [_feature("Polygon", [[[0, 0], [300, 0], [300, 200], [0, 200], [0, 0]]])])
    places = Layer("Places", [
        _feature("Point", [110, 95], name="Lillestrøm", rank=2),
        _feature("Point", [190, 95], name="Strømmen", rank=8),
    ])
    place_text = {"type": "Text", "text": {"property": "name"}, "position": [{"px": 0}, {"px": 12}],
                  "font": {"face": "sans-serif", "size": 13, "bold": True, "color": [27, 38, 49]}}
    road = [[-20, 250], [300, 800], [600, 330], [900, 870], [1200, 200], [1520, 650]]
    return [
        Decision(
            key="default-marker",
            title="The default marker",
            requirements=["/req/core/default-values", "/req/vector/marker", "/req/vector/dot"],
            question="A style that sets only a fill and a stroke, and no marker. Clause 7's defaults say the default Marker is "
                     "a single default Dot (white, 10 px), and markers are drawn at points, line vertices and polygon centroids. "
                     "Does every feature get a white dot?",
            style={"stylingRules": [{"symbolizer": {"fill": {"color": "lightSteelBlue"},
                                                    "stroke": {"color": "steelBlue", "width": {"px": 3}}}}]},
            layers=[Layer("Things", [_feature("Point", [40, 150]),
                                     _feature("LineString", [[20, 40], [90, 110], [140, 60]]),
                                     _feature("Polygon", [[[170, 30], [280, 50], [260, 170], [190, 140], [170, 30]]])])],
            variants=[
                Variant("The default Dot, as the table says", DRAFT.with_(default_marker="dot"), is_draft=True,
                        note="A white 10 px dot at the point, at every line vertex and at the polygon centroid."),
                Variant("No marker", DRAFT, note="What a style that clears the marker should give."),
            ],
            evidence="Jérôme: intended, so that every feature type is visible by default, and a single default Symbolizer "
                     "is intended; a typical base style unsets the marker for lines and polygons, e.g. "
                     "`[dataLayer.featuresGeometryDimensions > 0] { marker: null; }`. `marker: { elements: [] }` is "
                     "equivalent, while `marker: { }` still yields the default Dot; the draft renderer does the same, "
                     "and the PR's NOTE now says so. Open: the JSON schema rejects all three forms, and the Dot defaults "
                     "(size 10 px, color white) set properties the Dot class does not have: clause 8 and the schema draw "
                     "a Dot with its stroke's width and color. The other cards leave the default marker off, so they "
                     "stay readable."
        ),
        Decision(
            key="dots",
            title="What a stipple or dot-pattern dot looks like",
            requirements=["/req/stipples/ratio", "/req/dot-patterns/dotpattern", "/req/dot-patterns/distance"],
            question="A stipple fill (`ratio: 0.15`, left) and a dot pattern (`distance: 14 px`, right), both with a dark green fill color. "
                     "Neither the requirements nor the model say how big a dot is or which color it has (#84).",
            style=_by_layer({
                "Ground": {"fill": {"color": [223, 230, 211]}, "stroke": {"width": {"px": 0}}},
                "Stipple": {"fill": {"color": [30, 86, 49], "stipple": {"ratio": 0.15}},
                            "stroke": {"color": [30, 86, 49], "width": {"px": 1.5}}},
                "Dots": {"fill": {"color": [30, 86, 49],
                                  "dotpattern": {"distance": {"horizontal": {"px": 14}, "vertical": {"px": 14}}}},
                         "stroke": {"color": [30, 86, 49], "width": {"px": 1.5}}},
            }),
            layers=[ground, Layer("Stipple", [_feature("Polygon", _square(20, 40, 120))]),
                    Layer("Dots", [_feature("Polygon", _square(160, 40, 120))])],
            variants=[
                Variant("Small dots in the fill color (draft renderer's choice)", DRAFT),
                Variant("Dot class defaults (white, 10 px)", DRAFT.with_(dots="dot-defaults")),
            ],
            evidence="The draft leaves this open (#84). "
                     "#84 asks whether the Dot class defaults apply. Rendered, white 10 px dots read as a different symbol, "
                     "and the fill color no longer shows.",
        ),
        Decision(
            key="label-priority",
            title="Which label priority wins",
            requirements=["/req/labels/label", "/req/labels/placement"],
            question="Two nearby places whose labels overlap. Lillestrøm has `priority: 2`, Strømmen `priority: 8`. "
                     "Only one label fits. Which one is kept?",
            style=_by_layer({
                "Places": {"marker": {"elements": [{"type": "Dot", "stroke": {"width": {"px": 6}, "color": [27, 38, 49]}}]},
                           "label": {"elements": [place_text], "placement": {"priority": {"property": "rank"}}}},
            }),
            layers=[places],
            variants=[
                Variant("Higher value wins", DRAFT, is_draft=True, note="Strømmen (priority 8) is kept."),
                Variant("Lower value wins (1 = most important)", DRAFT.with_(label_priority="lower-wins"), note="Lillestrøm (priority 2) is kept."),
            ],
            evidence="The draft proposes that a higher value wins; the spec text does not say (#148). "
                     "In QGIS the label with the higher priority wins; MapLibre's symbol-sort-key places lower values first. "
                     "Both conventions are common, so the spec should state it.",
        ),
        Decision(
            key="label-spacing",
            title="Units of label minSpacing",
            requirements=["/req/labels/placement"],
            question="A road labelled with `minSpacing: 60` at 5 m per pixel. Is 60 in pixels or in metres?",
            style=_by_layer({
                "Roads": {"stroke": {"color": [230, 126, 34], "width": {"px": 5},
                                     "casing": {"color": [126, 60, 10], "width": {"px": 7}}},
                          "label": {"elements": [{"type": "Text", "text": "E6",
                                                  "font": {"face": "sans-serif", "size": 10, "bold": True,
                                                           "color": [27, 38, 49],
                                                           "outline": {"size": 2, "color": "white"}}}],
                                    "placement": {"minSpacing": 60}}},
            }),
            layers=[Layer("Roads", [_feature("LineString", road)])],
            view=View(bbox=(0, 0, 1500, 1000), width=300, height=200),
            variants=[
                Variant("Pixels", DRAFT, is_draft=True, note="At least 60 px between repeated labels."),
                Variant("Metres (map units)", DRAFT.with_(label_spacing_units="m"), note="60 m is 12 px here, so labels repeat as closely as they fit."),
            ],
            evidence="Jérôme: units are as in Graphical Units of Measure, pixels unless qualified with another unit. The PR "
                     "now says so for minSpacing and maxSpacing; a style that wants metres qualifies the value.",
        ),
        Decision(
            key="label-pass",
            title="Labels on top of everything",
            requirements=["/req/labels/label"],
            question="A labelled harbour point, and a pier polygon drawn after it (higher zOrder). "
                     "Is the label drawn in a separate pass on top, or with its own feature?",
            style=_by_layer({
                "Harbours": {"zOrder": 1,
                             "marker": {"elements": [{"type": "Dot", "stroke": {"width": {"px": 8}, "color": [21, 67, 96]}}]},
                             "label": {"elements": [{"type": "Text", "text": "Harbour",
                                                     "font": {"face": "sans-serif", "size": 16, "bold": True,
                                                              "color": [21, 67, 96]},
                                                     "position": [{"px": 0}, {"px": 16}]}]}},
                "Piers": {"zOrder": 2, "fill": {"color": [166, 172, 175]},
                          "stroke": {"color": [86, 101, 115], "width": {"px": 1.5}}},
            }),
            layers=[Layer("Harbours", [_feature("Point", [110, 120])]),
                    Layer("Piers", [_feature("Polygon", [[[130, 60], [250, 60], [250, 160], [130, 160], [130, 60]]])])],
            variants=[
                Variant("Separate pass on top", DRAFT, is_draft=True),
                Variant("With its own feature", DRAFT.with_(label_pass="with-feature"), note="The pier, drawn later, covers part of the label."),
            ],
            evidence="The draft requires the separate pass. Drawn with the feature, a later feature can cover the label, as on the right.",
        ),
    ]


def _coverage_decisions() -> list[Decision]:
    s2, rondane = sample_data.sentinel2(), sample_data.rondane()
    relief = [Layer("Elevation", type="coverage", grid=rondane)]
    pyramid_layer = [Layer("Elevation", type="coverage", grid=sample_data.pyramids())]
    sentinel = [Layer("sentinel2-l2a", type="coverage", grid=s2)]
    ex5, ex8, ex9 = (_example("5-coverage-dem"), _example("8-coverage-hillshading"),
                     _example("9-coverage-hillshading-opacity"))
    ex6 = _example("6-coverage-sentinel2")
    # Rondane spans about 290 to 2160 m: the elevation cards stretch the examples' color map (0 to 2500 m)
    # to RAMP, keeping its colors, so the whole ramp shows and the valley floors and summits fall outside it.
    ex8_rondane = _stretch_color_map(ex8, *RAMP)
    ex5_rondane = _stretch_color_map(ex5, *RAMP)
    ex6_unscaled = _tweak(ex6, note="colorChannels set back to the original example's unscaled B04 B03 B02",
                          colorChannels=[{"property": "B04"}, {"property": "B03"}, {"property": "B02"}])
    # Example 9 is an overlay: draw it over example 5's elevation colors on a second layer, "Terrain".
    terrain = Layer("Terrain", type="coverage", grid=rondane)
    base = _retarget(ex5_rondane, "Elevation", "Terrain")

    def on_terrain(overlay: dict) -> dict:
        return _changed({"metadata": copy.deepcopy(overlay.get("metadata", {})),
                         "stylingRules": base["stylingRules"] + overlay["stylingRules"]},
                        f"drawn over example 5's colors (colorMap stretched to {RAMP[0]}–{RAMP[1]} m) on a second "
                        "layer named Terrain")

    def factor_variants(example: dict, wrap, notes: dict, plain: tuple[str, dict, str]) -> list[Variant]:
        def factor(f: int) -> dict:
            return wrap(_tweak(example, hillShading={"factor": f}))
        return [
            Variant("factor: 56, as vertical exaggeration (as in Jérôme's renderer)", DRAFT, is_draft=True, note=notes[56]),
            Variant("factor: 1", DRAFT, style=factor(1), note=notes[1]),
            Variant("factor: 8", DRAFT, style=factor(8), note=notes[8]),
            Variant("factor: 32", DRAFT, style=factor(32), note=notes[32]),
            Variant(plain[0], DRAFT, style=plain[1], note=plain[2]),
            Variant("factor: 56 as darkening × factor (the earlier draft text)", DRAFT.with_(hillshade_factor="intensity"),
                    note="99 % of the cells are at or near the darkest shade."),
        ]
    common = dict(view=COVERAGE_VIEW, group="Part 1: coverage styling (the spec's examples 5–9)")
    on_relief = {**common, "view": RELIEF_VIEW}
    return [
        Decision(
            key="color-map",
            title="Example 5: colorMap between and beyond entries",
            requirements=["/req/coverage/color-map", "/req/coverage/opacity-map"],
            question="Example 5's color map, stretched from 0–2500 m to Rondane's 500–2000 m (same colors). Between "
                     "entries, are colors interpolated or stepped? Below 500 m (the valley floors) and above 2000 m (the "
                     "summits), is the first or last color used, or nothing?",
            style=ex5_rondane, layers=relief,
            variants=[
                Variant("Interpolate, clamp outside", DRAFT, is_draft=True),
                Variant("Step between entries", DRAFT.with_(map_mode="step")),
                Variant("Transparent outside the map", DRAFT.with_(map_outside="transparent"),
                        note="The valley floors below 500 m are left out. So are the summits above 2000 m, but next to the "
                             "map's near-white last color they hardly show."),
            ],
            evidence="The draft proposes interpolation and clamping (#149). SE 1.1 makes the choice "
                     "explicit with Interpolate and Categorize functions (its own DEM example uses Categorize); GeoServer's ColorMap defaults to an "
                     "interpolated ramp.",
            **on_relief,
        ),
        Decision(
            key="gamma",
            title="Direction of coverage gamma",
            requirements=["/req/coverage/gamma"],
            question="Example 5 with `gamma: 2` (its color map stretched to Rondane's 500–2000 m). "
                     "Does a gamma above 1 darken or brighten?",
            style=_tweak(ex5_rondane, gamma=2), layers=relief,
            variants=[
                Variant("c ^ gamma: darkens", DRAFT, is_draft=True),
                Variant("c ^ (1 / gamma): brightens, as SE", DRAFT.with_(gamma="inverse")),
            ],
            evidence="SE 1.1 GammaValue brightens for values above 1. The draft's exponent does the opposite. gamma is also "
                     "absent from the coverage UML, tables and schema (#86), so removing it is an option.",
            **on_relief,
        ),
        Decision(
            key="color-channels",
            title="Example 6: scaling colorChannels",
            requirements=["/req/coverage/color-channels", "/req/coverage/alpha-channel"],
            question="Example 6 set `colorChannels: B04 B03 B02`, Sentinel-2 digital numbers (reflectance × 10 000), "
                     "while the schema types colorChannels as 0..1. The PR now scales the bands in the style: "
                     "`colorChannels.r: B04 / 2500` and so on. Here on a real Sentinel-2 L2A scene of Rondane "
                     "(2 August 2024).",
            style=ex6, layers=sentinel,
            variants=[
                Variant("Scaled in the style, ÷ 2500", DRAFT, is_draft=True,
                        note="True color: grey rock and lichen above the tree line, green valleys and forest. The white "
                             "patches are clouds the example's SCL rules hide (alphaChannel 0 or 0.5)."),
                Variant("The original example: unscaled bands", DRAFT, style=ex6_unscaled,
                        note="Band values in the hundreds and thousands clamp to 1, so every cell is drawn white. The faint "
                             "shapes are the clouds, which the SCL rules make transparent or half transparent."),
            ],
            evidence="Jérôme: colorChannels is 0..1 and the example assumed pre-scaled bands; one of his working examples "
                     "divides each band by 2500. The PR now states the 0..1 range and scales example 6 that way. Still to "
                     "raise: the defaults table gives colorChannels as fields[0], fields[1], fields[2], unscaled (#150).",
            **on_relief,
        ),
        Decision(
            key="ndvi-division",
            title="Example 7: NDVI with integer bands",
            requirements=["/req/arithmetic/div", "/req/coverage/single-channel", "/req/coverage/color-map"],
            question="Example 7 computes `singleChannel: (B08 - B04)/(B08 + B04)`. Sentinel-2 L2A bands are integers; "
                     "here a real scene of Rondane (2 August 2024). Is `/` a real division?",
            style=_example("7-coverage-ndvi"), layers=sentinel,
            variants=[
                Variant("Real quotient", DRAFT, is_draft=True,
                        note="Green: forest and vegetated valleys. Brown: bare rock above the tree line. White: clouds "
                             "hidden by the SCL rules."),
                Variant("Integer quotient for two integers (libCartoSym)",
                        DRAFT.with_(division="integer-if-both-integers"),
                        note="Every cell evaluates to 0, so the whole scene gets the color for NDVI 0.0."),
            ],
            evidence="Jérôme confirmed: `/` is real-valued division and `div` is integer division, as in CQL2 arithmetic "
                     "expressions. libCartoSym's cs-canif (0.0.1 and main) evaluates (3000 - 1000) / (3000 + 1000) to 0, "
                     "and to 0.5 only when an operand is real; with integer division every NDVI value truncates to 0, so "
                     "the example's color map collapses to one color. Cloud cells are hidden by the example's SCL rules "
                     "(alphaChannel 0 and 0.5).",
            **on_relief,
        ),
        Decision(
            key="hillshade-factor",
            title="Example 8: what hillShading factor means",
            requirements=["/req/hill-shading/hill-shading", "/req/hill-shading/factor"],
            question="Example 8 shades the DEM color map with `factor: 56`, sun at azimuth 45°, elevation 60°. "
                     "Here on Rondane at 150 m cells, with the color map stretched from 0–2500 m to Rondane's 500–2000 m "
                     "(same colors), and the factors of Jérôme's renders (1, 8, 32). "
                     "Over what distance is the slope measured?",
            style=ex8_rondane, layers=relief,
            variants=factor_variants(ex8_rondane, lambda s: s, {
                56: "47 % of the cells are in full or near-full shade (below 0.05): the relief is saturated.",
                1: "The terrain as it is: no cell darker than 0.24.",
                8: "Strong relief: 12 % of the cells are in full or near-full shade.",
                32: "41 % of the cells are in full or near-full shade."},
                ("For reference: no hill shading", _without_hillshading(ex8_rondane), "The stretched color map alone.")),
            evidence="Jérôme: factor multiplies the horizontal components of the terrain normal before normalization, so "
                     "factor 1 is the plain dot product of the sun direction and the normal. The PR now says so, and the "
                     "draft renderer uses the same formula. His renders of the Tibetan Plateau, with pixels of several km, "
                     "show faint relief at 1, clear relief at 8 and strong relief at 32 and 64. On Rondane at 150 m cells "
                     "the slopes per cell are steeper than at his pixel size, so the same factor gives stronger relief: "
                     "1 already shows it clearly, 8 is strong, and the example's 56 saturates it. Jérôme: the "
                     "normal is computed between the samples of the DEM at the resolution being rendered, over the "
                     "horizontal distance between them, in the same units as the heights, so the factor that suits a "
                     "style depends on that resolution; and without a hillShading colorMap the cell's color is multiplied "
                     "by the shade, as in a typical shader. The draft renderer does both, and the PR now says so.",
            **on_relief,
        ),
        Decision(
            key="hillshade-overlay",
            title="Example 9: shading intensity mapped to color and opacity",
            requirements=["/req/hill-shading/factor", "/req/hill-shading/color-map", "/req/hill-shading/opacity-map"],
            question="Example 9 maps the shade (0..1) to black–white and to opacity 0.75–0, for use as an overlay. "
                     "Here it is drawn over example 5's elevation colors (a second layer, `Terrain`), stretched from "
                     "0–2500 m to Rondane's 500–2000 m. "
                     "With `factor: 56`, how much of the terrain does it darken?",
            style=on_terrain(ex9), layers=[terrain] + relief,
            variants=factor_variants(ex9, on_terrain, {
                56: "The overlay darkens 84 % of the cells: only a shade below 0.55 shows.",
                1: "Only the steepest slopes facing away from the sun (2 % of the cells) are darkened.",
                8: "The overlay darkens 48 % of the cells.",
                32: "The overlay darkens 76 % of the cells."},
                ("For reference: no overlay", base, "The stretched color map alone.")),
            evidence="Jérôme: the shade is the dot product of the sun direction and the terrain normal, from 0 (the sun at "
                     "90° from the normal, full shade) to 1 (no shade), and is the key for the hillShading colorMap and "
                     "opacityMap. His example uses a grayscale colorMap with an opacityMap that is more opaque in the shade, "
                     "so imagery shows through on flat ground, as example 9 does. The PR now states this. How much is "
                     "darkened depends on the factor and the distance the normal is computed over (see example 8).",
            **on_relief,
        ),
        Decision(
            key="sun-azimuth",
            title="Direction of the sun azimuth",
            requirements=["/req/hill-shading/sun"],
            question="Three pyramids, shaded with example 8's style, the sun at azimuth 315°, elevation 45°, `factor: 1`, in plain grey. "
                     "Is 315° north-west (compass bearing) or south-east (counter-clockwise from east)?",
            style=_tweak(ex8, hillShading={"factor": 1, "sun": {"azimuth": 315, "elevation": 45},
                                           "colorMap": [[0, "black"], [1, "white"]]}), layers=pyramid_layer,
            variants=[
                Variant("Clockwise from north, a compass bearing", DRAFT, is_draft=True,
                        note="Light from the north-west: slopes facing the top left are bright."),
                Variant("Counter-clockwise from east", DRAFT.with_(hillshade_azimuth="counter-clockwise-from-east"),
                        note="Light from the south-east: slopes facing the bottom right are bright."),
            ],
            evidence="Jérôme: directions on the ground, such as the sun azimuth, are compass bearings, clockwise from "
                     "north. Angles drawn on the map, such as a gradient's, start at 0 pointing right and turn "
                     "counter-clockwise. The PR now says so for the azimuth. Both examples use 45°, which is north-east as a bearing. GDAL and most GIS software use "
                     "compass bearings too.",
            **common,
        ),
    ]


def _gradient_decisions() -> list[Decision]:
    keys = [{"color": [26, 42, 108]}, {"color": [178, 31, 31], "percent": 0.5}, {"color": [253, 187, 45], "percent": 1}]
    common = dict(group="Part 2: gradient fills")
    return [
        Decision(
            key="gradient-angle",
            title="Gradient angle convention",
            requirements=["/req/gradients/angle", "/req/gradients/keys"],
            question="A linear gradient with `angle: 120`, from navy through red to gold. Where does 0° point, and which way "
                     "does the angle turn?",
            style={"stylingRules": [{"symbolizer": {
                "fill": {"gradient": {"type": "linear", "angle": 120, "keys": keys}},
                "stroke": {"color": [51, 51, 51], "width": {"px": 1}}}}]},
            layers=[Layer("Zones", [_feature("Polygon", [[[40, 30], [260, 30], [260, 170], [40, 170], [40, 30]]])])],
            variants=[
                Variant("Mathematical: 0° right, counter-clockwise", DRAFT, is_draft=True),
                Variant("CSS: 0° up, clockwise", DRAFT.with_(gradient_angle="css")),
            ],
            evidence="Jérôme: angles drawn on the map are in degrees, start at 0 pointing right and turn counter-clockwise. The PR now says "
                     "so for the gradient angle. The Part 1 hatch table, however, says \"clockwise degree\", and the sun "
                     "azimuth is relative to north, so whether this applies to every angle is still to confirm.",
            **common,
        ),
        Decision(
            key="gradient-frame",
            title="Gradient position and size: per feature or per map",
            requirements=["/req/gradients/position", "/req/gradients/size", "/req/gradients/type"],
            question="Three parcels with a radial gradient, `position: [0.5, 0.5]`, `size: 1`. Relative to each feature, "
                     "or to the map?",
            style={"stylingRules": [{"symbolizer": {
                "fill": {"gradient": {"type": "radial", "position": [0.5, 0.5], "size": 1,
                                      "keys": [{"color": [253, 187, 45]}, {"color": [26, 42, 108], "percent": 1}]}},
                "stroke": {"color": [51, 51, 51], "width": {"px": 1}}}}]},
            layers=[Layer("Parcels", [_feature("Polygon", _square(20, 110, 70)),
                                      _feature("Polygon", [[[110, 20], [280, 20], [280, 90], [110, 90], [110, 20]]]),
                                      _feature("Polygon", _square(150, 115, 60))])],
            variants=[
                Variant("Each feature's bounding box (draft renderer's choice)", DRAFT, note="Each parcel has its own centred gradient."),
                Variant("The whole map", DRAFT.with_(gradient_frame="map"), note="One gradient centred on the map; each parcel shows its part of it."),
            ],
            evidence="position and size have no reference frame in Part 2. Per feature, every polygon gets its own centred "
                     "gradient; per map, one gradient runs across all features. Jérôme: units are pixels unless "
                     "qualified, which the PR now says; this card's unqualified 0.5 and 1 are read as fractions of the "
                     "frame, which under the draft needs a percent unit. The `repeating` type also needs a definition "
                     "(repeating what, and how often).",
            **common,
        ),
    ]


def decisions() -> list[Decision]:
    return _vector_decisions() + _more_vector_decisions() + _coverage_decisions() + _gradient_decisions()


# ------------------------------------------------------- expression table

# --------------------------------------------------------------------- page

# Dark tokens apply when the reader picks Dark in the top bar, or picks Auto and the system is dark.
DARK = ("color-scheme: dark; --bg:#16181d; --fg:#e8e6e1; --muted:#a3a9b3; --card:#1f2229; --line:#30343c; --accent:#fbbf24; "
        "--accent-bg:#422006; --badge-bg:#78350f; --badge-fg:#fde68a; --json-k:#d7a6f2; --json-s:#7fd8a9; --json-n:#f0a868; --json-b:#8fb4ff;")

CSS = """
:root { color-scheme: light; --bg:#fbfaf7; --fg:#1f2328; --muted:#5b6370; --card:#fff; --line:#e3e0d8; --accent:#b45309; --accent-bg:#fffbeb; --badge-bg:#fde68a; --badge-fg:#92400e;
  --json-k:#7a3e9d; --json-s:#1a7f5a; --json-n:#b35900; --json-b:#2357b0; }
""" + f""":root[data-theme="dark"] {{ {DARK} }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ {DARK} }} }}
""" + """* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1320px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 26px; margin: 0 0 6px; } h2 { font-size: 19px; margin: 0 0 4px; }
.lead { color: var(--muted); max-width: 760px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 20px; margin: 22px 0; }
.reqs code { font-size: 12.5px; color: var(--muted); margin-right: 8px; }
.question { margin: 10px 0 14px; }
.variants { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
figure { margin: 0; } figure svg { width: 100%; height: auto; border-radius: 6px; border: 1px solid var(--line); display:block; }
figcaption { font-size: 13.5px; margin-top: 6px; }
.badge { display:inline-block; font-size: 11.5px; font-weight: 600; padding: 1px 7px; border-radius: 99px; background: var(--badge-bg); color: var(--badge-fg); margin-left: 6px; }
.evidence { font-size: 13.5px; color: var(--muted); border-top: 1px solid var(--line); margin-top: 14px; padding-top: 10px; }
details { margin-top: 8px; font-size: 13px; } pre { overflow-x: auto; background: var(--bg); padding: 10px; border-radius: 6px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; } th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); }
.table-wrap { overflow-x: auto; }
.req { font-size: 13.5px; margin: 6px 0; } .req ul { margin: 4px 0 8px; padding-left: 20px; }
.draft-text { margin: 6px 0 0; } .draft-text summary { font-size: 13.5px; }
.sources, .kit, .note, .legend { font-size: 13px; color: var(--muted); margin: 6px 0; }
.badge.open { background: var(--bg); color: var(--muted); border: 1px solid var(--line); font-weight: 500; vertical-align: middle; }
.vnote { display: block; font-size: 12.5px; color: var(--muted); }
.matrix td, .matrix th { font-size: 13.5px; vertical-align: top; }
a { color: inherit; text-decoration: underline; text-decoration-color: var(--accent); text-decoration-thickness: 1.5px; text-underline-offset: 2px; }
a:hover { color: var(--accent); }
h2.group { font-size: 21px; margin: 40px 0 0; }
.card-body { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; align-items: start; }
@media (min-width: 1100px) { .card-body { grid-template-columns: minmax(0, 1fr) 380px; } }
.style-pane { min-width: 0; }
.pane-head { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); margin-bottom: 4px; flex-wrap: wrap; }
.pane-head strong { color: var(--fg); margin-right: auto; }
.pane-head button { font: inherit; font-size: 12px; padding: 2px 8px; border-radius: 6px; border: 1px solid var(--line); background: var(--card); color: var(--fg); cursor: pointer; }
.json { max-height: 460px; overflow: auto; font: 12px/1.45 ui-monospace, Consolas, monospace; margin: 0; }
.json .k { color: var(--json-k); } .json .s { color: var(--json-s); } .json .n { color: var(--json-n); } .json .b { color: var(--json-b); }
"""

COPY_SCRIPT = """<script>
document.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-copy]");
  if (!b || !navigator.clipboard) return;
  navigator.clipboard.writeText(document.getElementById(b.dataset.copy).textContent);
  const t = b.textContent; b.textContent = "Copied"; setTimeout(() => (b.textContent = t), 1200);
});
</script>"""


def compact_json(obj) -> str:
    """json.dumps with indent 2, but arrays of plain values (colors, positions) on one line."""
    import re
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    plain = re.compile(r'\[\s*((?:-?[\d.eE+-]+|true|false|null|"[^"\,\[\]{}]*")(?:,\s*(?:-?[\d.eE+-]+|true|false|null|"[^"\,\[\]{}]*"))*)\s*\]')
    return plain.sub(lambda m: "[" + ", ".join(x.strip() for x in m.group(1).split(",")) + "]", text)


def json_html(obj) -> str:
    """Pretty JSON with keys, strings, numbers and literals wrapped for coloring."""
    import re
    text = compact_json(obj)
    token = re.compile(r'("(?:[^"\\]|\\.)*")(\s*:)?|(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)|\b(true|false|null)\b')
    out, pos = [], 0
    for m in token.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        if m.group(1):
            cls = "k" if m.group(2) else "s"
            out.append(f'<span class="{cls}">{html.escape(m.group(1))}</span>{html.escape(m.group(2) or "")}')
        elif m.group(3):
            out.append(f'<span class="n">{m.group(3)}</span>')
        else:
            out.append(f'<span class="b">{m.group(4)}</span>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def style_pane(pane_id: str, style: dict, playground_key: str, title: str = "Style (CartoSym-JSON)") -> str:
    return (f'<aside class="style-pane"><div class="pane-head"><strong>{html.escape(title)}</strong>'
            f'<button type="button" data-copy="{pane_id}">Copy</button>'
            f'<a href="playground.html#{playground_key}">Edit in playground</a></div>'
            f'<pre class="json" id="{pane_id}">{json_html(style)}</pre></aside>')


REQUIREMENTS = json.loads((Path(__file__).parent / "requirements.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((Path(__file__).parent / "CartoSym-JSON.schema.json").read_text(encoding="utf-8"))


def _check_styles(styles: dict[str, dict], key: str) -> list[str]:
    """Validate a card's styles against the PR's CartoSym-JSON schema."""
    import jsonschema

    validator = jsonschema.validators.validator_for(SCHEMA)(SCHEMA)
    problems = []
    for name, style in styles.items():
        for err in validator.iter_errors(style):
            leaf = err
            while leaf.context:
                leaf = max(leaf.context, key=lambda c: len(list(c.absolute_path)))
            path = "/".join(map(str, leaf.absolute_path))
            problems.append(f"{key}/{name} at {path}: {leaf.message[:160]}")
    return problems
PR_FILES = "https://github.com/henrik716/cartographic-symbology/blob/requirements-placeholders/"


def _requirement_text(ids: list[str]) -> str:
    out = []
    for rid in ids:
        r = REQUIREMENTS["requirements"].get(rid)
        if not r:
            out.append(f"<div class='req'><code>{html.escape(rid)}</code> (not found)</div>")
            continue
        url = f"{PR_FILES}{r['file']}#L{r['line']}"
        parts = "".join(f"<li>{_inline_code(p)}</li>" for p in r["parts"])
        out.append(f"<div class='req'><a href='{url}'><code>{html.escape(rid)}</code></a><ul>{parts}</ul></div>")
    return "".join(out)


def _issue_links(escaped: str) -> str:
    """Link #NN / #NNN to the spec's GitHub issues (not ecere/libCartoSym#5 or HTML entities)."""
    return re.sub(r"(?<![\w/&])#(\d{2,3})\b", lambda m: f'<a href="{ISSUES}{m.group(1)}">#{m.group(1)}</a>', escaped)


def _inline_code(text: str) -> str:
    """Escape text, render `code` spans and link issue numbers."""
    pieces = html.escape(text).split("`")
    return _issue_links("".join(f"<code>{p}</code>" if i % 2 else p for i, p in enumerate(pieces)))


def _sources(key: str) -> str:
    items = SOURCES.get(key)
    if not items:
        return ""
    links = " · ".join(f'<a href="{html.escape(u)}">{html.escape(label)}</a>' for label, u in items)
    return f'<p class="sources">Sources: {links}</p>'


def _matrix_rows(decisions_: list[Decision]) -> str:
    rows = []
    for d in decisions_:
        m = MATRIX.get(d.key)
        if not m:
            continue
        rows.append(f'<tr><td><a href="#{d.key}">{html.escape(d.title)}</a></td><td>{_inline_code(m.draft_says)}</td>'
                    f'<td>{_inline_code(m.view)}</td><td>{_inline_code(m.status)}</td><td>{_inline_code(m.ask)}</td></tr>')
    for title, m in EXTRA_ROWS:
        rows.append(f'<tr><td>{_inline_code(title)}</td><td>{_inline_code(m.draft_says)}</td>'
                    f'<td>{_inline_code(m.view)}</td><td>{_inline_code(m.status)}</td><td>{_inline_code(m.ask)}</td></tr>')
    return "".join(rows)


def build(out_dir: Path) -> str:
    cards = []
    group = ""
    invalid: list[str] = []
    all_decisions = decisions()
    contents: list[tuple[str | None, str, bool]] = [("matrix", "Decision matrix", False)]
    for d in all_decisions:
        figs = []
        if d.group != group:
            group = d.group
            group_id = "g-" + re.sub(r"[^a-z0-9]+", "-", group.lower()).strip("-")
            cards.append(f'<h2 class="group" id="{group_id}">{html.escape(group)}</h2>')
            contents.append((None, group, False))
            if group.startswith("Part 1: coverage"):
                cards.append('<p class="note">The cards use real data of Rondane, Norway, 45 × 30 km with 150 m cells: '
                             "elevation (elevation data © Kartverket, CC BY 4.0), with the examples' color map stretched "
                             "from 0–2500 m to 500–2000 m, and a Sentinel-2 L2A scene of 2 August 2024 (contains modified "
                             "Copernicus Sentinel data 2024). Only the pyramids are synthetic (see the README). The styles "
                             "are the spec's examples, unchanged unless the question says otherwise.</p>")
        styles = {"style.cs.json": d.style}
        for i, v in enumerate(d.variants):
            svg = render(v.style or d.style, d.layers, d.view, v.options, anchors=d.anchors)
            badge = '<span class="badge">draft</span>' if v.is_draft else ""
            note = f'<span class="vnote">{html.escape(v.note)}</span>' if v.note else ""
            figs.append(f"<figure>{svg}<figcaption>{html.escape(v.label)}{badge}{note}</figcaption></figure>")
            if v.style:
                styles[f"style-variant-{i + 1}.cs.json"] = v.style
        invalid += _check_styles(styles, d.key)
        links = export(d.key, d.title, styles, d.layers, d.view, out_dir)
        kit = " · ".join(f'<a href="{html.escape(p)}">{html.escape(name)}</a>' for name, p in links)
        is_open = not any(v.is_draft for v in d.variants)
        open_tag = ' <span class="badge open">open in draft</span>' if is_open else ""
        contents.append((d.key, d.title, is_open))
        cards.append(
            f'<section class="card" id="{d.key}"><h2>{html.escape(d.title)}{open_tag}{permalink(d.key)}</h2>'
            f'<details class="draft-text"><summary>What the draft says</summary>{_requirement_text(d.requirements)}</details>'
            f'<p class="question">{_inline_code(d.question)}</p>'
            f'<div class="card-body"><div class="variants">{"".join(figs)}</div>{style_pane("json-" + d.key, d.style, d.key)}</div>'
            f'<p class="evidence">{_inline_code(d.evidence)}</p>{_sources(d.key)}'
            f'<p class="kit">Render it yourself: {kit}<a class="up" href="#matrix">↑ Matrix</a></p></section>'
        )
    if invalid:
        raise SystemExit("Styles that do not validate against the CartoSym-JSON schema:\n  " + "\n  ".join(invalid))
    zip_all(out_dir)
    snap = REQUIREMENTS
    snapshot = (f"Requirement text from branch <code>{html.escape(snap['branch'])}</code> at "
                f"<code>{html.escape(snap['commit'])}</code>"
                + (" with uncommitted TODO(review) notes" if snap["uncommitted_changes"] else "") + ".")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CartoSym Draft Decisions</title>
<style>{CSS}{NAV_CSS}</style></head><body class="has-toc">
{topbar("index.html", [(a, label) for a, label, _ in contents])}
<div class="layout has-toc">{toc(contents)}<main>
<h1>CartoSym 2.0 draft: judgement calls, rendered</h1>
<p class="lead">Where the spec text does not settle how a renderer should behave, the draft requirements in
<a href="https://github.com/opengeospatial/cartographic-symbology/pull/133">PR #133</a> make a choice. Each card renders the same
small map with the draft's choice and the alternatives. Because the draft renderer implements the draft itself, it can show
what each choice looks like, but not whether that choice is the intended one: that is for the SWG to decide. Comparing with an
independent renderer shows whether others read the requirements the same way, so each card links its style, data and view settings
(all in <a href="kit.zip">kit.zip</a>), and the <a href="playground.html">playground</a> lets you edit a style and see the result.</p>
<p class="legend"><strong><a href="requirements.html">All 134 requirements and how each is checked →</a></strong> ·
<strong><a href="playground.html">Playground: edit a style and see it rendered →</a></strong></p>
<p class="legend"><span class="badge">draft</span> the draft's choice. <span class="badge open">open in draft</span> the draft
does not settle the question; the variant labelled "draft renderer's choice" is the proposed resolution. {snapshot}</p>
<section class="card" id="matrix"><h2>Decision matrix{permalink("matrix")}</h2>
<p class="question">Proposed resolutions from the PR author, for discussion at the review.</p>
<div class="table-wrap"><table class="matrix"><thead><tr><th>Question</th><th>Draft says</th><th>Proposed resolution</th>
<th>Status in PR #133</th><th>Question for the SWG</th></tr></thead><tbody>{_matrix_rows(all_decisions)}</tbody></table></div></section>
{''.join(cards)}
</main></div>{COPY_SCRIPT}{NAV_SCRIPT}</body></html>"""


def main(argv: list[str]) -> int:
    out = Path(argv[0] if argv else "gallery/index.html")
    from . import playground
    from .requirements_page import build as build_requirements
    from .samples import samples

    req_page = build_requirements(out.parent)
    playground.write(out.parent, decisions(), samples(), CSS)
    out.write_text(build(out.parent), encoding="utf-8")  # last: it zips all kits, the samples' included
    (out.parent / "requirements.html").write_text(req_page, encoding="utf-8")
    print(f"Wrote {out.resolve()}, requirements.html and the render kits in {(out.parent / 'kit').resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
