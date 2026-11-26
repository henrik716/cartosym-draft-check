# Notes: rendering 18 cases from the CartoSym 2.0 Part 1 draft text only

Renderer: `renderer/render.py` (numpy, Pillow, shapely, resvg-py for the SVG images; run `uv run --no-project --with numpy --with pillow --with shapely --with resvg-py python renderer/render.py`). Output: `out/case-NN-1.png`, 18 images, all at the `width` x `height` of the view. `renderer/sheet.py` only makes a contact sheet.

How it works, in one paragraph: geometry is transformed to pixel space (ground metres per pixel = `pixelSize_mm` x `scaleDenominator` / 1000, which equals bbox width / image width in every case). For each visualization pass, for each layer, feature and feature pass, the styling rules are applied in order (nested rules after their parent, later properties override earlier ones, an object replaces the earlier object unless it has `"alter": true`), giving one symbolizer. These "items" are sorted by `zOrder` (stable). Per `zOrder`: all casings, then each item's fill, stroke and marker, then all center lines. Labels are drawn last. Anti-aliasing: 4x supersampling.

## Choices where the text leaves the result open

Format per entry: id / place; the words that leave it open; readings; chosen; words relied on.

### C1. Which passes exist, and do rules without a pass selector repeat in every pass? (cases 8, 16, 13, 9, 12)
- Where: clause 7 "Visualization Rendering Passes", `viz.pass`, `feature.pass` (clause 8 "Feature Rendering Passes"), Annex C painter's algorithm comment.
- Words: "A later pass will only begin after all data layers and their features / coverage cells have been rendered with the symbolizers set for earlier visualization passes." Nothing says how many passes there are, nor what a rule without a `viz.pass` selector does in pass 1, 2, ...
- Readings: (a) the set of passes is not defined at all; (b) passes are the integers named by the style's selectors; (c) a rule without a `viz.pass` selector applies in every pass; (d) such a rule applies only in the first pass.
- Implemented: (b) plus pass 0 always (the numbers `=`-compared with `viz.pass` or `feature.pass` anywhere in the style, in increasing order; no gaps filled) and (c). So in case 8 and 16 the Zones polygon is drawn again in pass 1, over the black first-pass roads, which hides the black road casing inside the zone. Env `PASSMODE=first` implements (d) (not used for the delivered images).
- Relied on: "Setting up symbolization rules for a selector on a visualization pass allows to render all data of the map using different set of symbolizers" and the selector requirement `/req/core/selector` ("applying the Symbolizer ... only if the rule has no selector or if its selector evaluates to true").
- Also open: expressions like `viz.pass = 4 * z_order + 0` (Annex C) have no enumerable pass set; not needed by these cases.

### C2. feature.pass negative values and how a feature without a selected pass rule is drawn (case 14)
- Where: Annex C "Z-ordering and feature rendering passes" (`[feature.pass = -1]`), clause 8.
- Words: `feature.pass` is "Current rendering pass for the same feature"; no range or start value.
- Readings: passes start at 0 and -1 is invalid; passes run from the smallest named value (-1) to the largest, and every pass draws the feature with whatever the rules give.
- Implemented: second. In case 14 a non-bridge rail is drawn in pass -1 and in pass 0 with its base stroke (identical, so invisible), a bridge is drawn in pass -1 as white 9 px with casing and then in pass 0 as the 3 px dark line on top.

### C3. Order of feature passes against passes and layers (cases 3, 4, 9)
- Where: clause 7 painter's algorithm comment (in a `////` comment block, so informative at best) and Annex C comment.
- Words: "For each viz.pass: For each distinct zOrder: (if applicable, for each built-in Casing pass:) For each data layer: For each feature / cell: For each feature.pass".
- Readings: the pseudocode is normative, or only a comment.
- Implemented: that nesting. So with feature passes (case 3) each road gets black then white before the next road, and the roads do not merge at crossings (the later road's black cuts the earlier road's white); with viz passes (case 5) the roads merge. The pseudocode is inside a comment block in the text: the order is only stated there, and the tables below it say it loosely ("before rendering next data point").

