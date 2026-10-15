"""Sample renders for requirements that are not judgement calls.

One sample per straightforward visual requirement (or small group of them):
a render of what the requirement says, and a line saying what to check.
They have no alternatives; the gallery cards cover the open questions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import sample_data
from .gallery import COVERAGE_VIEW, DRAFT, VIEW, _by_layer, _example, _feature, _square, _tweak
from .options import Options
from .render import Layer, View


@dataclass
class Panel:
    style: dict
    layers: list[Layer]
    view: View = field(default_factory=lambda: VIEW)
    options: Options = field(default_factory=lambda: DRAFT)
    caption: str = ""
    anchors: bool = False


@dataclass
class Sample:
    key: str
    title: str
    requirements: list[str]
    check: str  # what a reviewer should see
    panels: list[Panel]


def _line(*coords, **props) -> dict:
    return _feature("LineString", [list(c) for c in coords], **props)


def samples() -> list[Sample]:
    dem = sample_data.dem()
    elevation = Layer("Elevation", type="coverage", grid=dem)
    parcels = Layer("Parcels", [
        _feature("Polygon", _square(20, 110, 70), landuse="forest", area=4900),
        _feature("Polygon", _square(110, 110, 70), landuse="forest", area=900),
        _feature("Polygon", _square(200, 110, 70), landuse="lake", area=4900),
        _feature("Polygon", _square(65, 20, 70), landuse="farm", area=4900),
        _feature("Polygon", _square(155, 20, 70), landuse="farm", area=4900, hidden=True),
    ])
    rules = {"stylingRules": [
        {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Parcels"]},
         "symbolizer": {"fill": {"color": "silver"}},
         "nestedRules": [
             {"selector": {"op": "=", "args": [{"property": "landuse"}, "forest"]},
              "symbolizer": {"fill": {"color": "forestGreen"}},
              "nestedRules": [{"selector": {"op": "<", "args": [{"property": "area"}, 2000]},
                               "symbolizer": {"fill": {"color": "lightGreen"}}}]},
             {"selector": {"op": "=", "args": [{"property": "landuse"}, "lake"]},
              "symbolizer": {"fill": {"color": "steelBlue"}, "stroke": {"color": "navy", "width": {"px": 3}}}},
             {"selector": {"op": "=", "args": [{"property": "hidden"}, True]}, "symbolizer": {"visibility": False}},
         ]},
    ]}
    roads = [_line((10, 160), (290, 40), lanes=1), _line((10, 100), (290, 100), lanes=2),
             _line((10, 40), (290, 160), lanes=4)]
    scale_style = _by_layer({"Places": {
        "marker": {"elements": [{"type": "Dot", "stroke": {"width": {"px": 8}, "color": "darkRed"}}]}}})
    scale_style["stylingRules"][0]["nestedRules"] = [
        {"selector": {"op": "<", "args": [{"sysId": "viz.sd"}, 10000]},
         "symbolizer": {"label": {"elements": [{"type": "Text", "text": {"property": "name"}, "position": [{"px": 0}, {"px": 12}],
                                                "font": {"size": 11, "color": "black"}}]}}}]
    places = Layer("Places", [_feature("Point", [70, 100], name="Kongsberg"), _feature("Point", [200, 90], name="Hvittingfoss")])
    pin = {"type": "Dot", "stroke": {"width": {"px": 6}, "color": "black"}}

    return [
        # ---------------------------------------------------------------- core
        Sample("core-rules", "Rules, selectors, nested rules and visibility",
               ["/req/core/rules", "/req/core/selector", "/req/core/nested", "/req/core/symbolizer", "/req/core/visibility",
                "/req/core/layers", "/req/core/expressions-field-identifiers", "/req/core/default-values"],
               "Farm: silver (only the layer rule applies) with the default black 1 px stroke. Large forest: forest green "
               "(nested rule). Small forest: light green (a rule nested twice). Lake: blue with a 3 px navy stroke. "
               "The second farm (hidden = true) is not drawn.",
               [Panel(rules, [parcels])]),
        Sample("core-scale", "Rules depending on the scale",
               ["/req/core/scale", "/req/core/expressions-system-identifiers"],
               "The dots are shown at both scales; a nested rule on viz.sd < 10 000 adds the labels, so they show at 1:5 000 only.",
               [Panel(scale_style, [places], View(bbox=(0, 0, 420, 280), width=300, height=200), caption="1:5 000"),
                Panel(scale_style, [places], View(bbox=(-705, -465, 975, 655), width=300, height=200),
                      caption="1:20 000 (the same places, smaller)")]),
        Sample("core-alter", "Partial updates (alter) and array element updates",
               ["/req/core/instances", "/req/json/partial-update", "/req/json/array-element-update"],
               "Left: a later rule with alter: true changes only the width, so the line stays red. Middle: the same rule "
               "without alter replaces the whole stroke, so the color falls back to the default black. Right: "
               "{index: 1, value: 2} changes only the gap of the dash pattern [16, 8] to [16, 2].",
               [Panel({"stylingRules": [{"symbolizer": {"stroke": {"color": "red", "width": {"px": 3}}}},
                                        {"symbolizer": {"stroke": {"alter": True, "width": {"px": 10}}}}]},
                      [Layer("Roads", [roads[1]])], caption="alter: true"),
                Panel({"stylingRules": [{"symbolizer": {"stroke": {"color": "red", "width": {"px": 3}}}},
                                        {"symbolizer": {"stroke": {"width": {"px": 10}}}}]},
                      [Layer("Roads", [roads[1]])], caption="no alter"),
                Panel({"stylingRules": [{"symbolizer": {"stroke": {"color": "red", "width": {"px": 6}, "dashPattern": [16, 8]}}},
                                        {"symbolizer": {"stroke": {"alter": True, "dashPattern": {"index": 1, "value": 2}}}}]},
                      [Layer("Roads", [roads[1]])], caption="dashPattern element 1 set to 2")]),
        Sample("core-parameters", "Property values from expressions",
               ["/req/core/parameters", "/req/parameter-values/expressions"],
               "Stroke width = lanes × 3 + 1 px: the roads with 1, 2 and 4 lanes are 4, 7 and 13 px wide.",
               [Panel({"stylingRules": [{"symbolizer": {"stroke": {"color": "darkOrange", "width": {"px": {
                   "op": "+", "args": [{"op": "*", "args": [{"property": "lanes"}, 3]}, 1]}}}}}]},
                   [Layer("Roads", roads)])]),
        # -------------------------------------------------------------- vector
        Sample("vector-fill-stroke", "Fill and stroke",
               ["/req/vector/fill", "/req/vector/stroke"],
               "Left: a teal fill at opacity 1 with a 2 px black stroke. Right: the same fill at opacity 0.4 over the "
               "grey band, with a 6 px crimson stroke at opacity 0.6.",
               [Panel(_by_layer({
                   "Band": {"fill": {"color": "gray"}, "stroke": {"width": {"px": 0}}},
                   "A": {"fill": {"color": "teal"}, "stroke": {"color": "black", "width": {"px": 2}}},
                   "B": {"fill": {"color": "teal", "opacity": 0.4}, "stroke": {"color": "crimson", "width": {"px": 6}, "opacity": 0.6}},
               }), [Layer("Band", [_feature("Polygon", [[[0, 80], [300, 80], [300, 120], [0, 120], [0, 80]]])]),
                    Layer("A", [_feature("Polygon", _square(40, 40, 100))]),
                    Layer("B", [_feature("Polygon", _square(170, 40, 100))])])]),
        Sample("vector-units", "Units of measure",
               ["/req/vector/units"],
               "At 2 px per metre: 4 px, 2 mm (7.1 px at 0.28 mm per pixel) and 10 m (20 px).",
               [Panel({"stylingRules": [
                   {"selector": {"op": "=", "args": [{"property": "unit"}, "px"]}, "symbolizer": {"stroke": {"color": "black", "width": {"px": 4}}}},
                   {"selector": {"op": "=", "args": [{"property": "unit"}, "mm"]}, "symbolizer": {"stroke": {"color": "black", "width": {"mm": 2}}}},
                   {"selector": {"op": "=", "args": [{"property": "unit"}, "m"]}, "symbolizer": {"stroke": {"color": "black", "width": {"m": 10}}}}]},
                   [Layer("Lines", [_line((10, 80), (140, 80), unit="px"), _line((10, 50), (140, 50), unit="mm"),
                                    _line((10, 20), (140, 20), unit="m")])],
                   View(bbox=(0, 0, 150, 100), width=300, height=200))]),
        Sample("vector-marker", "Where markers go",
               ["/req/vector/marker"],
               "A dot at the point, at every vertex of the line, and at the centroid of the polygon.",
               [Panel({"stylingRules": [{"symbolizer": {"fill": {"color": "lightSteelBlue"}, "stroke": {"color": "steelBlue"},
                                                        "marker": {"elements": [pin]}}}]},
                      [Layer("Things", [_feature("Point", [40, 150]),
                                        _line((20, 40), (90, 110), (140, 60)),
                                        _feature("Polygon", [[[170, 30], [280, 50], [260, 170], [190, 140], [170, 30]]])])])]),
        Sample("vector-graphics", "Graphic position offset",
               ["/req/vector/graphics", "/req/vector/dot"],
               "The black cross is the point. A red dot (stroke width 12 px, so 12 px across) is drawn 30 px right of "
               "it, and a blue one 20 px above (positive y is up).",
               [Panel({"stylingRules": [{"symbolizer": {"marker": {"elements": [
                   {"type": "Dot", "stroke": {"width": {"px": 12}, "color": "red"}, "position": [{"px": 30}, {"px": 0}]},
                   {"type": "Dot", "stroke": {"width": {"px": 12}, "color": "blue"}, "position": [{"px": 0}, {"px": 20}]}]}}}]},
                   [Layer("POI", [_feature("Point", [150, 100])])], anchors=True)]),
        Sample("vector-text", "Text and fonts",
               ["/req/vector/text", "/req/vector/fonts"],
               "Three texts at the same point (black cross): serif 16 pt bold, sans-serif 12 pt italic in dark red, "
               "monospace 10 pt. Left, centre and right alignment put the cross at the start, middle and end of the text.",
               [Panel({"stylingRules": [{"symbolizer": {"marker": {"elements": [
                   {"type": "Text", "text": "Serif bold", "alignment": ["left", "middle"], "position": [{"px": 0}, {"px": 30}],
                    "font": {"face": "serif", "size": 16, "bold": True}},
                   {"type": "Text", "text": "Sans italic", "font": {"face": "sans-serif", "size": 12, "italic": True, "color": "darkRed"}},
                   {"type": "Text", "text": "Monospace", "alignment": ["right", "middle"], "position": [{"px": 0}, {"px": -30}],
                    "font": {"face": "monospace", "size": 10}}]}}}]},
                   [Layer("POI", [_feature("Point", [150, 100])])], anchors=True)]),
        # ------------------------------------------------------ strokes, fills
        Sample("dash-offset", "Dash offset",
               ["/req/dashes/dash-offset"],
               "Both lines use dashPattern [16, 8]; the lower one has dashOffset 8 px, so its dashes start 8 px later.",
               [Panel({"stylingRules": [
                   {"symbolizer": {"stroke": {"color": "black", "width": {"px": 5}, "dashPattern": [16, 8]}}},
                   {"selector": {"op": "=", "args": [{"property": "offset"}, True]},
                    "symbolizer": {"stroke": {"alter": True, "dashOffset": {"px": 8}}}}]},
                   [Layer("Lines", [_line((20, 130), (280, 130)), _line((20, 70), (280, 70), offset=True)])])]),
        Sample("hatch-width-distance", "Hatch width and distance",
               ["/req/hatches/hatch", "/req/hatches/width", "/req/hatches/distance"],
               "Left: the defaults (1 px lines every 10 px at 45°). Middle: width 3 px. Right: distance 20 px.",
               [Panel(_by_layer({
                   "A": {"fill": {"color": "darkSlateBlue", "hatch": {}}, "stroke": {"color": "darkSlateBlue"}},
                   "B": {"fill": {"color": "darkSlateBlue", "hatch": {"width": {"px": 3}}}, "stroke": {"color": "darkSlateBlue"}},
                   "C": {"fill": {"color": "darkSlateBlue", "hatch": {"distance": {"px": 20}}}, "stroke": {"color": "darkSlateBlue"}},
               }), [Layer("A", [_feature("Polygon", _square(15, 55, 85))]), Layer("B", [_feature("Polygon", _square(108, 55, 85))]),
                    Layer("C", [_feature("Polygon", _square(200, 55, 85))])])]),
        Sample("font-outline-properties", "Font outline size, opacity and color",
               ["/req/font-outlines/size", "/req/font-outlines/opacity", "/req/font-outlines/color"],
               "On the dark band: a 1 px white outline, a 4 px yellow outline, and a 4 px white outline at opacity 0.3.",
               [Panel(_by_layer({
                   "Band": {"fill": {"color": "darkSlateGray"}, "stroke": {"width": {"px": 0}}},
                   **{name: {"marker": {"elements": [{"type": "Text", "text": text, "font": {
                       "size": 18, "bold": True, "color": "black", "outline": outline}}]}}
                      for name, text, outline in [
                          ("L1", "Outline 1 px", {"size": 1, "color": "white"}),
                          ("L2", "Outline 4 px", {"size": 4, "color": "yellow"}),
                          ("L3", "Opacity 0.3", {"size": 4, "color": "white", "opacity": 0.3})]}}),
                   [Layer("Band", [_feature("Polygon", [[[0, 20], [300, 20], [300, 180], [0, 180], [0, 20]]])]),
                    Layer("L1", [_feature("Point", [150, 150])]), Layer("L2", [_feature("Point", [150, 100])]),
                    Layer("L3", [_feature("Point", [150, 50])])])]),
        Sample("dot-pattern-distance", "Dot pattern distance",
               ["/req/dot-patterns/dotpattern", "/req/dot-patterns/distance"],
               "Left: dots every 8 px both ways. Right: horizontal 20 px, vertical 8 px, so rows of widely spaced dots.",
               [Panel(_by_layer({
                   "A": {"fill": {"color": "saddleBrown", "dotpattern": {"distance": {"horizontal": {"px": 8}, "vertical": {"px": 8}}}},
                         "stroke": {"color": "saddleBrown"}},
                   "B": {"fill": {"color": "saddleBrown", "dotpattern": {"distance": {"horizontal": {"px": 20}, "vertical": {"px": 8}}}},
                         "stroke": {"color": "saddleBrown"}},
               }), [Layer("A", [_feature("Polygon", _square(25, 40, 120))]), Layer("B", [_feature("Polygon", _square(155, 40, 120))])])]),
        # ------------------------------------------------------------ coverage
        Sample("coverage-opacity-map", "Coverage opacity map",
               ["/req/coverage/opacity-map", "/req/coverage/single-channel", "/req/coverage/alpha-channel"],
               "Example 5's colors with an opacityMap from 0 at 0 m to 1 at 2000 m, over a striped background: the "
               "stripes show through the lowlands and disappear under the peaks.",
               [Panel({"stylingRules": [
                   {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Stripes"]},
                    "symbolizer": {"fill": {"color": "black", "hatch": {"width": {"px": 3}, "distance": {"px": 14}, "angle": 0}},
                                   "stroke": {"width": {"px": 0}}, "zOrder": 0}},
                   {"selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Elevation"]},
                    "symbolizer": {**_tweak(_example("5-coverage-dem"), opacity=1)["stylingRules"][0]["nestedRules"][0]["symbolizer"],
                                   "opacityMap": [[0, 0], [2000, 1]]}}]},
                   [Layer("Stripes", [_feature("Polygon", [[[0, 0], [15000, 0], [15000, 10000], [0, 10000], [0, 0]]])]), elevation],
                   COVERAGE_VIEW)]),
        # ----------------------------------------------------------- gradients
        Sample("gradient-types", "Gradient types and keys",
               ["/req/gradients/gradient", "/req/gradients/type", "/req/gradients/keys"],
               "Linear, radial, repeating and conic, each from white through orange (at 30 %) to dark red, as their keys say.",
               [Panel({"stylingRules": [{"symbolizer": {"stroke": {"color": "black"}, "fill": {"gradient": {
                   "type": {"property": "type"}, "angle": 90,
                   "keys": [{"color": "white"}, {"color": "orange", "percent": 0.3}, {"color": "darkRed", "percent": 1}]}}}}]},
                   [Layer("Parcels", [_feature("Polygon", _square(10, 105, 85), type="linear"),
                                      _feature("Polygon", _square(105, 105, 85), type="radial"),
                                      _feature("Polygon", _square(10, 10, 85), type="repeating"),
                                      _feature("Polygon", _square(105, 10, 85), type="conic")])],
                   View(bbox=(0, 0, 200, 200), width=200, height=200))]),
    ]


__all__ = ["Panel", "Sample", "samples"]
