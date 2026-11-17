"""Review annotations for the gallery: sources and the decision matrix.

Edit this file to change what the matrix says. `draft_says` is what the requirement
text says (the snapshot in requirements.json), `view` the proposed resolution (from
the Part 1 editor), and `status` where the question stands on GitHub as of
MATRIX_AS_OF: what Part 1 says since #133 merged, what open pull requests change,
and answers given since. Update MATRIX_AS_OF with the rows.
"""

from __future__ import annotations

from dataclasses import dataclass

SE11 = "https://docs.ogc.org/is/05-077r4/05-077r4.pdf"
GEOSERVER_RASTER = "https://docs-archive.geoserver.org/stable/en/user/styling/sld/reference/rastersymbolizer.html"
GEOSERVER_LINE = "https://docs-archive.geoserver.org/stable/en/user/styling/sld/reference/linesymbolizer.html"
GEOSERVER_TEXT = "https://docs.geoserver.org/main/en/user/styling/ysld/reference/symbolizers/text/"
MAPLIBRE = "https://maplibre.org/maplibre-style-spec/layers/"
QGIS_LABELS = "https://docs.qgis.org/latest/en/docs/user_manual/style_library/label_settings.html"
GDALDEM = "https://gdal.org/en/stable/programs/gdaldem.html"
CSS_GRADIENT = "https://developer.mozilla.org/en-US/docs/Web/CSS/gradient/linear-gradient"
ISSUES = "https://github.com/opengeospatial/cartographic-symbology/issues/"
PR133 = "https://github.com/opengeospatial/cartographic-symbology/pull/133"

# Sources for the claims in each card's evidence line, checked 2026-10-15.
SOURCES: dict[str, list[tuple[str, str]]] = {
    "font-outline": [("SE 1.1, 11.4.5 Halo: applied to the backgrounds of font glyphs", SE11),
                     ("QGIS label buffer", QGIS_LABELS)],
    "dash-units": [("SE 1.1, Stroke: stroke-dasharray lengths in the symbolizer's units of measure", SE11),
                   ("GeoServer: stroke-dasharray in pixels", GEOSERVER_LINE),
                   ("MapLibre line-dasharray: units in line widths", MAPLIBRE + "#line-dasharray")],
    "label-priority": [("QGIS: the label with the higher priority is displayed", QGIS_LABELS),
                       ("GeoServer: higher priority values take precedence", GEOSERVER_TEXT),
                       ("MapLibre symbol-sort-key: lower values placed first", MAPLIBRE + "#symbol-sort-key")],
    "casing-width": [("Jérôme, #147: total width = main width + 2 × casing width", ISSUES + "147")],
    "casing-crossing": [("Jérôme, #147: equivalent to drawing all casings first", ISSUES + "147")],
    "color-map": [("SE 1.1, RasterSymbolizer ColorMap: Interpolate or Categorize", SE11),
                  ("GeoServer: ColorMap type ramp (interpolated) is the default", GEOSERVER_RASTER)],
    "gamma": [("SE 1.1, ContrastEnhancement: GammaValue above 1.0 brightens", SE11)],
    "hillshade-factor": [("Jérôme's renders for factor 1, 8, 32 and 64 (PR #133)", PR133),
                         ("gdaldem hillshade: -z is a vertical exaggeration", GDALDEM)],
    "hillshade-overlay": [("Jérôme's renders for factor 1, 8, 32 and 64 (PR #133)", PR133),
                          ("gdaldem hillshade: -z is a vertical exaggeration", GDALDEM)],
    "sun-azimuth": [("gdaldem hillshade: azimuth 0 = from the top, 90 = from the east", GDALDEM)],
    "gradient-angle": [("CSS linear-gradient: 0deg = to top, clockwise", CSS_GRADIENT)],
    "ndvi-division": [("Test report: arithmetic/div cases", "../reports/report.md")],
}


@dataclass
class Row:
    draft_says: str
    view: str  # our proposal
    status: str  # where it stands, as of MATRIX_AS_OF
    ask: str = ""  # question for the SWG