### C4. Casing, center line, and zOrder grouping (cases 7, 11, 14, 15)
- Where: `/req/casing/casing`, `/req/casing/center`.
- Words: "drawing, within a single visualization pass, the casings of all features with the same `zOrder` beneath the main strokes of all those features".
- Open: whether this also applies across feature passes and layers; whether fill/marker are before or after casings; whether the casing follows `dashPattern`; whether the casing is under the previous zOrder's content.
- Implemented: within a viz pass and one zOrder: casings of all items (all layers, all feature passes) first, then each item's fill, stroke and marker in order, then all center lines. The casing is always a solid line along the whole geometry (the casing is a StrokeStyling, which has no `dashPattern`), width = stroke width + 2 x casing width (stated in the requirement). Casing and center line ignore the Symbolizer opacity grouping (they are painted with the symbolizer opacity as an alpha factor).
- Case 15: with a dashed main stroke the solid casing shows in the gaps (white dashes on a dark 6 px band). A reading with dashed casing is equally possible.

### C5. Default values (cases 8, 14-18, all)
- Where: `cscss-default-values` and `/req/core/default-values`. This clause is in the CSS encoding section but `/req/core/default-values` makes it binding for renderers.
- Words: stroke default 1 px black, fill default white, zOrder default 1, default marker is a Dot 10 px white at every vertex/centroid. "A style that sets no marker therefore draws a Dot at each point, at each vertex of a line and at the centroid of each polygon."
- Implemented as stated. Consequences: Zones (case 8, 16) get a 1 px black outline; the Piers polygon in case 18 gets a white 10 px Dot at its centroid (visible as a white dot); case 10's two layers have different zOrder, so the view's layer order is overridden. The default marker on lines is drawn at every vertex.
- Open: whether the default zOrder 1 and a data-driven `zOrder` should also order layers; I used one global order by zOrder, then layer order (as in the view), then feature order.

### C6. Pattern fills (`fill.pattern` with an Image graphic, case 17)
- Where: JSON schema only (`fill.pattern`, `stroke.pattern` as `graphic`). Part 1 text contains no requirement for image pattern fills, tiling, `transform`, `scaling`, `patternGap`, `patternInitialGap`. The Image requirement says an image is drawn "at its own size, one pixel of the image to one pixel of the map".
- Open: tile origin, tile size, whether a Fill color under the pattern is painted, what `scaling: [3.0, 3.0]` means.
- Implemented: the tile is the SVG rasterised at its own width/height (150 x 150 px etc.) times the scaling factor, tiled from the map's top left corner (the hatch requirement says one pattern aligned with the map, "a line through the top left corner of the map"; I reused that for images), no color painted under the pattern (hatch/dot pattern/stipple requirements say "without painting the area between"; the SVG may itself have an opaque background such as the white rect in the Verkehrsflaeche SVG). Tile period is rounded to whole supersampled pixels.
- Relied on: `/req/vector/image`, `/req/hatches/hatch`, `/req/dot-patterns/dotpattern`.

### C7. Meaning of `scaling` without a unit (case 17)
- Where: clause 16 table "Units of measure abbreviations", row (none): "For relative values like scaling, 100 times less than if _pc_ is specified."
- Words: "100 times less than if pc is specified" does not say whether 3 means 3 (x3), 0.03 or 300 pc.
- Readings: factor 3; factor 0.03; factor 300 pc = 3.
- Implemented: factor = number / 100 (3 -> 0.03, a 4.5 px tile from a 150 px SVG). The factor-3 reading gives 450 px tiles (and stamps larger than the map), which cannot be meant for a 1:2000 plan. This is the weakest choice of case 17 (the sentence is also self-contradictory: "pc" 3 would be 0.03, "100 times less" than that is 0.0003). A text that said "1 = 100 pc" would settle it.

