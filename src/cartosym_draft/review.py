"""Review annotations for the gallery: sources and the decision matrix.

Edit this file to change what the matrix says. `draft_says` is what the requirement
text says (the snapshot in requirements.json), `view` the proposed resolution (from
the Part 1 editor), and `status` where the question stands on GitHub as of
MATRIX_AS_OF: what Part 1 says, what open pull requests change, and answers given
since. A merged pull request counts as decided. Update MATRIX_AS_OF with the rows.
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
REPORT = "https://github.com/henrik716/cartosym-draft-check/blob/main/reports/libcartosym-main/report.md"

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
    "ndvi-division": [("Test report: arithmetic/div cases", REPORT + "#reqarithmeticdiv")],
}


@dataclass
class Row:
    draft_says: str
    view: str  # our proposal
    status: str  # where it stands, as of MATRIX_AS_OF
    ask: str = ""  # question for the SWG


MATRIX_AS_OF = "23 November 2026"

MATRIX: dict[str, Row] = {
    "opacity": Row("multiplies fill, stroke, marker graphics and coverage cells; not labels; recommended for the parts "
                   "together, per feature or per data layer and zOrder",
                   "Keep, with the recommendation to apply it to the parts together (group opacity).",
                   "In Part 1 (#133), as Jérôme answered on #162. Jérôme on #192 questioned the cost of applying it "
                   "per feature (W14); #192 (merged 20 November) allows either per feature or per data layer and "
                   "zOrder, with a NOTE that the choice is still under consideration. The draft renderer applies it "
                   "per data layer and zOrder, so that all fills are drawn before the casings (#198).",
                   "Per feature, or per data layer and zOrder?"),
    "casing-order": Row("casing beneath the stroke", "Keep.", "In Part 1 (#133); no comment on #162."),
    "casing-crossing": Row("all casings with the same zOrder beneath the strokes",
                           "Keep, as the painter's algorithm in clause 7 loops (casing passes inside each zOrder).",
                           "In Part 1 (#133), as Jérôme answered on #147 (closed). #192 (merged) draws centre lines "
                           "after all main strokes of the zOrder (W6). On #198 Jérôme agreed the order within a pass: "
                           "fill, casing, main stroke, centre line, then marker; the marker part is not in the text yet."),
    "casing-width": Row("extends beyond each side of the stroke; casing and centre line widths default to 0",
                        "Keep (total = stroke + 2 × casing).",
                        "In Part 1 (#133), as Jérôme answered on #147 (closed). The defaults Jérôme gave on #194 (width "
                        "0 turns them off, black if only a width is set) came with #192 (merged)."),
    "font-outline": Row("outline beneath the glyphs; outline size in pixels", "Keep (as SE Halo).",
                        "In Part 1 (#133); no comment on #162. #192 (merged) gives the outline size in pixels (W11); "
                        "units wait for the schema. On #100 (18–19 November) Jérôme and the Part 1 editor agreed that a "
                        "font `size` without a unit is in pixels, like every other length, with `pt` written out in the "
                        "examples; not in a pull request yet.",
                        "Confirm pixels for a font `size` without a unit (#100)."),
    "z-order": Row("higher zOrder on top", "Keep.", "In Part 1 (#133); no comment on #162."),
    "hatch-angle": Row("counter-clockwise, following the figure of the default hatch (TODO(review), #146)",
                       "Counter-clockwise from 0 pointing right, as the document's figure of the default hatch shows "
                       "and as gradient angles turn.",
                       "#192 (merged 20 November) made it counter-clockwise (W8), after Jérôme's \"sounds right\". #146 "
                       "(one convention for all angles) is still open.",
                       "Confirm counter-clockwise for every angle drawn on the map (#146)."),
    "dash-units": Row("UnitValues, pixels unless qualified", "Keep.",
                      "In Part 1 (#133), as Jérôme answered on #161: px, pt, mm, cm and inches, and a permission for "
                      "meters, feet and percent of the stroke width. `dashOffset` is defined by #192 (W5) and in the "
                      "schema by #188 (both merged 20 November; #120 closed)."),
    "image-hotspot": Row("the centre by default", "Keep the centre as the default.",
                         "In Part 1 (#133, #145 closed). Following Jérôme on #192 and #100, #192 (merged) reads a "
                         "`hotSpot` number without a unit as pixels of the image file, with `50 pc 50 pc` (the default) "
                         "for the centre and `0 0` the top left corner. A uom-qualified Image `size` is a TODO(review) "
                         "(#100)."),
    "default-marker": Row("a single default Dot (white, 10 px)",
                          "Keep, as intended (Jérôme); a style clears it with `marker: null`.",
                          "In Part 1 (#133): the NOTE, a schema that accepts `marker: null` (#143, closed), and Dot "
                          "`size` and `color` (#144, closed). #192 (merged) adds the permission "
                          "`/per/vector/dot-outline`. Jérôme proposes a Marker `placement` member so that the default "
                          "Marker is drawn at points only (#241, open); the spelling of "
                          "`feature.geometryDimension(s)` is #242.",
                          "A `placement` member on Marker, defaulting to points (#241)?"),
    "dots": Row("dot patterns: 2 px dots in the fill colour on a grid; stipples: dots covering the `ratio`, size and "
                "arrangement not stated (both TODO(review), #84)",
                "Keep the dot pattern as it is (W9); define the stipple dots or merge the two classes.",
                "#192 (merged) added the dot pattern wording (W9, W10). Open in #84 and #184: Jérôme on #184 (20 "
                "November): the dots were meant in `fill.color` and 1 × 1 pixel, and a dot pattern as a random "
                "distribution with an accurate ratio, so the two may overlap; to be discussed at an SWG meeting with "
                "the vignettes.",
                "What should stipples and dot patterns look like, and are both needed?"),
    "label-priority": Row("higher value wins (TODO(review))", "Keep the name `priority` with higher winning, or rename "
                          "it if lower should come first. libCartoSym's placement engine places lower values first.",
                          "Open, #148; no answer yet.", "Higher wins, or rename the property if lower should come first?"),
    "label-spacing": Row("pixels unless uom-qualified", "Keep.", "In Part 1 (#133), as Jérôme answered."),
    "label-pass": Row("separate pass on top; omitting overlaps is recommended", "Keep.",
                      "In Part 1 (#133), as Jérôme answered on #162. Labels that cross the edge of the map: following "
                      "Jérôme, #192 (merged) leaves it to the Renderer in a NOTE (static maps, dynamic maps, tiles)."),
    "ndvi-division": Row("real quotient", "Keep (as CQL2).",
                         "In Part 1 (#133). libCartoSym `main` divides integers as reals since ecere/libCartoSym#11 "
                         "was closed on 16 November; the `cartosym` 0.0.1 pip package still truncates."),
    "color-channels": Row("0..1; example 6 scales the bands",
                          "Examples 6 and 7 assume reflectance, with a second version for digital numbers (proposed "
                          "on #150).",
                          "TODO(review) in clause 7, #150 open.",
                          "Which data should examples 6 and 7 assume, and is the unscaled default OK?"),
    "color-map": Row("interpolate (method open), exact at entries, clamp outside",
                     "Keep, with the recommendation that the result stays between the two closest entries.",
                     "In Part 1 (#133, #149 closed). Following Jérôme, #192 (merged) prescribes no method, keeps a "
                     "classification uninterpolated, and permits interpolating continuous variables (from the logical "
                     "schema) and drawing from overviews (W12)."),
    "gamma": Row("removed from Part 1", "Use `^` in colorChannels instead.",
                 "Removed by #133 (#86 closed), as the SWG agreed on 6 November."),
    "hillshade-factor": Row("multiplies the horizontal components of the normal; 0 by default (off)", "Keep.",
                            "In Part 1 (#133). As Jérôme asked on #194, #192 (merged) adds `factor: 0` as the default "
                            "and lowers examples 8 and 9 to `factor: 3`."),
    "hillshade-overlay": Row("dot product, 0 (full shade) to 1 (no shade)", "Keep.",
                             "In Part 1 (#133). #192 (merged) says the normal is taken \"at about the resolution being "
                             "rendered\", with the method as a NOTE (W13), as Jérôme asked."),
    "sun-azimuth": Row("clockwise from north, a compass bearing; 315 and 45 by default", "Keep.",
                       "In Part 1 (#133). For global data and globes (Jérôme), #192 (merged) says \"north as shown on "
                       "the map at the shaded point\" (W16), with the defaults Jérôme agreed on #194."),
    "gradient-angle": Row("degrees, 0 pointing right, turning counter-clockwise", "Keep.",
                          "In the Part 2 gradient fills (#133). #192 (merged) turns hatch angles the same way (W8); "
                          "#146 is open."),
    "gradient-frame": Row("pixels unless uom-qualified; frame not stated (Part 2)",
                          "Wait until two or three renderers can be compared (Jérôme).",
                          "#153 open, tagged Part 2: Part 1 has no gradient property left since #133 (Maxime and "
                          "Jérôme on #153, 18–19 November)."),
}

# Findings without a gallery card (from the test harness and the schema).
EXTRA_ROWS: list[tuple[str, Row]] = [
    ("notLike in CartoSym-JSON",
     Row("a separate operation; the schema has none",
         "Keep `notLike` in the model, encoded in CartoSym-JSON as `not` applied to `like`, as CQL2 does.",
         "Jérôme on #140 (13 November): the same, and written back to CartoSym-CSS as `NOT LIKE`. Tracked in #167.")),
    ("caseInsensitize / accentInsensitize vs casei / accenti",
     Row("casei and accenti", "Use the CQL2 names casei and accenti.",
         "Done in #224 (merged 20 November), as Jérôme asked on #167.")),
    ("What counts as an accent (`Ø`)",
     Row("accent stripping and diacritic folding (CQL2 Requirement 9)", "Fold Ø → O, as libCartoSym does.",
         "In Part 1 (#133), with a NOTE pointing to Unicode Technical Report 30; #152 open. Jérôme fixed the folding "
         "of seven letters in eC `main` (19 November).")),
    ("Right-hand identifiers vs the CSCSS examples",
     Row("any expression on the right-hand side", "Where an enumeration is expected, a bare word is an "
         "enumeration value (clause 16).", "In Part 1 (#133, #151 closed).")),
    ("center vs centerLine",
     Row("center everywhere", "Use center.",
         "The SWG decided `center` on 13 November; #188 (merged 20 November) changed the schema and #120 is closed.")),
    ("a_equals and element order",
     Row("compares in order, as libCartoSym does (TODO(review))", "Jérôme would rather keep arrays ordered, but keep "
         "CQL2's meaning as far as possible.", "Open, #154; raised as opengeospatial/ogcapi-features#1099.",
         "Ordered, or sets as in CQL2?")),
    ("NULL in expressions",
     Row("operations follow CQL2; a Symbolizer property takes a value per data type",
         "0, false, black, the empty string, the default for an enumeration, and null for a Marker or Label, with "
         "a recommendation to report it.",
         "In Part 1 (#133). #155 open: a pull request is to follow libCartoSym (18 November): division by zero gives "
         "NULL, `5 IN (1, NULL)` gives NULL, and `x IN ()` is false.")),
    ("contains, startsWith, endsWith: functions or operators",
     Row("functions, no prefix; not* removed", "Keep.",
         "In Part 1 (#133). libCartoSym made them functions (ecere/libCartoSym#12, closed 16 November). #156 is "
         "still open.")),
    ("intDiv and mod",
     Row("truncate toward zero; sign of the first operand", "Keep, as C-style languages do (Jérôme).",
         "In Part 1 (#133), as Jérôme answered on #162.")),
    ("round and rint",
     Row("round: halves away from zero; rint removed", "Keep (the C rule).",
         "In Part 1 (#133), as Jérôme answered on #162. ceil, floor and round return an integer since #190; large "
         "numbers are #229.")),
    ("Function call with wrong arguments",
     Row("evaluates to NULL", "Keep, with integer → real and text → enumeration conversions.",
         "In Part 1 (#133), as Jérôme answered on #162 and #163.")),
    ("min and max with more than two arguments",
     Row("one or more arguments", "One or more arguments, as Jérôme answered on #192.",
         "In Part 1 since #192 (merged 20 November); the harness expects 5 for `max(1, 5, 3)` and 7 for `min(7)`, and "
         "libCartoSym `main` gives both. Mixing units in their arguments is #237.")),
    ("CartoSym-CSS selectors",
     Row("expressions ANDed; only short-hand data layer names ORed", "Keep.",
         "In Part 1 (#133), with a NOTE and Jérôme's example in clause 16. pycartosym follows it since 0.6.4. "
         "An implied OR between selectors separated by commas is #239.")),
    ("Schema: colors from expressions, empty arrays, and clearing the marker",
     Row("(schema on `main`)", "Make the branches exclusive (2020-12, the fixes from #140).",
         "Done in #188 (merged 20 November), from #140, #165 and #166; the schema tests give 0 wrong outcomes on it "
         "with three validators. The Part 2 to 4 schemas are still broken on `main`.")),
    ("format string syntax",
     Row("C printf conversion specifiers (ANSI C)", "Keep.", "In Part 1 (#133), as Jérôme answered.")),
    ("intDiv in libCartoSym",
     Row("truncating integer division", "Fix in libCartoSym: cs-canif 0.0.1 crashes on `7 div 2`.",
         "Fixed in libCartoSym `main` (ecere/libCartoSym#5, closed 16 November); the pip package still crashes.")),
]