MATRIX_AS_OF = "17 November 2026"

MATRIX: dict[str, Row] = {
    "opacity": Row("multiplies fill, stroke, marker graphics and coverage cells; not labels",
                   "Keep, with the recommendation to apply it to the parts together (group opacity).",
                   "In Part 1 (#133), as Jérôme answered on #162. Jérôme on #192 questioned the cost of applying it "
                   "per feature (W14); #192 now allows either per feature or per data layer and zOrder, with a NOTE "
                   "that the choice is still under consideration.",
                   "Per feature, or per data layer and zOrder?"),
    "casing-order": Row("casing beneath the stroke", "Keep.", "In Part 1 (#133); no comment on #162."),
    "casing-crossing": Row("all casings with the same zOrder beneath the strokes",
                           "Keep, as the painter's algorithm in clause 7 loops (casing passes inside each zOrder).",
                           "In Part 1 (#133), as Jérôme answered on #147 (closed). #192 draws centre lines after all "
                           "main strokes of the zOrder (W6), which Jérôme confirmed."),
    "casing-width": Row("extends beyond each side of the stroke",
                        "Keep (total = stroke + 2 × casing).",
                        "In Part 1 (#133), as Jérôme answered on #147 (closed). Jérôme on #194: casing and centre line "
                        "widths default to 0, which turns them off, with black as the colour if only a width is set; "
                        "#192 adds these defaults."),
    "font-outline": Row("outline beneath the glyphs", "Keep (as SE Halo).",
                        "In Part 1 (#133); no comment on #162. #192 gives the outline size in pixels (W11); Jérôme: "
                        "pixels unless another unit is given (the schema takes only a number there, so units wait for "
                        "the schema), and whether a bare `font.size` is in points is still to decide.",
                        "A font `size` without a unit: points, as Part 1 says, or pixels like other sizes?"),
    "z-order": Row("higher zOrder on top", "Keep.", "In Part 1 (#133); no comment on #162."),
    "hatch-angle": Row("clockwise in the table on `main`; counter-clockwise in #192",
                       "Counter-clockwise from 0 pointing right, as the document's figure of the default hatch shows "
                       "and as gradient angles turn.",
                       "#192 proposes counter-clockwise (W8); Jérôme on #192: \"sounds right\". #146 (one convention "
                       "for all angles) is still open.",
                       "Confirm counter-clockwise for every angle drawn on the map (#146)."),
    "dash-units": Row("UnitValues, pixels unless qualified", "Keep.",
                      "In Part 1 (#133), as Jérôme answered on #161: px, pt, mm, cm and inches, and a permission for "
                      "meters, feet and percent of the stroke width. #192 defines `dashOffset` (W5), as Jérôme "
                      "confirmed; #188 adds it to the schema."),
    "image-hotspot": Row("the centre by default", "Keep the centre as the default.",
                         "In Part 1 (#133, #145 closed). #192 first read a `hotSpot` number without a unit as a fraction "
                         "(W2); following Jérôme on #192 and #100 it now reads pixels of the image file, with "
                         "`50 pc 50 pc` (the default) for the centre and `0 0` the top left corner."),
    "default-marker": Row("a single default Dot (white, 10 px)",
                          "Keep, as intended (Jérôme); a style clears it with `marker: null`.",
                          "In Part 1 (#133): the NOTE, a schema that accepts `marker: null` and `marker: { elements: [] }` "
                          "(#143, closed), and Dot `size` and `color` (#144, closed). Jérôme on #192 and #194 suggested a "
                          "permission to draw a hairline outline, so that the white Dot shows on a white background; "
                          "#192 adds `/per/vector/dot-outline` (Dots only)."),
    "dots": Row("not stated on `main` (#84)",
                "#192: dot patterns as 2 px dots in the fill colour on a grid (W9); stipples as dots covering the "
                "`ratio`, their size and arrangement (regular or random) left to the Renderer (W10).",
                "Open, #84. Jérôme on #192 expects a stipple to be a regular bitmap pattern (for example 8 × 8) and "
                "a dot pattern perhaps more random, and asks whether both are needed.",
                "What should stipples and dot patterns look like, and are both needed?"),
    "label-priority": Row("higher value wins (TODO)", "Keep the name `priority` with higher winning, or rename it if "
                          "lower should come first. libCartoSym's placement engine places lower values first.",
                          "Open, #148; no answer yet.", "Higher wins, or rename the property if lower should come first?"),
    "label-spacing": Row("pixels unless uom-qualified", "Keep.", "In Part 1 (#133), as Jérôme answered."),
    "label-pass": Row("separate pass on top; omitting overlaps is recommended", "Keep.",
                      "In Part 1 (#133), as Jérôme answered on #162. Labels that cross the edge of the map: #192 "
                      "first omitted them (W7); following Jérôme, a NOTE now leaves it to the Renderer (static maps, "
                      "dynamic maps, tiles)."),
    "ndvi-division": Row("real quotient", "Keep (as CQL2).",
                         "In Part 1 (#133). libCartoSym `main` divides integers as reals since ecere/libCartoSym#11 "
                         "was closed on 16 November; the `cartosym` 0.0.1 pip package still truncates."),
    "color-channels": Row("0..1; example 6 scales the bands",
                          "Examples 6 and 7 assume reflectance, with a second version for digital numbers (proposed "
                          "on #150).",
                          "TODO(review) in Part 1, #150 open.",
                          "Which data should examples 6 and 7 assume, and is the unscaled default OK?"),
    "color-map": Row("interpolate (method open), exact at entries, clamp outside",
                     "Keep, with the recommendation that the result stays between the two closest entries.",
                     "In Part 1 (#133, #149 closed). #192 first gave each map pixel the cell that contains its centre "
                     "(W12); following Jérôme it now prescribes no method, keeps a classification uninterpolated, and "
                     "permits interpolating continuous variables (from the logical schema) and drawing from overviews."),
    "gamma": Row("removed from Part 1", "Use `^` in colorChannels instead.",
                 "Removed by #133 (#86 closed), as the SWG agreed on 6 November."),
    "hillshade-factor": Row("multiplies the horizontal components of the normal", "Keep.",
                            "In Part 1 (#133). Jérôme on #194: `factor: 0` is the default and turns hill shading off; "
                            "example 8's 56 is extreme, and the figures should show a range of values. #192 adds the "
                            "default and lowers examples 8 and 9 to `factor: 3`."),
    "hillshade-overlay": Row("dot product, 0 (full shade) to 1 (no shade)", "Keep.",
                             "In Part 1 (#133). #192 said which samples are differenced (W13); Jérôme: essentially "
                             "yes, but the wording should leave room. It now says \"at about the resolution being "
                             "rendered\", with the method as a NOTE."),
    "sun-azimuth": Row("clockwise from north, a compass bearing", "Keep.",
                       "In Part 1 (#133). #192 first measured it from grid north (W16); Jérôme: it needs to work for "
                       "global data and globes. It now says \"north as shown on the map at the shaded point\", with "
                       "the defaults Jérôme agreed on #194: azimuth 315, elevation 45."),
    "gradient-angle": Row("degrees, 0 pointing right, turning counter-clockwise", "Keep.",
                          "In the Part 2 gradient fills (#133). #192 turns hatch angles the same way (W8); #146 is "
                          "open."),
    "gradient-frame": Row("pixels unless uom-qualified; frame not stated (Part 2)",
                          "Wait until two or three renderers can be compared (Jérôme).", "TODO(review), #153 open."),
}