### C8. Stroke patterns along lines, `patternGap`, `patternInitialGap`, rotation (case 17)
- Not defined in Part 1 text (only `stroke.pattern` in the schema). Implemented: the image (scaled as C7) is stamped, centered (default hotSpot `50 pc 50 pc`), at distance `patternInitialGap`, then every `patternGap` (ground metres converted with the scale) along each line of the feature, not rotated.
- Vendor properties (`vendor.xleitstelle.offset`, `.placements`, `.rotate`, `.trim`): the text only says vendor extensions are prefixed `vendor.<name>`, with no meaning. Ignored (lines are not offset or trimmed, stamps not rotated).

### C9. `join`, `cap` (case 17) and round caps with dashes (case 15)
- Where: Part 1 text says "The ends of open lines are drawn with round caps, and their vertices with round joins (the Joins and Caps requirements class of Part 2 adds properties to choose other caps and joins)". `/req/vector/stroke` requires round caps and joins. The case 17 style uses `join: miter`, `cap: butt/square`.
- Choice: honoured `cap` and `join` when present (miter limit 4, an SVG default I assumed), default round. A strict reading of Part 1 would ignore them.
- Dashes: each dash is drawn with butt ends (so a 6 px dash is 6 px long). The requirement for round caps is about "open lines"; with round caps on dashes the 6/6 dashes of case 15 would be 9/3. Left open in the text.

### C10. Dash pattern details (cases 15, 17)
- Where: `/req/dashes/dash-pattern`, `/req/dashes/dash-offset`.
- Words: "alternating a long dash with a short gap"; odd-length arrays and zero-length dashes not specified.
- Implemented: even index = dash, odd = gap; an odd-length array is repeated twice (SVG rule, not in the text); dash of length 0 draws nothing (so `[0, 5]` in `SO_Denkmalschutzrecht` draws nothing; with round caps it would be dots). Pattern restarts at the start of each line, continues across vertices (stated). For polygons each ring is one line starting at its first vertex.

### C11. Opacity grouping (cases 16, 17)
- Where: `/req/core/opacity`, `/rec/core/opacity-together` (a recommendation) and its note ("Which of these to recommend is still under consideration").
- Readings: per feature, or all features of a layer and zOrder at once.
- Implemented: per item (feature x pass): fill, stroke and marker of one item are composited as one group at the symbolizer opacity; casing and center lines are painted separately with the opacity as alpha. In case 16 each pass is a separate draw, so the black 50 % roads get the white 50 % road over them, giving gray-white road bodies. The "all at once" reading would make crossing roads of one pass not show through each other; I did not do it.

### C12. Labels: position on a line, orientation, collisions, one label for several passes (case 13, 18)
- Where: `/req/labels/label`, `/req/vector/text`, `/rec/labels/overlap`, placement requirement.
- Words: "drawing the graphical elements of the labels as a separate pass on top of all styled vector features"; nothing says where on a line (or polygon) the Label graphics' origin is.
- Implemented: anchor = point at half the length of the line (centroid of the longest part for Multi); polygons: `representative_point`; points: the point. No rotation along the line. The label belongs to the feature once, taken from the symbolizer of the last pass evaluated (in case 13 the Label is set at the root of the rule so it is the same in every pass). Labels are placed in feature order (higher `priority` first, default 0); a label whose text box overlaps an already placed one is omitted (the recommendation says SHOULD). Labels reaching outside the map are drawn (clipped), as the NOTE leaves it open. `minSpacing`/`maxSpacing` repetition: not implemented (no case uses it).
- In case 13 the three labels are the roads' own (unmerged) per-feature labels; Road 1 and Road 2 labels nearly touch at the crossing but their boxes do not overlap.

