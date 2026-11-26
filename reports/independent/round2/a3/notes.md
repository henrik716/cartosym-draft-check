# Notes: independent CartoSym renderer (Part 1 draft, from the text only)

Code: `renderer/render.py` (run as `uv run --no-project --with numpy --with pillow --with shapely python renderer/render.py`).
Images: `out/case-NN-1.png`, 18 files, all 300 x 200 px.
Each case was rendered from `style.cs.json`, the GeoJSON layers and `view-1.json`. The `.cscss` files were not used.

Scale: all views use 0.28 mm per pixel. Ground units are converted with `scaleDenominator`, so one metre is 1 px at 1:3571.4 and 1.79 px at 1:2000.

## 1. Choices where the text leaves the drawing open

Each entry gives the requirement, the words that leave the choice open, the readings considered, what I implemented, and the text I relied on.

### 1.1 Defaults for unset properties (`/req/core/default-values`, `/req/core/symbolizer`)

- Words: "using the default values for properties not set by any selected rule". The default table gives `fill` = default Fill (white), `stroke` = default Stroke (1 px black), `marker` = single default Dot (10 px white).
- Readings considered: (a) defaults apply to every feature, so a polygon with no `fill` gets a white fill and a 1 px black outline; (b) defaults apply only when the author writes nothing.
- Implemented: (a). The consequences are visible in the images: case 08 Zones and case 16 Zones have a black 1 px outline, and case 18 Piers get a white 10 px dot at the centroid.
- Relied on: "A Renderer SHALL support portraying, with the default values, ..." and the Symbolizer default table in clause 7.

### 1.2 Default marker on line strings (`/req/vector/marker`)

- Words: "at the points of vector geometry (for points and line strings) and at the centroid of polygons". It does not say whether "points of a line string" means its vertices or some other point on the line.
- Implemented: vertices for line strings, the point for points, the centroid for polygons. In every case that has line features, the style sets `marker: null` on those lines, so the default line marker never appears. Case 17 sets `marker: null` in its first rule, which has no selector and so applies to all features.

### 1.3 Rules with no selector and rule order (`/req/core/rules`, `/req/core/nested`)

- Words: "Symbolizer properties specified in a StylingRule appearing later ... overriding all Symbolizer properties set by earlier rules". A nested rule with no selector is always selected when its parent is.
- Implemented: plain last-wins per property. Object members (for example `stroke.width`) are merged. A `null` replaces the value.
- Consequence: case 01 and case 02 render only the white 3 px road. The black 5 px stroke is overridden by the later white stroke, not drawn underneath. The text leaves no room for another reading, but the author may have meant the black stroke to remain.

### 1.4 Visualization and feature passes (`/req/core/symbolizer`, clause 7 "Visualization Rendering Passes", `/req/vector/...` feature passes)

- Words: the painter's algorithm in clause 7 is written as "For each viz.pass ... For each feature: For each feature.pass: Render". It does not say whether a rule without a pass constraint is applied again in every pass.
- Readings considered: (a) literal: every feature is drawn in every viz pass with its resolved symbolizer; (b) a feature takes part in a pass only when a rule constrained to that pass selects it.
- Implemented: (b). Under (a), the base rule in case 16 would draw the green zone again in pass 1 over the black road of pass 0, so the road would be hidden. Under (b), zones are drawn once with no pass and the roads in passes 0 and 1.
- Feature passes follow the same rule per feature.
- Relied on: "Setting up symbolization rules for a selector on a visualization pass allows to render all data of the map using different set of symbolizers", and Annex C's use of `feature.pass = -1` for bridges.

### 1.5 Order within a pass (`/req/casing/casing`, `/req/casing/center`, `/req/core/zorder`)

- Words: "in increasing order of their resolved zOrder"; casings "beneath the main strokes of all those features"; centres "on top of the main strokes of all those features".
- Implemented, for each viz pass, then each zOrder value in increasing order: all casings of that zOrder, then all main symbolizers (fill, stroke, marker) in layer-then-feature order, then all centre lines. Labels are drawn last in a separate pass.
- Within one zOrder, layers keep the order of the view's `layers` list. This is my choice, since the text only says "drawing order" in the view.

