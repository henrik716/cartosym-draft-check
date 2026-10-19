"""Review annotations for the gallery: sources and the decision matrix.

Edit this file to change what the matrix says. `view` is the proposed resolution
(from the PR author); `status` is what PR #133 currently does about it.
"""

from __future__ import annotations

from dataclasses import dataclass

SE11 = "https://docs.ogc.org/is/05-077r4/05-077r4.pdf"
GEOSERVER_RASTER = "https://docs-archive.geoserver.org/stable/en/user/styling/sld/reference/rastersymbolizer.html"
GEOSERVER_LINE = "https://docs-archive.geoserver.org/stable/en/user/styling/sld/reference/linesymbolizer.html"
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
    "dots": [("Issue #84", ISSUES + "84")],
    "label-priority": [("QGIS: the label with the higher priority is displayed", QGIS_LABELS),
                       ("MapLibre symbol-sort-key: lower values placed first", MAPLIBRE + "#symbol-sort-key")],
    "label-spacing": [("Issue #80 (text spacing, not placement)", ISSUES + "80")],
    "color-map": [("SE 1.1, RasterSymbolizer ColorMap: Interpolate or Categorize", SE11),
                  ("GeoServer: ColorMap type ramp (interpolated) is the default", GEOSERVER_RASTER)],
    "gamma": [("SE 1.1, ContrastEnhancement: GammaValue above 1.0 brightens", SE11), ("Issue #86", ISSUES + "86")],
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
    "casing-crossing": Row("not stated", "Specify: all casings before the strokes, so crossings merge.",
                           "TODO(review)"),
    "casing-width": Row("not stated", "Specify: total width of the casing band.", "TODO(review)"),
    "font-outline": Row("outline beneath the glyphs", "Keep as drafted (as SE Halo).", "unchanged"),
    "z-order": Row("higher zOrder on top", "Keep as drafted.", "unchanged"),
    "hatch-angle": Row("clockwise (table)", "Keep as drafted.", "unchanged"),
    "dash-units": Row("not stated", "Specify: the stroke's unit of measure, pixels by default (as SE).", "TODO(review)"),
    "image-hotspot": Row("centre (0.5, 0.5)", "Keep as drafted (same as libCartoSym).", "unchanged"),
    "default-marker": Row("a single default Dot (white, 10 px)",
                          "Keep, as intended (Jérôme); say how a style clears it, and give Dot defaults in terms of its Stroke.",
                          "NOTE + TODO(review)", "How does a style clear the marker? `marker: { elements: [] }` fails the schema."),
    "dots": Row("not stated (#84)", "Add dot size and color properties; until then, small dots in the fill color.",
                "TODO(review)", "Should stipple/dot-pattern dots have their own size and color?"),
    "label-priority": Row("higher value wins", "Keep as drafted.", "TODO(review)"),
    "label-spacing": Row("not stated", "Specify: pixels unless uom-qualified.", "TODO(review)"),
    "label-pass": Row("separate pass on top", "Keep as drafted.", "unchanged"),
    "ndvi-division": Row("real quotient", "Keep as drafted (confirmed by Jérôme, as CQL2); libCartoSym should change "
                         "(it returns 0 for example 7).", "unchanged", "Open the libCartoSym issue?"),
    "color-channels": Row("0..1; example 6 scales the bands", "Done: as Jérôme's renderer, the style scales the bands "
                          "(÷ 2500 in example 6).", "resolved",
                          "The default colorChannels (fields[0..2]) is unscaled too: keep it?"),
    "color-map": Row("interpolate, clamp outside", "Keep as drafted (GeoServer's default ramp behaves the same).", "TODO(review)"),
    "gamma": Row("c ^ gamma (darkens above 1)", "Remove from coverage (not in the model); if kept, use SE's direction.",
                 "TODO(review)"),
    "hillshade-factor": Row("multiplies the horizontal components of the normal", "Done, as Jérôme's renderer. "
                            "Still to state: the distance the normal is computed over, and the shade without a colorMap.",
                            "TODO(review)", "Over what horizontal distance is the normal computed?"),
    "hillshade-overlay": Row("dot product, 0 (full shade) to 1 (no shade)", "Done, as Jérôme described.", "resolved"),
    "sun-azimuth": Row("relative to north, direction not stated", "Specify: clockwise from north (as GDAL).",
                       "TODO(review)"),
    "gradient-angle": Row("not stated", "Specify: the CSS convention, 0 = up, clockwise.", "TODO(review)"),
    "gradient-frame": Row("not stated", "Specify: relative to each feature's bounding box.", "TODO(review)"),
}

# Findings without a gallery card (from the test harness and the schema).
EXTRA_ROWS: list[tuple[str, Row]] = [
    ("notLike, notContains, notStartsWith, notEndsWith",
     Row("separate operations", "Encode as `not` applied to the positive form (as CQL2); no schema change.",
         "TODO(review)")),
    ("caseInsensitize / accentInsensitize vs casei / accenti",
     Row("long names (model); short in the schema", "Use the CQL2 names casei and accenti.", "TODO(review)")),
    ("What counts as an accent (`Ø`)",
     Row("“removes accents”", "Follow Unicode decomposition: Ø is a letter, not O with an accent.", "TODO(review)",
         "Intended for libCartoSym too?")),
    ("Right-hand identifiers vs the CSCSS examples",
     Row("any expression on the right-hand side", "Specify how `[dataLayer.type = coverage]` (a bare word meant as a "
         "string, in the spec's examples) is read, or quote the strings in the examples.", "TODO(review)",
         "Is a bare word on the right a string or an identifier?")),
    ("center vs centerLine (#120)",
     Row("center (UML)", "Decide one name.", "TODO(review)", "Which name is intended?")),
    ("Schema: colors from expressions, and empty arrays",
     Row("(schema on main)", "Make the oneOf branches exclusive (e.g., require r, g, b in the color object).",
         "not in PR (schema)", "Report as an issue?")),
    ("intDiv in libCartoSym 0.0.1",
     Row("truncating integer division", "Report: cs-canif crashes on `7 div 2`.", "n/a (implementation)",
         "Known issue?")),
]
