"""Renders, CartoSym-JSON and AsciiDoc blocks for the examples in the Part 1 document.

Usage: python -m cartosym_draft.doc_examples [--spec ../cartographic-symbology] [name ...]

For each example below, reads ``1-core/examples/<name>.cscss`` from the spec
repository, converts it to CartoSym-JSON with pycartosym 0.6.5 (with the one
fix-up in PYCARTOSYM_GAPS), validates the JSON against the spec's schema, renders
it with the draft renderer on the Rondane data (Kartverket N50, the elevation
model and a Sentinel-2 scene) and writes:

- ``1-core/examples/<name>.cs.json``: the CartoSym-JSON;
- ``1-core/figures/examples/<name>.jpg``: the render, one panel per scale or per variant (JPEG at quality 88
  without chroma subsampling: a third of the size of a PNG, with no visible difference on these maps);
- ``1-core/examples/<name>.adoc``: the render above a two-column table with the
  CartoSym-CSS and the CartoSym-JSON, for the document to include (the CartoSym-CSS only, for the
  requirement figures).

The gallery maps (GALLERY_EXAMPLES) are not in the document: their style, JSON and render are in this
repository's ``gallery/maps``, with an ``index.html`` that shows them on GitHub Pages.

The requirement figures (REQUIREMENT_EXAMPLES) are vignettes: small panels of one place, each changing one
value of the style (or the view), with pale lakes as the only context. The numbered examples and the gallery
maps are drawn over a context of land cover, relief and rivers
that is not part of the style; the figure caption says so.
"""

from __future__ import annotations

import argparse
import base64
import copy
import datetime
import html
import io
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
class Variant:
    """One panel of a vignette: the example's style with one snippet replaced, or the same style in another view."""
    label: str  # shown under the panel
    replace: tuple[str, str] | None = None  # (snippet of the CSS file, what replaces it in this panel)
    panel: Panel | None = None  # another view than the example's first panel
    time_interval: tuple[datetime.date, datetime.date] | None = None

    @property
    def shows_file(self) -> bool:
        """Whether this panel's style is the one in the .cscss file (printed under the figure)."""
        return self.replace is None or self.replace[0] == self.replace[1]


@dataclass
class DocExample:
    name: str  # file stem in 1-core/examples (or in its subdir)
    title: str  # figure caption
    layers: list[str]
    panels: list[Panel]
    # True: land cover, relief and rivers; "relief": the relief shadows only; "water": pale lakes only; False: none
    context: bool | str = True
    notes: list[str] = field(default_factory=list)
    subdir: str = ""  # "requirements" for the examples placed under requirements, "gallery" for the maps kept aside
    requirements: list[str] = field(default_factory=list)
    time_interval: tuple[datetime.date, datetime.date] = TIME_INTERVAL
    # A vignette: small panels of the same place, each with one value changed (option D on #192).
    variants: list[Variant] = field(default_factory=list)
    varies: str = ""  # what the panels differ in, for the caption

    def views(self) -> list[tuple[Panel, tuple[datetime.date, datetime.date]]]:
        """The panel and time interval of each rendered panel."""
        if not self.variants:
            return [(p, self.time_interval) for p in self.panels]
        return [(v.panel or self.panels[0], v.time_interval or self.time_interval) for v in self.variants]

    def styles_css(self, css: str) -> list[str]:
        """The CSS of each rendered panel."""
        out = []
        for v in self.variants or [Variant("")]:
            if v.replace is None:
                out.append(css)
                continue
            old, new = v.replace
            if old not in css:
                raise ValueError(f"{self.name}: snippet {old!r} is not in the CSS")
            out.append(css.replace(old, new))
        return out


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


def _gallery(name, title, requirements, layers, panels, **kw) -> DocExample:
    return DocExample(name, title, layers, panels, subdir="gallery", requirements=requirements, **kw)