# Findings without a gallery card (from the test harness and the schema).
EXTRA_ROWS: list[tuple[str, Row]] = [
    ("notLike in CartoSym-JSON",
     Row("a separate operation; the schema has none",
         "Keep `notLike` in the model, encoded in CartoSym-JSON as `not` applied to `like`, as CQL2 does.",
         "Jérôme on #140 (13 November): the same, and written back to CartoSym-CSS as `NOT LIKE`. Now tracked in "
         "#167.")),
    ("caseInsensitize / accentInsensitize vs casei / accenti",
     Row("long names (model); short in the schema", "Use the CQL2 names casei and accenti.", "Open, #167.")),
    ("What counts as an accent (`Ø`)",
     Row("accent stripping and diacritic folding (CQL2 Requirement 9)", "Fold Ø → O, as libCartoSym does.",
         "In Part 1 (#133), with a NOTE pointing to Unicode Technical Report 30; #152 open.")),
    ("Right-hand identifiers vs the CSCSS examples",
     Row("any expression on the right-hand side", "Where an enumeration is expected, a bare word is an "
         "enumeration value (clause 17).", "In Part 1 (#133, #151 closed).")),
    ("center vs centerLine",
     Row("center (UML and text); centerLine in the schema on `main`", "Use center.",
         "The SWG decided `center` on 13 November. #188 changes the schema; #120 stays open until then.")),
    ("a_equals and element order",
     Row("compares in order, as libCartoSym does", "Jérôme would rather keep arrays ordered, but keep CQL2's "
         "meaning as far as possible.", "Open, #154; raised as opengeospatial/ogcapi-features#1099.",
         "Ordered, or sets as in CQL2?")),
    ("NULL in expressions",
     Row("operations follow CQL2; a Symbolizer property takes a value per data type",
         "0, false, black, the empty string, the default for an enumeration, and null for a Marker or Label, with "
         "a recommendation to report it.",
         "In Part 1 (#133). #155 open: Jérôme fixed several of the harness's NULL cases in libCartoSym (17 "
         "November) and would rather have recommendations than strict tests for malformed styles.")),
    ("contains, startsWith, endsWith: functions or operators",
     Row("functions, no prefix; not* removed", "Keep.",
         "In Part 1 (#133). libCartoSym made them functions (ecere/libCartoSym#12, closed 16 November). #156 is "
         "still open.")),
    ("intDiv and mod",
     Row("truncate toward zero; sign of the first operand", "Keep, as C-style languages do (Jérôme).",
         "In Part 1 (#133), as Jérôme answered on #162.")),
    ("round and rint",
     Row("round: halves away from zero; rint removed", "Keep (the C rule).",
         "In Part 1 (#133), as Jérôme answered on #162.")),
    ("Function call with wrong arguments",
     Row("evaluates to NULL", "Keep, with integer → real and text → enumeration conversions.",
         "In Part 1 (#133), as Jérôme answered on #162 and #163.")),
    ("min and max with more than two arguments",
     Row("two arguments (the table)", "One or more arguments, as Jérôme answered on #192.",
         "Jérôme added it to libCartoSym on 16 November. #192 now says one or more arguments; the harness "
         "expects 5 for `max(1, 5, 3)` and 7 for `min(7)`.")),
    ("CartoSym-CSS selectors",
     Row("expressions ANDed; only short-hand data layer names ORed", "Keep.",
         "In Part 1 (#133), with a NOTE and Jérôme's example in clause 17. pycartosym follows it since 0.6.4.")),
    ("Schema: colors from expressions, empty arrays, and clearing the marker",
     Row("(schema on `main`)", "Make the branches exclusive (2020-12, the fixes from #140).",
         "The marker part in Part 1 (#133, #143 closed). The rest is #188 (open), from #140, #165 and #166; the "
         "schema tests give 0 wrong outcomes on its branch.")),
    ("format string syntax",
     Row("C printf conversion specifiers (ANSI C)", "Keep.", "In Part 1 (#133), as Jérôme answered.")),
    ("intDiv in libCartoSym",
     Row("truncating integer division", "Fix in libCartoSym: cs-canif 0.0.1 crashes on `7 div 2`.",
         "Fixed in libCartoSym `main` (ecere/libCartoSym#5, closed 16 November); the pip package still crashes.")),
]