### C13. Font size and font face (cases 13, 18)
- Where: `/req/vector/fonts`: "a `size` specified in _points_", clause 16 units: "One point is equal to 1/72 inch (0.3528 mm)".
- Open: the pixel size of a point with a 0.28 mm pixel (pt x 25.4/72/0.28 = 1.26 px; a 96 dpi screen would give 1.33 px). Implemented 1.26 (the pixel size in the view). So 11 pt = 13.9 px, 16 pt = 20.2 px.
- Face: "Arial" and "sans-serif" are names with no font file in the folder; I used the font that ships with Pillow, so glyph shapes and widths do not match Arial. `bold` is done by thickening the outlines by 1/3 px (the default font has no bold). A different font changes label extents (and so the overlap decisions).
- Text alignment: "top of the font's ascent", "bottom of its descent", "middle ... halfway between" implemented with the font's ascender/descender lines. Default `left top` (case 18, label at +16 px below the dot: the text top is 16 px under the dot centre).

### C14. Dot with stroke object (case 18)
- Where: `/req/vector/dot`: size and color are "the same values as the `width` and the `color` of its stroke". Case 18 gives only `stroke` {width 8 px, color}. Implemented: filled circle with diameter 8 px (the `width`) and the stroke color; no outline (the permission `/per/vector/dot-outline` is not used).
- Marker `position` offset: `[{px:0},{px:16}]` is used by the Label's text element (offsets down 16 px). Positive y downward (stated).

### C15. Marker on polygons/lines (case 18 and default marker)
- `/req/vector/marker`: "at the points of vector geometry (for points and line strings) and at the centroid of polygons". For a polygon I use the centroid (for a concave polygon the centroid can be outside the polygon). Polygon rings' vertices not used. For a Multi geometry: every member.

### C16. Selector semantics with nulls and the `dataLayer.id` / `viz` names (all cases)
- The JSON uses `sysId` values `dataLayer.id`, `viz.pass`, `feature.pass`, `dataLayer.featuresGeometryDimensions`. The class diagrams in clauses 7 and 8 call them `dataLayer.identifier`, `visualization.pass`, `feature.pass`, and the table in clause 8 has both `feature.geometryDimension` and `featuresGeometryDimensions` (spelled with an `s` in the diagram, without in the table). I map `viz`->`visualization`, `id`->`identifier` and treat `featuresGeometryDimensions` as the layer dimension (2 for polygon layers, 1 lines, 0 points, null mixed) as the schema's enumeration in the JSON lists `dataLayer.id` and `viz.*`.
- A selector that evaluates to null does not select (stated in the NOTE of `/req/core/selector`); comparisons with null are null; `and`/`or` use three-valued logic (CQL2 behaviour, not in the text).
- Property names containing dots (`zweckbestimmung.0` in case 17): the text has no rule for them. I look up the full name first, then follow `.` as nested key or array index. With this reading `zweckbestimmung.0 = '4000'` selects the Kennzeichnung feature. Property values that are arrays are compared with `=` only after indexing.
- `zOrder` as an expression (case 17): evaluated per feature; NULL -> 0 (table in `/req/parameter-values/null`); the style uses `?:`, `isNull`, `abs`: not defined in Part 1 clauses I read beyond the operator list; I implemented them in the usual way.

### C17. Replacing versus merging nested symbolizer objects (cases 1, 2, 14)
- Words: "Symbolizers will inherit from and override the parent StylingRule's Symbolizer"; "/req/json/partial-update ... with `alter` set to true" merges; without `alter` the CSS example says "completely replace stroke property".
- Implemented: an object without `alter` replaces the property of the parent entirely; members it omits then get the class defaults (stroke color black, width 1 px, ...). In case 1 and 2 the later rule (white 3 px) overrides the black 5 px: only a white 3 px line shows. This is the most natural reading but case 1 and 2 are exactly what a style author would not want.

### C18. Rendering of line strokes at feature level versus feature union (cases 1-6)
- Strokes of one feature are drawn as one geometry (union of buffered parts), so a self-overlapping line is not doubled for opacity.

## Things used but not defined, or contradictory