### 1.6 Casing width (`/req/casing/casing`)

- Words: "a total width of the main stroke's width plus twice the casing's width".
- Implemented exactly that. Casing and centre are drawn as their own sub-passes as in 1.5.

### 1.7 Line caps, joins and dash pieces (`/req/vector/stroke`, `/req/dashes/dash-pattern`, `/req/dashes/dash-offset`)

- Words: "round caps at the ends of open lines and round joins at their vertices" (SHALL). For dashes the text says only "dashing vector geometry".
- Implemented: round caps and joins by default; `cap: butt` and `join: miter` when given (case 17). Each dash is a separate open line, so it also gets a round cap. Dash offset is applied once per line, and the pattern restarts on each line of a feature.

### 1.8 Units (`/req/vector/units`)

- Words: "px" is the default. For `m`/`ft` the text gives no conversion, but the view gives `scaleDenominator` and `pixelSize_mm` 0.28.
- Implemented: 1 px = 0.28 mm on the map; mm, cm, inch and pt (1 pt = 1/72 inch) are converted through 0.28 mm; ground units m and ft are converted with `scaleDenominator`.

### 1.9 Colours (clause 16 and clause 8 Color)

- Words: "red, green and blue components" are numbers in the JSON, and clause 16 gives "Color(255, 100, 50)" with 0 to 255 values. The JSON `[245, 215, 110]` form and the CSS name `lightGray` both appear.
- Implemented: JSON arrays as 0 to 255, CSS names and `#hex` through the standard colour table (PIL's name table).

### 1.10 Labels (`/req/labels/label`, `/req/labels/placement`, `/rec/labels/overlap`, clause 10)

- Words: "Text ... with a font and an alignment"; placement is required only where a `placement` object is given. Cases 13 and 18 give no placement.
- Implemented: a label is placed at the midpoint (by length) of the longest part of a line, at the representative point of a polygon, and at the point. Its `position` offset is in px, positive y downwards. Labels that overlap an earlier label are omitted (`/rec/labels/overlap`). No repetition of labels is done.
- Font: Arial and sans-serif are not available here, so every label uses the Pillow default font at the size given in points. The bold flag is not applied. Labels are not coloured by opacity.

### 1.11 Null parameter values (`/req/parameter-values/null`)

- Implemented per the table: a null number is 0, a null colour is black, a null `visibility` is false, a null marker or label is empty, a `null` set directly removes the symbolizer. No case depends on this in an important way.

### 1.12 Symbolizer opacity (`/req/core/opacity`, `/rec/core/opacity-together`)

- Words: "SHOULD apply the Symbolizer opacity to the fill, the stroke and the graphics of markers together".
- Implemented per primitive (each fill, stroke and marker is composited separately). This departs from the recommendation. It matters only where primitives of one feature overlap. Case 16 is the only case with opacity below 1, and its two strokes are in different viz passes.

## 2. Not implemented

- **SVG image fills (case 17, 6 uses).** `fill.pattern` with an `Image` type referring to an SVG file. No SVG rasterizer is allowed (or available without another library). The fill is skipped for those features, and the note in the run log lists them. Features with a plain colour fill are drawn.
- **Vendor extension `vendor.xleitstelle`** (case 17: `offset`, `placements`, `rotate`, `trim`). It is not part of CartoSym and was ignored.
- **`stroke.patternGap`, `patternInitialGap`, `stroke.pattern`** (case 17). Not implemented, since they are patterns along the line of SVG images.
- **Hatch, dot pattern and stipple fills.** No case uses them, so I did not implement them.
- **Image markers, `em` units, percent units.** Not used by any case.

## 3. Contradictions, undefined names and gaps in the text

- **Names for the visualization pass.** Clause 7 uses `visualization.pass` in the construct table and in the Annex C text, while the cases and the requirement sections use `viz.pass`. I read them as the same identifier.
- **CRS.** The README says the layers are in EPSG:25833. Case 17's view says EPSG:25832, and its GeoJSON files also say EPSG:25832. I used the coordinates as they are, with no reprojection, and used the view's bbox.
- **`feature.pass = -1`.** Annex C says it draws bridges "first", but the text gives no definition of the pass values. I treat any integer as a pass label. Its order relative to other passes comes from the per-feature order (1.4).
- **Point-of-line marker positions.** See 1.2.
- **Label placement for lines.** Missing; see 1.10.
- **Default hatch values.** The hatch table gives multiplicities of 0..1 but no defaults, so the angle and distance of a hatch are undefined when omitted. Not used by any case.
- **Stipples.** The text leaves the dot size and arrangement to the renderer. Not used by any case.
- **`em` unit.** Listed in the units enumeration but not defined. Not used.
- **Casing dash patterns.** The casing `StrokeStyling` has no dash pattern. Casings are drawn solid.
- **Case 14, `zOrder: z_order`.** This is a property of the data (`z_order`), which is undefined in the text as a bare identifier in JSON. I read it as `{ "property": "z_order" }`, as the JSON does.

## 4. Summary of key checks

- Case 01 and case 02 render the same white 3 px road, because the second rule overrides the first (1.3). I think this is what the text says.
- Case 18 Piers gets a white dot at the centroid (1.1). The Harbour dot is 8 px and its label sits 16 px below it.
- Case 16 shows roads at 50 % opacity over a green zone, without the zone being redrawn in pass 1 (1.4).

## 5. Rendered cases

| Case | What the renderer draws |
|---|---|
| case-01 | Roads as white 3 px lines; the black 5 px stroke is overridden by the white one (1.3). |
| case-02 | Same as case-01: two sibling rules, the second overrides, so only the white 3 px line shows. |
| case-03 | Roads drawn in two feature passes: black 5 px, then white 3 px on top of each road. |
| case-04 | As case-03 with black 12 px and white 8 px. |
| case-05 | Two viz passes on Roads: black 5 px across all roads, then white 3 px across all roads. |
| case-06 | As case-05 with black 12 px and white 8 px. |
| case-07 | Roads white 3 px with a 1 px black casing, so the dark edge is 5 px wide in total. |
| case-08 | Zones light grey with the default black 1 px outline; roads as in case-05, black 5 px then white 3 px. |
| case-09 | Viz pass 0: black 7 px then white 5 px per road by feature pass; viz pass 1: red 1 px on top. |
| case-10 | Roads grey 4 px (zOrder 0); rails black 2 px on top (zOrder 1). |
| case-11 | Roads yellow 10 px with a 1.5 px brown casing and a 1 px brown centre line. |
| case-12 | Three viz passes: brown 13 px, yellow 10 px, brown 1 px centre line. |
| case-13 | Viz passes black 12 px then white 8 px; bold 11 pt labels with the road names at the midpoint of each line, drawn last. |
| case-14 | Roads yellow 8 px with 1 px casing; rails dark 3 px at zOrder from `z_order`; bridge rails (feature pass -1) white 9 px with dark casing. |
| case-15 | Roads yellow 8 px with 1.5 px casing; rails white 3 px dashed 6 px / 6 px with dark 1.5 px casing. |
| case-16 | Zones green fill with default black 1 px outline; roads black 12 px then white 8 px at 50 % opacity. |
| case-17 | Building plan (German B-Plan): coloured fills and outlines by zOrder from `abs(ebene)`, metre-based widths; SVG pattern fills skipped and vendor properties ignored (section 2). |
| case-18 | Harbour as an 8 px dark dot with the label "Harbour" 16 px below it; Piers grey with a 1.5 px outline and the default white dot at the centroid. |

## 6. Files read outside this folder

Files read outside this folder: none.

The libraries I import (numpy, Pillow and shapely) load their own files at import time, and Pillow loads its bundled default font for the labels. I did not open any of those files myself.
