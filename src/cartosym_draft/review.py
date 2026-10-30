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
    "opacity": Row("whole symbol (group opacity)", "Keep as drafted.", "unchanged"),
    "casing-order": Row("casing beneath the stroke", "Keep as drafted.", "unchanged"),
    "casing-crossing": Row("all casings with the same zOrder beneath the strokes", "Done, as Jérôme answered and as "
                           "the painter's algorithm in clause 7 loops (casing passes inside each zOrder).", "resolved, #147"),
    "casing-width": Row("extends beyond each side of the stroke", "Done, as Jérôme answered (total = stroke + 2 × casing).",
                        "resolved, #147"),
    "font-outline": Row("outline beneath the glyphs", "Keep as drafted (as SE Halo).", "unchanged"),
    "z-order": Row("higher zOrder on top", "Keep as drafted.", "unchanged"),
    "hatch-angle": Row("clockwise (table)", "Probably counter-clockwise from 0 pointing right, as other angles drawn on "
                       "the map (Jérôme); check graphics toolkits first.", "TODO(review), #146",
                       "What do Win32 GDI, X and newer toolkits do? (@ebocher, @oertz, @maxcollombin)"),
    "dash-units": Row("pixels unless uom-qualified", "Done, as Jérôme answered (as SE).", "resolved"),
    "image-hotspot": Row("centre (0.5, 0.5)", "Keep as drafted (Jérôme confirmed; same as libCartoSym).",
                         "resolved; tint and blackTint added, alphaThreshold for picking (permission for the alpha "
                         "test), #145"),
    "default-marker": Row("a single default Dot (white, 10 px)",
                          "Keep, as intended (Jérôme); clearing it (`marker: null`) is now in the NOTE. Fix the schema "
                          "(`anyOf` in graphicArray plus a `marker` change, #143). Done: Dot has `size` and `color`, the same "
                          "values as its stroke's width and color, always a filled circle; CS-JSON forbids setting both in "
                          "one object (#144).", "NOTE + TODO(review), #143; resolved, #144", "Schema change OK?"),
    "dots": Row("not stated", "Add dot size and color properties; until then, small dots in the fill color.",
                "TODO(review), #84", "Should stipple/dot-pattern dots have their own size and color?"),
    "label-priority": Row("higher value wins", "Keep as drafted (as QGIS and GeoServer, and as zOrder); libCartoSym's "
                          "engine currently places lower values first.", "TODO(review), #148",
                          "Higher wins, or rename the property if lower should come first?"),
    "label-spacing": Row("pixels unless uom-qualified", "Done, as Jérôme answered.", "resolved"),
    "label-pass": Row("separate pass on top", "Keep as drafted.", "unchanged"),
    "ndvi-division": Row("real quotient", "Keep as drafted (confirmed by Jérôme, as CQL2); libCartoSym should change "
                         "(it returns 0 for example 7).", "unchanged", "Open the libCartoSym issue?"),
    "color-channels": Row("0..1; example 6 scales the bands", "Done: as Jérôme's renderer, the style scales the bands "
                          "(÷ 2500 in example 6).", "resolved; default: TODO(review), #150",
                          "The default colorChannels (fields[0..2]) is unscaled too: keep it?"),
    "color-map": Row("interpolate (method open), exact at entries, clamp outside",
                     "Done, as Jérôme answered; libCartoSym interpolates quadratically. SHOULD stay between the two "
                     "closest entries; stepped classes via conditional expressions (Jérôme).", "recommendation + NOTE, #149"),
    "gamma": Row("c ^ gamma (darkens above 1)", "Remove from coverage (not in the model); if kept, use SE's direction.",
                 "TODO(review), #86"),
    "hillshade-factor": Row("multiplies the horizontal components of the normal", "Done, as Jérôme's renderer, "
                            "including the sample distance and the shade without a colorMap.", "resolved"),
    "hillshade-overlay": Row("dot product, 0 (full shade) to 1 (no shade)", "Done, as Jérôme described.", "resolved"),
    "sun-azimuth": Row("clockwise from north, a compass bearing", "Done, as Jérôme answered (as GDAL).", "resolved"),
    "gradient-angle": Row("degrees, 0 pointing right, turning counter-clockwise", "Done, as Jérôme answered.", "resolved"),
    "gradient-frame": Row("pixels unless uom-qualified; frame not stated (Part 2)",
                          "Wait until two or three renderers can be compared (Jérôme).", "TODO(review), #153"),
}

# Findings without a gallery card (from the test harness and the schema).
EXTRA_ROWS: list[tuple[str, Row]] = [
    ("notLike, notContains, notStartsWith, notEndsWith",
     Row("separate operations", "Encode as `not` applied to the positive form (as CQL2); no schema change.",
         "TODO(review), #140")),
    ("caseInsensitize / accentInsensitize vs casei / accenti",
     Row("long names (model); short in the schema", "Use the CQL2 names casei and accenti.", "TODO(review), #140")),
    ("What counts as an accent (`Ø`)",
     Row("“removes accents”", "Reference CQL2 Requirement 9. Either remove nonspacing marks only (Ø stays, as this "
         "renderer does), or also fold with a named one-to-one table (Ø → O, as libCartoSym does).", "TODO(review), #152",
         "Which of the two?")),
    ("Right-hand identifiers vs the CSCSS examples",
     Row("any expression on the right-hand side", "Done: where an enumeration is expected, a bare word is an "
         "enumeration value (clause 17); a NOTE now points there.", "resolved, #151")),
    ("center vs centerLine",
     Row("center (UML)", "Decide one name.", "TODO(review), #120", "Which name is intended?")),
    ("Schema: colors from expressions, empty arrays, and clearing the marker",
     Row("(schema on main)", "Make the oneOf branches exclusive (e.g., require r, g, b in the color object). For the "
         "marker: `anyOf` in graphicArray, and `marker` accepting null and an object without elements (tested).",
         "not in PR (schema), #140, #143")),
    ("format string syntax",
     Row("C printf conversion specifiers (ANSI C)", "Done, as Jérôme answered.", "resolved")),
    ("intDiv in libCartoSym 0.0.1",
     Row("truncating integer division", "Fix in libCartoSym: cs-canif crashes on `7 div 2`.",
         "n/a (implementation), ecere/libCartoSym#5")),
]