- `sysId` names differ between diagram and schema (C16). `featuresGeometryDimension` (singular in the table) vs `featuresGeometryDimensions` (plural in the diagram, the schema and the style).
- `/req/vector/graphics` says position is "uom-qualified 2D"; JSON in case 13 gives `alignment` as a two-element array `["center","middle"]`, whereas clause 8 defines `horzAlignment`/`vertAlignment` members. I accept both forms.
- `zOrder` default 1 (clause 7 default table) but `/req/parameter-values/null` gives NULL zOrder -> 0 and the JSON schema comment says nothing: a layer with no `zOrder` sits above a layer with `zOrder: 0` (case 10 uses this deliberately, Roads 0, Rails 1).
- `join`, `cap`, `pattern`, `patternGap`, `patternInitialGap`, `transform.scaling`, `vendor.*`: used by case 17, not required anywhere in Part 1.
- The pass pseudocode is inside a `////` comment block (C3); the tables near it describe the same order more loosely.
- "Opacity does not apply to labels" is in a NOTE of `/req/core/opacity`; label opacity from the Font `opacity` only.
- Stroke `opacity` and Fill `opacity` multiply with the Symbolizer opacity (stated in `/req/core/opacity`).
- Not implemented (no case needs them): hatch, dot pattern, stipple fills; Image graphics (`Image` marker); coverages and hill shading; `$variables`, `$include`; label spacing; font outlines.
- `dashPattern` with CSS encoding `5, 5` in Annex C vs `[ 6 px, 6 px ]` in cases: only the JSON was read.
- Coordinate systems: the layer files and the view are in the same CRS in all cases; no reprojection is done.

## Per-case summary

| Case | What the renderer draws |
|---|---|
| 01 | Nested rules without selectors: the later white 3 px stroke replaces the black 5 px: a single white 3 px line per road |
| 02 | Two top-level rules, same selector: the later one wins, white 3 px roads only |
| 03 | Feature passes 0/1 per road: black 5 px then white 3 px, each road in turn, so crossings are cut by the next road's black outline |
| 04 | As 03 with 12 px black / 8 px white: wide roads with visible cuts at the crossings |
| 05 | Visualization passes 0/1: all black 5 px roads, then all white 3 px: merged crossings (cased roads) |
| 06 | As 05 with 12/8 px |
| 07 | Built-in casing: white 3 px stroke with 1 px black casing each side (5 px total), crossings merged |
| 08 | Zones gray fill (+ default 1 px black outline) in both passes; roads black 5 px then white 3 px in passes 0 and 1; the zone is re-drawn in pass 1 over the black road, so inside the zone only the white 3 px roads show (C1) |
| 09 | Pass 0: per road black 7 px, white 5 px (in turn); pass 1: red 1 px centre line over all |
| 10 | Roads gray 4 px (zOrder 0) under the black 2 px rail (zOrder 1), although the view lists Rails first |
| 11 | Yellow 10 px roads, 1.5 px brown casing, 1 px brown center line on top of all roads |
| 12 | Three viz passes: brown 13 px, yellow 10 px, brown 1 px centre: cased roads with a centre line |
| 13 | Black 12 px / white 8 px roads (two passes) with the road names (bold 11 pt, centred at the middle of each line, horizontal), drawn last |
| 14 | Roads yellow 8 px with 1 px casing (zOrder 1); rail 3 px dark (zOrder from `z_order`); the bridge (zOrder 2) drawn over the road as a white 9 px strip with dark casing and the dark 3 px rail on it |
| 15 | Roads yellow 8 px with 1.5 px casing; rail as white 3 px dashes (6 px on, 6 px off, butt ends) over a solid dark casing band (6 px) |
| 16 | Green Zones polygon (+ default outline), roads at 50 % opacity: black 12 px then white 8 px per pass; the zone is re-drawn in pass 1 (C1), so black roads show only outside the zone |
| 17 | German plan: yellow/purple/orange areas, 1:2000, 0.2-0.3 m outlines, SVG hatch fills (scaling number / 100), dashed lines, stamped line symbols, no vendor offsets (C6-C10) |
| 18 | Piers polygon fill gray with 1.5 px blue-gray outline plus the default white 10 px dot at its centroid; harbour dot dark blue 8 px; label "Harbour" bold 16 pt below it (left/top at +16 px) |

## Files read outside this folder

none