# Maps with context that combine a requirement with the land cover, relief and rivers around it. They were the
# requirement figures until the vignettes below replaced them (Jérôme on #185 and #192: vignettes with a range of
# values and no distractions in the requirement classes; a gallery of fuller maps kept aside). Not included in
# the document; their files are in gallery/maps of this repository (removed from #192 on Nov 20, as Maxime asked).
GALLERY_EXAMPLES = [
    _gallery("core-rules", "Rules, nested rules and visibility on the land cover around Myrtjørna",
         ["/req/core/rules", "/req/core/selector", "/req/core/nested", "/req/core/symbolizer", "/req/core/visibility",
          "/req/core/layers", "/req/core/expressions-field-identifiers"],
         ["Landcover"], [Panel(25000, MYRTJORNA, 600, 400)],
         notes=["Open land is not drawn (visibility false); the light grey shapes under it are the context."]),
    _gallery("core-opacity", "Symbolizer opacity on Rondane national park, fill and wide stroke together",
         ["/req/core/opacity", "/rec/core/opacity-together"], ["ProtectedAreas"],
         [Panel(100000, PARK_WEST_EDGE, 600, 400)]),
    _gallery("core-z-order", "zOrder: rivers above roads at Mysusæter", ["/req/core/z-order"], ["Roads", "Rivers"],
         [Panel(20000, MYSUSAETER, 600, 400)]),
    _gallery("core-instances", "Changing one member of the stroke in a nested rule", ["/req/core/instances"], ["Roads"],
         [Panel(100000, SEL_600, 600, 400)]),
    _gallery("core-parameters", "Dot size computed from the elevation of each spot height", ["/req/core/parameters"],
         ["SpotHeights"], [Panel(100000, RONDSLOTTET, 600, 400)],
         notes=["The size is an arithmetic expression, so this style also needs the \"Parameter Values\" and "
                "\"Arithmetic\" requirements classes."]),
    _gallery("core-time", "Roads updated in the visualization's time interval (1 January 2020 to 14 November 2026)",
         ["/req/core/time"], ["Roads"], [Panel(50000, OTTA_ROADS, 600, 400)],
         time_interval=(datetime.date(2020, 1, 1), VIEW_DATE)),
    _gallery("vector-fill-stroke", "Fill and stroke of forest, bogs and lakes at Mysusæter",
         ["/req/vector/fill", "/req/vector/stroke"], ["Landcover"], [Panel(25000, MYSUSAETER, 600, 400)]),
    _gallery("vector-units", "Stroke widths in metres, pixels and millimetres at two scales", ["/req/vector/units"],
         ["Roads"], [Panel(8000, SELSVERKET_UNITS), Panel(20000, SELSVERKET_UNITS)]),
    _gallery("vector-marker-dot", "Dot markers on cabins (points), marked paths (line vertices) and lakes (centroids)",
         ["/req/vector/marker", "/req/vector/dot", "/req/vector/graphics"], ["Landcover", "Roads", "Huts"],
         [Panel(30000, RONDVASSBU, 600, 400)]),
    _gallery("vector-image", "An Image marker on the tourist cabins, colored by service", ["/req/vector/image"], ["Huts"],
         [Panel(WHOLE_SD_600, WHOLE, 600, 400)]),
    _gallery("vector-text", "Text markers on the peaks above 1900 m", ["/req/vector/text", "/req/vector/fonts"], ["Places"],
         [Panel(100000, RONDSLOTTET, 600, 400)]),
    _gallery("casing", "Casing and center line of the roads at Selsverket, Sel", ["/req/casing/casing", "/req/casing/center"],
         ["Roads"], [Panel(25000, SELSVERKET_CASING, 600, 400)]),
    _gallery("dashes", "Dashed paths around Rondvassbu", ["/req/dashes/dash-pattern", "/req/dashes/dash-offset"],
         ["Roads"], [Panel(30000, RONDVASSBU, 600, 400)]),
    _gallery("hatches", "Hatch fills on the land cover around Myrtjørna", ["/req/hatches/hatch", "/req/hatches/width",
         "/req/hatches/angle", "/req/hatches/distance"], ["Landcover"], [Panel(20000, MYRTJORNA, 600, 400)]),
    _gallery("stipples-dot-patterns", "Stipple and dot pattern fills on the land cover around Myrtjørna",
         ["/req/stipples/ratio", "/req/dot-patterns/dotpattern", "/req/dot-patterns/distance"], ["Landcover"],
         [Panel(20000, MYRTJORNA, 600, 400)]),
    _gallery("font-outlines", "Font outlines on peak names over the relief", ["/req/font-outlines/outline",
         "/req/font-outlines/size", "/req/font-outlines/opacity", "/req/font-outlines/color"], ["Elevation", "Places"],
         [Panel(100000, RONDSLOTTET, 600, 400)], context=False),
    _gallery("labels-priority", "Peak labels placed by priority (elevation), overlapping labels left out",
         ["/req/labels/label", "/req/labels/placement", "/rec/labels/overlap"], ["Places"],
         [Panel(150000, RONDSLOTTET, 600, 400)]),
    _gallery("labels-spacing", "Road numbers repeated along the roads near Otta", ["/req/labels/placement"], ["Roads"],
         [Panel(50000, OTTA_ROADS, 600, 400)]),
    _gallery("coverage-opacity-map", "An opacity map on the elevation of Rondane", ["/req/coverage/opacity-map",
         "/rec/coverage/map-interpolation"], ["Elevation"], [Panel(WHOLE_SD_600, WHOLE, 600, 400)], context=False),
    _gallery("hill-shading-sun", "Hill shading with the sun in the south-east, without a hill-shading color map",
         ["/req/hill-shading/hill-shading", "/req/hill-shading/factor", "/req/hill-shading/sun"], ["Elevation"],
         [Panel(WHOLE_SD_600, WHOLE, 600, 400)], context=False),
]


