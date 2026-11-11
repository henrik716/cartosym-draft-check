"""Review annotations for the gallery: sources and the decision matrix.

Edit this file to change what the matrix says. `view` is the proposed resolution
(from the PR author); `status` is what PR #133 currently does about it.
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
    status: str  # in PR #133 now
    ask: str = ""  # question for Jérôme / the SWG


MATRIX: dict[str, Row] = {
    "opacity": Row("multiplies fill, stroke, marker graphics and coverage cells; not labels",
                   "In the PR, as Jérôme answered, with a recommendation to apply it to the parts together (group "
                   "opacity). Jérôme asked about the cost of compositing; the draft renderer uses SVG group opacity, "
                   "with no performance data.", "answered, #162"),
    "casing-order": Row("casing beneath the stroke", "Keep as drafted.", "no objection, #162"),
    "casing-crossing": Row("all casings with the same zOrder beneath the strokes", "In the PR, as Jérôme answered and as "
                           "the painter's algorithm in clause 7 loops (casing passes inside each zOrder).", "answered, #147"),
    "casing-width": Row("extends beyond each side of the stroke", "In the PR, as Jérôme answered (total = stroke + 2 × casing).",
                        "answered, #147"),
    "font-outline": Row("outline beneath the glyphs", "Keep as drafted (as SE Halo).", "no objection, #162"),
    "z-order": Row("higher zOrder on top", "Keep as drafted.", "no objection, #162"),
    "hatch-angle": Row("clockwise (table)", "Probably counter-clockwise from 0 pointing right, as other angles drawn on "
                       "the map (Jérôme); check graphics toolkits first.", "TODO(review), #146",
                       "What do Win32 GDI, X and newer toolkits do? (@ebocher, @oertz, @maxcollombin)"),
    "dash-units": Row("UnitValues, pixels unless qualified",
                      "In the PR, as Jérôme answered: a Renderer supports px, pt, mm, cm and inches, and a permission in "
                      "three parts covers meters and feet, and percent of the stroke width.", "answered, #161"),
    "image-hotspot": Row("centre (0.5, 0.5)", "Keep as drafted (Jérôme confirmed; same as libCartoSym).",
                         "answered; tint and blackTint added, alphaThreshold for picking (permission for the alpha "
                         "test), #145"),
    "default-marker": Row("a single default Dot (white, 10 px)",
                          "Keep, as intended (Jérôme); clearing it (`marker: null`) is now in the NOTE. Fix the schema "
                          "(`anyOf` in graphicArray plus a `marker` change, and test `label`, #143), as the SWG agreed on 6 November. In the PR: Dot has `size` and `color`, the same "
                          "values as its stroke's width and color, always a filled circle; CS-JSON forbids setting both within "
                          "a single styling rule (#144).", "NOTE, #143 agreed by the SWG and in the PR; answered, #144"),
    "dots": Row("not stated", "Add dot size and color properties; until then, small dots in the fill color.",
                "TODO(review), #84", "Should stipple/dot-pattern dots have their own size and color?"),
    "label-priority": Row("higher value wins", "Keep as drafted (as QGIS and GeoServer, and as zOrder); libCartoSym's "
                          "engine currently places lower values first.", "TODO(review), #148",
                          "Higher wins, or rename the property if lower should come first?"),
    "label-spacing": Row("pixels unless uom-qualified", "In the PR, as Jérôme answered.", "answered"),
    "label-pass": Row("separate pass on top; omitting overlaps is recommended",
                      "In the PR: the separate pass as drafted, and omitting labels that overlap is now a "
                      "recommendation, unless a property of the Symbolizer allows the overlap (Jérôme).",
                      "answered, #162"),
    "ndvi-division": Row("real quotient", "Keep as drafted (confirmed by Jérôme, as CQL2); libCartoSym should change "
                         "(it returns 0 for example 7; Jérôme agrees).", "unchanged, ecere/libCartoSym#11"),
    "color-channels": Row("0..1; example 6 scales the bands", "Example 6 scales the bands in the style (÷ 2500), as one of "
                          "Jérôme's own styles does, though Jérôme said the example assumed pre-scaled bands. Proposed on "
                          "#150: examples 6 and 7 assume reflectance, with a second version for digital numbers.",
                          "TODO(review), #150", "Which data should examples 6 and 7 assume, and is the unscaled default OK?"),
    "color-map": Row("interpolate (method open), exact at entries, clamp outside",
                     "In the PR, as Jérôme answered (clamp, exact at entries, method open); libCartoSym interpolates "
                     "quadratically. Stepped classes via conditional expressions (Jérôme). Added by the PR: a "
                     "recommendation that the result stays between the two closest entries.",
                     "recommendation + NOTE, #149", "Recommendation OK?"),
    "gamma": Row("c ^ gamma (darkens above 1)", "Take out of Part 1, as the SWG agreed on 6 November. The ^ operator in colorChannels does the same.",
                 "agreed by the SWG and removed in the PR, #86"),
    "hillshade-factor": Row("multiplies the horizontal components of the normal", "In the PR, as Jérôme's renderer, "
                            "including the sample distance and the shade without a colorMap.", "answered"),
    "hillshade-overlay": Row("dot product, 0 (full shade) to 1 (no shade)", "In the PR, as Jérôme described.", "answered"),
    "sun-azimuth": Row("clockwise from north, a compass bearing", "In the PR, as Jérôme answered (as GDAL).", "answered"),
    "gradient-angle": Row("degrees, 0 pointing right, turning counter-clockwise", "In the PR, as Jérôme answered.", "answered"),
    "gradient-frame": Row("pixels unless uom-qualified; frame not stated (Part 2)",
                          "Wait until two or three renderers can be compared (Jérôme).", "TODO(review), #153"),
}

# Findings without a gallery card (from the test harness and the schema).
EXTRA_ROWS: list[tuple[str, Row]] = [
    ("notLike in CartoSym-JSON",
     Row("a separate operation; the schema has none", "Encode as `not` applied to `like` (as CQL2); no schema change. "
         "notContains, notStartsWith and notEndsWith are removed: their negations use `not` (#156).",
         "TODO(review), #140")),
    ("caseInsensitize / accentInsensitize vs casei / accenti",
     Row("long names (model); short in the schema", "Use the CQL2 names casei and accenti.", "TODO(review), #140")),
    ("What counts as an accent (`Ø`)",
     Row("accent stripping and diacritic folding (CQL2 Requirement 9)", "In the PR, as Jérôme answered: folds Ø → O as "
         "libCartoSym does, with a NOTE pointing to Unicode Technical Report 30.", "answered, #152")),
    ("Right-hand identifiers vs the CSCSS examples",
     Row("any expression on the right-hand side", "In the PR: where an enumeration is expected, a bare word is an "
         "enumeration value (clause 17); a NOTE now points there.", "answered, #151")),
    ("center vs centerLine",
     Row("center (UML)", "Use center, as the UML and libCartoSym do, and change the schema.", "TODO(review), #120",
         "Which name is intended?")),
    ("a_equals and element order",
     Row("compares in order, as libCartoSym does", "Jérôme would rather keep arrays ordered, but keep CQL2's meaning as far as possible, "
         "and suggests raising it with OGC API - Features.", "partly answered, #154", "Ordered, or sets as in CQL2?")),
    ("NULL in expressions",
     Row("operations follow CQL2; a Symbolizer property takes a value per data type",
         "In the PR, as Jérôme answered: 0, false, black, the empty string, the default for an enumeration, and "
         "null for a Marker or Label, with a recommendation to report it.", "answered, #155")),
    ("contains, startsWith, endsWith: functions or operators",
     Row("functions, no prefix; not* removed", "In the PR as a preliminary approach, as Jérôme agreed (no prefix, "
         "not* removed, class renamed, clauses 14 and 15 merged). libCartoSym has operators (`~`, `^^`, `$`), "
         "left over from GNOSIS CMSS.", "preliminary, SWG decides 13 November, #156",
         "Functions or operators?")),
    ("intDiv and mod",
     Row("truncate toward zero; sign of the first operand", "Keep, as C-style languages do (Jérôme); worth "
         "raising with OGC API - Features for CQL2.", "answered, #162")),
    ("round and rint",
     Row("round: halves away from zero; rint removed", "In the PR, as Jérôme answered (the C rule).",
         "answered, #162")),
    ("Function call with wrong arguments",
     Row("evaluates to NULL", "In the PR, as Jérôme answered. Which conversions apply (integer to real, text to "
         "an enumeration) is open.", "answered, #162; conversions in #163",
         "Which argument conversions are required?")),
    ("CartoSym-CSS selectors",
     Row("expressions ANDed; only short-hand data layer names ORed",
         "In the PR, with a NOTE and Jérôme's example in clause 17. pycartosym ANDed several names until "
         "0.6.4 (maxcollombin/pycartosym#169).", "answered, #162")),
    ("Schema: colors from expressions, empty arrays, and clearing the marker",
     Row("(schema on main)", "Make the oneOf branches exclusive (e.g., require r, g, b in the color object). For the "
         "marker: `anyOf` in graphicArray, and `marker` accepting null and an object without elements (tested; the SWG agreed the marker part on 6 November).",
         "marker in the PR, #143; the rest not in the PR, #140")),
    ("format string syntax",
     Row("C printf conversion specifiers (ANSI C)", "In the PR, as Jérôme answered.", "answered")),
    ("intDiv in libCartoSym 0.0.1",
     Row("truncating integer division", "Fix in libCartoSym: cs-canif crashes on `7 div 2`.",
         "n/a (implementation), ecere/libCartoSym#5")),
]