VW, VH = 300, 200  # the size of a vignette panel
LJOSABELGEN = (16150, 12650)  # five named peaks within 2 x 1.4 km
SMUKSJOSETER = (10079, 12795)  # a cabin clear of the path, a lake centroid and a dozen path vertices


def _vig(name, title, requirements, layers, at: Panel, varies: str, variants: list[Variant], **kw) -> DocExample:
    kw.setdefault("context", "water")
    return DocExample(name, title, layers, [at], subdir="requirements", requirements=requirements,
                      variants=variants, varies=varies, **kw)


def _single(name, title, requirements, layers, at: Panel, **kw) -> DocExample:
    kw.setdefault("context", "water")
    return DocExample(name, title, layers, [at], subdir="requirements", requirements=requirements, **kw)


def _values(snippet: str, values: list[tuple[str, str]]) -> list[Variant]:
    """Variants replacing *snippet* by each (label, replacement); the one equal to *snippet* is the file's style."""
    return [Variant(label, (snippet, new)) for label, new in values]


# The requirement figures: vignettes of small panels, each changing one value (agreed with the Part 1 editor,
# following Jérôme on #185 and #192). The pale lakes under vector vignettes are the only context.
REQUIREMENT_EXAMPLES = [
    _single("core-rules", "Rules, nested rules and visibility on the land cover around Myrtjørna",
            ["/req/core/rules", "/req/core/selector", "/req/core/nested", "/req/core/symbolizer", "/req/core/visibility",
             "/req/core/layers", "/req/core/expressions-field-identifiers"],
            ["Landcover"], Panel(25000, MYRTJORNA, 600, 400), context=False,
            notes=["Open land is not drawn (visibility false)."]),
    _vig("core-opacity", "Symbolizer opacity on Rondane national park, fill and wide stroke together",
         ["/req/core/opacity", "/rec/core/opacity-together"], ["ProtectedAreas"], Panel(200000, PARK_WEST_EDGE, VW, VH),
         "the Symbolizer `opacity`",
         _values("opacity: 0.45;", [("opacity: 1", "opacity: 1;"), ("opacity: 0.75", "opacity: 0.75;"),
                                    ("opacity: 0.45", "opacity: 0.45;"), ("opacity: 0.2", "opacity: 0.2;")])),
    _vig("core-z-order", "zOrder: rivers and roads at Mysusæter", ["/req/core/z-order"], ["Roads", "Rivers"],
         Panel(20000, MYSUSAETER, VW, VH), "the `zOrder` of the rivers (the roads have 1)",
         _values("   zOrder: 2;", [("Rivers zOrder: 0", "   zOrder: 0;"), ("Rivers zOrder: 2", "   zOrder: 2;")])),
    _vig("core-instances", "Changing one member of the stroke in a nested rule", ["/req/core/instances"], ["Roads"],
         Panel(80000, SEL_600, VW, VH), "whether the nested rule that sets `stroke.color` is there",
         _values("   [class = 'county' or class = 'european'] { stroke.color: #d0483a; }\n",
                 [("without the nested rule", ""),
                  ("with it", "   [class = 'county' or class = 'european'] { stroke.color: #d0483a; }\n")])),
    _single("core-parameters", "Dot size computed from the elevation of each spot height", ["/req/core/parameters"],
            ["SpotHeights"], Panel(100000, RONDSLOTTET, 600, 400),
            notes=["The size is an arithmetic expression, so this style also needs the \"Parameter Values\" and "
                   "\"Arithmetic\" requirements classes."]),
    _vig("core-time", "Roads updated in the visualization's time interval near Otta", ["/req/core/time"], ["Roads"],
         Panel(50000, OTTA_ROADS, VW, VH), "the start of the visualization's time interval (it ends on 14 November "
         "2026); the style is the same in all panels",
         [Variant(f"from {y}-01-01", time_interval=(datetime.date(y, 1, 1), VIEW_DATE)) for y in (2022, 2018, 2010)]),
    _vig("vector-fill-stroke", "Fill and stroke of the lakes around Myrtjørna", ["/req/vector/fill", "/req/vector/stroke"],
         ["Landcover"], Panel(20000, MYRTJORNA, VW, VH), "the `fill` and `stroke`",
         _values("fill: { color: #b7d3e6 }; stroke: { color: #3f7fb3; width: 1 px };",
                 [("fill only", "fill: { color: #b7d3e6 }; stroke: { width: 0 };"),
                  ("fill and stroke", "fill: { color: #b7d3e6 }; stroke: { color: #3f7fb3; width: 1 px };"),
                  ("fill opacity 0.4", "fill: { color: #b7d3e6; opacity: 0.4 }; stroke: { color: #3f7fb3; width: 1 px };"),
                  ("stroke only, 2 px", "fill: { opacity: 0 }; stroke: { color: #3f7fb3; width: 2 px };")]),
         context=False),
    _vig("vector-units", "Stroke widths in metres, pixels and millimetres at three scales", ["/req/vector/units"],
         ["Roads"], Panel(10000, SELSVERKET_UNITS, VW, VH), "the scale; the style is the same in all panels",
         [Variant(p.label, panel=p) for p in (Panel(s, SELSVERKET_UNITS, VW, VH) for s in (10000, 25000, 50000))]),
    _vig("vector-marker-dot", "Dot markers on a cabin (point), a marked path (line vertices) and a lake (centroid) at Smuksjøseter",
         ["/req/vector/marker", "/req/vector/dot", "/req/vector/graphics"], ["Landcover", "Roads", "Huts"],
         Panel(15000, SMUKSJOSETER, VW, VH), "the Dots of the marker (the same in all three layers)",
         _values("Dot { size: 7 px, color: white }, Dot { size: 4.5 px, color: #b8322a }",
                 [("one Dot", "Dot { size: 4.5 px, color: #b8322a }"),
                  ("two Dots (an outline)", "Dot { size: 7 px, color: white }, Dot { size: 4.5 px, color: #b8322a }"),
                  ("plus a Dot at 6 -6", "Dot { size: 7 px, color: white }, Dot { size: 4.5 px, color: #b8322a }, "
                                         "Dot { size: 3 px, color: #1f4e79, position: 6 -6 }")]),
         context=False),
    _vig("vector-image", "An Image marker on the tourist cabins in Dørålen (the blue Dot marks the cabin)",
         ["/req/vector/image"], ["Huts"], Panel(10000, DORAALSETER, VW, VH), "the `hotSpot` and `blackTint`",
         _values("hotSpot: 50 pc 100 pc; blackTint: #b8322a;",
                 [("no hotSpot (center)", "blackTint: #b8322a;"),
                  ("hotSpot: 50 pc 100 pc", "hotSpot: 50 pc 100 pc; blackTint: #b8322a;"),
                  ("hotSpot: 0 0", "hotSpot: 0 0; blackTint: #b8322a;"),
                  ("blackTint: #3a7d44", "hotSpot: 50 pc 100 pc; blackTint: #3a7d44;")])),
    _vig("vector-text", "The alignment of Text graphics on the peaks around Ljosåbelgen (the Dot marks the position)",
         ["/req/vector/text", "/req/vector/fonts"], ["Places"], Panel(52000, LJOSABELGEN, VW, VH), "the `alignment`",
         _values(", alignment: center middle",
                 [("left top (default)", ""), ("center middle", ", alignment: center middle"),
                  ("right bottom", ", alignment: right bottom"), ("center bottom", ", alignment: center bottom")])),
    _vig("casing", "Casing and center line of the roads at Selsverket, Sel", ["/req/casing/casing", "/req/casing/center"],
         ["Roads"], Panel(25000, (7900, 3300), VW, VH), "the `casing` and `center` of the stroke",
         _values("; casing: { color: #8c8172; width: 1 px }; center: { color: #d0483a; width: 1 px }",
                 [("no casing", ""), ("casing 1 px", "; casing: { color: #8c8172; width: 1 px }"),
                  ("casing 2.5 px", "; casing: { color: #8c8172; width: 2.5 px }"),
                  ("casing and center", "; casing: { color: #8c8172; width: 1 px }; center: { color: #d0483a; width: 1 px }")])),
    _vig("dashes", "Dash patterns and a dash offset on the paths at Rondvassbu",
         ["/req/dashes/dash-pattern", "/req/dashes/dash-offset"], ["Roads"], Panel(12000, RONDVASSBU, VW, VH),
         "the `dashPattern` and `dashOffset`",
         _values("; dashPattern: [ 10 px, 10 px ]",
                 [("no dashPattern", ""), ("[ 10 px, 10 px ]", "; dashPattern: [ 10 px, 10 px ]"),
                  ("[ 10 px, 10 px ], dashOffset: 10 px", "; dashPattern: [ 10 px, 10 px ]; dashOffset: 10 px"),
                  ("[ 8 px, 3 px, 2 px, 3 px ]", "; dashPattern: [ 8 px, 3 px, 2 px, 3 px ]")])),
    _vig("hatches", "Hatch fills on the forest around Myrtjørna", ["/req/hatches/hatch", "/req/hatches/width",
         "/req/hatches/angle", "/req/hatches/distance"], ["Landcover"], Panel(20000, MYRTJORNA, VW, VH),
         "the `hatch`",
         _values("hatch: { width: 1 px; angle: 45; distance: 6 px }",
                 [("angle: 0", "hatch: { width: 1 px; angle: 0; distance: 6 px }"),
                  ("angle: 45", "hatch: { width: 1 px; angle: 45; distance: 6 px }"),
                  ("angle: 135", "hatch: { width: 1 px; angle: 135; distance: 6 px }"),
                  ("width: 2 px, distance: 12 px", "hatch: { width: 2 px; angle: 45; distance: 12 px }")])),
    _vig("stipples-dot-patterns", "Stipple and dot pattern fills on the forest around Myrtjørna",
         ["/req/stipples/ratio", "/req/dot-patterns/dotpattern", "/req/dot-patterns/distance"], ["Landcover"],
         Panel(20000, MYRTJORNA, VW, VH), "the `stipple` or `dotpattern` of the fill",
         _values("stipple: { ratio: 0.2 }",
                 [("stipple ratio: 0.2", "stipple: { ratio: 0.2 }"), ("stipple ratio: 0.5", "stipple: { ratio: 0.5 }"),
                  ("dotpattern 6 × 6 px", "dotpattern: { distance: { horizontal: 6 px; vertical: 6 px } }"),
                  ("dotpattern 10 × 5 px", "dotpattern: { distance: { horizontal: 10 px; vertical: 5 px } }")])),
    _vig("font-outlines", "Font outlines on peak names over the relief", ["/req/font-outlines/outline",
         "/req/font-outlines/size", "/req/font-outlines/opacity", "/req/font-outlines/color"], ["Elevation", "Places"],
         Panel(100000, RONDSLOTTET, VW, VH), "the `outline` of the font",
         _values(", outline: { size: 2, opacity: 0.85, color: white }",
                 [("no outline", ""), ("size 1, white", ", outline: { size: 1, color: white }"),
                  ("size 2, white, opacity 0.85", ", outline: { size: 2, opacity: 0.85, color: white }"),
                  ("size 3, #f3e7b8, opacity 0.5", ", outline: { size: 3, opacity: 0.5, color: #f3e7b8 }")]),
         context=False),
    _vig("labels-priority", "Peak labels placed by priority, overlapping labels left out",
         ["/req/labels/label", "/req/labels/placement", "/rec/labels/overlap"], ["Places"],
         Panel(250000, RONDSLOTTET, VW, VH), "the `priority` of the label placement",
         _values(",\n               placement: { priority: elevation }",
                 [("no priority", ""), ("priority: elevation", ",\n               placement: { priority: elevation }"),
                  # Part 1 has no unary minus (only `not` is unary), so -elevation would not validate.
                  ("priority: 0 - elevation", ",\n               placement: { priority: 0 - elevation }")])),
    _vig("labels-spacing", "Road numbers repeated along the roads near Otta", ["/req/labels/placement"], ["Roads"],
         Panel(50000, OTTA_ROADS, VW, VH), "the `minSpacing` of the label placement",
         _values("minSpacing: 150", [("minSpacing: 80", "minSpacing: 80"), ("minSpacing: 150", "minSpacing: 150"),
                                     ("minSpacing: 300", "minSpacing: 300")])),
    _vig("coverage-opacity-map", "An opacity map on the elevation of Rondane", ["/req/coverage/opacity-map",
         "/rec/coverage/map-interpolation"], ["Elevation"], Panel(WHOLE_SD_600 * 2, WHOLE, VW, VH), "the `opacityMap`",
         _values("\n   opacityMap: [ 700 0.0, 900 1.0 ];",
                 [("no opacityMap", ""), ("fades out below 900 m", "\n   opacityMap: [ 700 0.0, 900 1.0 ];"),
                  ("fades out below 1500 m", "\n   opacityMap: [ 1300 0.0, 1500 1.0 ];")]),
         context=False),
    _vig("hill-shading-factor", "Hill shading with different factors (sun at the default azimuth 315, elevation 45)",
         ["/req/hill-shading/hill-shading", "/req/hill-shading/factor"], ["Elevation"],
         Panel(150000, RONDSLOTTET, VW, VH), "the `factor`",
         _values("factor: 3", [("factor: 0 (off)", "factor: 0"), ("factor: 0.5", "factor: 0.5"),
                               ("factor: 1", "factor: 1"), ("factor: 3", "factor: 3")]),
         context=False),
    _vig("hill-shading-sun", "Hill shading with the sun from different directions", ["/req/hill-shading/hill-shading",
         "/req/hill-shading/sun"], ["Elevation"], Panel(150000, RONDSLOTTET, VW, VH), "the `azimuth` of the `sun`",
         _values("azimuth: 315", [("azimuth: 315, the default", "azimuth: 315"), ("azimuth: 45", "azimuth: 45"),
                                  ("azimuth: 135", "azimuth: 135"), ("azimuth: 225", "azimuth: 225")]),
         context=False),
]

# What pycartosym 0.6.5 writes differently in CSS → JSON; to_json fixes it and reports the fix-up.
# (0.6.5 fixed the other gaps the figures found: pycartosym #174, #182 to #185.)
PYCARTOSYM_GAPS = [
    "`center` is written as `centerLine`, the name before the SWG's decision on #120 (the schema follows in #188)",
]


def _center_from_center_line(style) -> bool:
    """Rename `centerLine` in each Stroke to `center` (PYCARTOSYM_GAPS); whether any was renamed."""
    renamed = False

    def walk(obj):
        nonlocal renamed
        if isinstance(obj, dict):
            stroke = obj.get("stroke")
            if isinstance(stroke, dict) and "centerLine" in stroke:
                stroke["center"] = stroke.pop("centerLine")
                renamed = True
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(style)
    return renamed


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

def to_json(css: str) -> tuple[dict, list[str]]:
    """Convert CartoSym-CSS to CartoSym-JSON with pycartosym; the second value lists warnings and fix-ups.

    pycartosym 0.6.4 needed more fix-ups here (`marker: null` and hex colors of Dots); 0.6.5 needs only the
    `center` name (PYCARTOSYM_GAPS).
    """
    fixups = []
    warnings: list[str] = []

    class _Collect(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.WARNING:
                warnings.append(record.getMessage())

    handler = _Collect()
    logging.getLogger().addHandler(handler)
    try:
        style = pycartosym.Converter().cscss_to_csjson(css)
    finally:
        logging.getLogger().removeHandler(handler)
    fixups += [f"pycartosym warning: {w}" for w in warnings]
    if _center_from_center_line(style):
        fixups.append("centerLine renamed center (#120)")
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


# The only context under vector vignettes: lakes in a very pale blue, without an outline.
WATER_STYLE = {"stylingRules": [{
    "selector": {"op": "=", "args": [{"sysId": "dataLayer.id"}, "Landcover"]},
    "symbolizer": {"visibility": False, "marker": None, "stroke": {"width": 0}},
    "nestedRules": [{"selector": {"op": "=", "args": [{"property": "class"}, "lake"]},
                     "symbolizer": {"visibility": True, "fill": {"color": [226, 237, 244]}}}]}]}


def render_example(ex: DocExample, styles: list[dict]) -> str:
    """The figure: one panel per view, each with its own style (the same style unless the example is a vignette)."""
    views = ex.views()
    if len(styles) == 1:
        styles = styles * len(views)  # one style for all panels (the examples at several scales)
    if len(styles) != len(views):
        raise ValueError(f"{ex.name}: {len(styles)} styles for {len(views)} panels")
    vignette = bool(ex.variants)
    gap = 12 if vignette else 16
    label_h = 22 if vignette else (20 if len(views) > 1 else 0)
    width = sum(p.width for p, _ in views) + gap * (len(views) - 1)
    height = max(p.height for p, _ in views) + label_h
    marks_file = vignette and any(not v.shows_file for v in ex.variants)
    parts, x = [], 0
    for i, ((p, interval), style) in enumerate(zip(views, styles)):
        system = {"viz.date": VIEW_DATE, "visualization.date": VIEW_DATE,
                  "viz.timeInterval.start.date": interval[0], "viz.timeInterval.end.date": interval[1]}
        bbox = p.bbox
        bg = "#ffffff"
        if ex.context == "water":
            water = render(WATER_STYLE, [n50.layer("Landcover", bbox)],
                           View(bbox, p.width, p.height, background="#ffffff"), DRAFT)
            parts.append(f'<g transform="translate({x},0)">' + _strip(water) + "</g>")
            bg = "none"
        elif ex.context:
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
        if vignette:
            # A neat line only; the value below. The credit is in the caption.
            v = ex.variants[i]
            bold = marks_file and v.shows_file
            parts.append(f'<rect x="{x + 0.5}" y="0.5" width="{p.width - 1}" height="{p.height - 1}" fill="none" '
                         f'stroke="#3b4650" stroke-width="1"/>')
            parts.append(f'<text x="{x + p.width / 2}" y="{p.height + 16}" text-anchor="middle" '
                         f'font-family="Consolas, monospace" font-size="12" fill="#2f3a42"'
                         f'{" font-weight=" + chr(34) + "bold" + chr(34) if bold else ""}>'
                         f'{html.escape(v.label)}{" (style below)" if bold else ""}</text>')
        else:
            parts.append(_furniture(p, x, ex.layers))
            if label_h:
                parts.append(f'<text x="{x + p.width / 2}" y="{p.height + 15}" text-anchor="middle" '
                             f'font-family="Arial" font-size="12" fill="#444444">{p.label}</text>')
        x += p.width + gap
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#ffffff"/>{"".join(parts)}</svg>')


# Examples in Annex C, which shows its styles in CartoSym-CSS only (its other use cases too).
ANNEX_C = {"10-protected-areas", "11-rondane-overview"}


def adoc_block(ex: DocExample) -> str:
    css_only = bool(ex.subdir) or ex.name in ANNEX_C
    scales = list(dict.fromkeys(p.label for p, _ in ex.views()))
    where = (f", at {scales[0]}" if len(scales) == 1 else
             "" if ex.variants else  # the panels are labelled with their scale
             ", at " + ", ".join(scales[:-1]) + f" and {scales[-1]}, from left to right")
    context = (" The pale blue lakes are context, not part of the style." if ex.context == "water" else
               " The grey shadows of the relief, seen through the 80 % opaque coverage, the scale bar and the credit "
               "are context, not part of the style." if ex.context == "relief" else
               " The pale land cover, water and rivers, the grey shadows of the relief, the scale bar and the credit "
               "are context, not part of the style." if ex.context else "")
    vignette = ""
    if ex.variants:
        vignette = f" The panels differ only in {ex.varies}"
        vignette += (("; the CartoSym-CSS below is that of the panel marked in bold." if css_only else
                      "; the CartoSym-CSS and CartoSym-JSON below are those of the panel marked in bold.")
                     if any(not v.shows_file for v in ex.variants) else ".")
    notes = "".join(" " + n for n in ex.notes)
    figure = f"figures/examples/{ex.subdir + '/' if ex.subdir else ''}{ex.name}.jpg"
    reqs = ("Illustrates " + ", ".join(f"`{r}`" for r in ex.requirements) + ".\n\n") if ex.requirements else ""
    anchor = f"fig-example-{ex.name}"
    head = f"""// Generated by cartosym-draft-check (python -m cartosym_draft.doc_examples); edit the .cscss instead.
[[{anchor}]]
.{ex.title}{where}
image::{figure}[]

{reqs}Rendered by the draft renderer of cartosym-draft-check.{vignette}{context}{notes} Map data © Kartverket, CC BY 4.0{"; contains modified Copernicus Sentinel data 2024" if "sentinel2-l2a" in ex.layers else ""}.
"""
    if css_only:
        # The requirement figures and Annex C show the CartoSym-CSS only, without a table (Jérôme, Nov 20).
        return head + f"""
[source,cscss]
----
include::{ex.name}.cscss[]
----
"""
    return head + f"""
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


GALLERY_DIR = ROOT / "gallery" / "maps"


def gallery_page() -> str:
    """gallery/maps/index.html: each gallery map with its CartoSym-CSS and a link to its CartoSym-JSON."""
    items = []
    for ex in GALLERY_EXAMPLES:
        css = (GALLERY_DIR / f"{ex.name}.cscss").read_text(encoding="utf-8")
        scales = list(dict.fromkeys(p.label for p, _ in ex.views()))
        reqs = ", ".join(f"<code>{html.escape(r)}</code>" for r in ex.requirements)
        items.append(f'''<section id="{ex.name}">
<h2>{html.escape(ex.title)}</h2>
<p class="meta">{reqs} · {html.escape(", ".join(scales))} ·
<a href="{ex.name}.cscss">{ex.name}.cscss</a> · <a href="{ex.name}.cs.json">{ex.name}.cs.json</a></p>
<img loading="lazy" src="{ex.name}.jpg" alt="{html.escape(ex.title)}">
<pre>{html.escape(css)}</pre>
</section>''')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CartoSym gallery maps</title>
<style>
:root {{ --paper:#f5f8fa; --ink:#15232e; --muted:#536473; --rule:#d3dde4; --code:#ffffff; }}
@media (prefers-color-scheme: dark) {{ :root {{ --paper:#121a20; --ink:#e3eaef; --muted:#9aabb8; --rule:#2c3a44;
  --code:#1a252d; }} }}
body {{ margin:0 auto; max-width:1100px; padding:24px 16px; background:var(--paper); color:var(--ink);
  font:15px/1.5 "Segoe UI",Arial,sans-serif; }}
a {{ color:inherit; }} .meta {{ color:var(--muted); font-size:13px; }}
section {{ border-top:1px solid var(--rule); padding-top:12px; margin-top:28px; }}
h2 {{ font-size:18px; margin:0 0 4px; }} img {{ max-width:100%; height:auto; display:block; }}
pre {{ background:var(--code); border:1px solid var(--rule); padding:10px; overflow-x:auto; font-size:12.5px; }}
</style></head><body>
<h1>Gallery maps</h1>
<p>Maps on the Rondane data (Kartverket N50, CC BY 4.0) that combine a requirement of OGC CartoSym Part 1 with
land cover, relief and rivers as context; the context is not part of the style. They were the requirement figures of
#192 until the vignettes replaced them, and are not in the document. Rendered by the draft renderer of
cartosym-draft-check (<code>python -m cartosym_draft.doc_examples</code>).</p>
{"".join(items)}
</body></html>
'''


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
    from PIL import Image

    failures = 0
    gallery_built = False
    for ex in EXAMPLES + REQUIREMENT_EXAMPLES + GALLERY_EXAMPLES:
        if names and ex.name not in names and f"{ex.subdir}/{ex.name}" not in names:
            continue
        if ex.subdir == "gallery":
            ex_dir = figures = GALLERY_DIR
            gallery_built = True
        else:
            ex_dir = core / "examples" / ex.subdir if ex.subdir else core / "examples"
            figures = core / "figures" / "examples" / ex.subdir if ex.subdir else core / "figures" / "examples"
        figures.mkdir(parents=True, exist_ok=True)
        css_path = ex_dir / f"{ex.name}.cscss"
        css = css_path.read_text(encoding="utf-8")
        style, fixups = to_json(css)
        json_path = ex_dir / f"{ex.name}.cs.json"
        json_path.write_text(json.dumps(style, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        problems = [f for f in fixups if f.startswith("pycartosym warning")]
        problems += [f"text literal not quoted in the CSS: {u}" for u in unquoted_strings(css, style)]
        results = {k: _schema_errors(style, sch) for k, sch in schemas.items()}
        if all(results.values()):
            problems += [f"schema {k}: {e}" for k, errs in results.items() for e in errs[:3]]
        # Every panel of a vignette has its own style: converted, checked and validated like the file's.
        styles = []
        for i, panel_css in enumerate(ex.styles_css(css), start=1):
            panel_style, panel_fixups = (style, fixups) if panel_css == css else to_json(panel_css)
            if panel_css != css:
                problems += [f"panel {i}: {f}" for f in panel_fixups if f.startswith("pycartosym warning")]
                problems += [f"panel {i}: schema {k}: {e}" for k, sch in schemas.items()
                             for e in _schema_errors(panel_style, sch)[:3]]
            styles.append(_local_images(panel_style, css_path.parent))
        svg = render_example(ex, styles)
        png = bytes(resvg_py.svg_to_bytes(svg_string=svg, zoom=2))
        Image.open(io.BytesIO(png)).convert("RGB").save(figures / f"{ex.name}.jpg", "JPEG", quality=88,
                                                         subsampling=0, optimize=True)
        if ex.subdir != "gallery":
            (ex_dir / f"{ex.name}.adoc").write_text(adoc_block(ex), encoding="utf-8")
        if kits:
            kit(ex, css, style, css_path.parent, kits)
        status = ", ".join(f"{k} {'OK' if not errs else str(len(errs)) + ' errors'}" for k, errs in results.items())
        fixed = sorted({f for f in fixups if not f.startswith("pycartosym warning")})
        where = f"{ex.subdir}/" if ex.subdir else ""
        print(f"{where}{ex.name}: schema {status}" + (f"; fix-ups: {', '.join(fixed)}" if fixed else "")
              + (f"; {len(styles)} panels" if ex.variants else ""))
        for pr in problems:
            print("   PROBLEM:", pr)
        failures += bool(problems)
    if gallery_built:
        (GALLERY_DIR / "index.html").write_text(gallery_page(), encoding="utf-8")
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
