# Notes: places where the Part 1 text left a choice open

Renderer: `renderer/render.py` (Python, numpy + Pillow + shapely; 4x4 supersampling). Images: `out/<case>-<N>.png`, 21 images for the 20 cases (`vector-units` has view-1 and view-2).

Format of each item: identifier, the words that leave it open, readings considered, what I implemented. "(C)" marks a contradiction between two places in the text, "(U)" a term used but not defined, "(O)" an open choice.

## A. Rules, symbolizers, expressions

**A1. Features that no rule selects (O). `/req/core/symbolizer`, `/req/core/default-values` and its NOTE.**
Words: "using the default values for properties not set by any selected rule"; "so that every feature is visible by default".
Readings: (a) a feature that no rule selects (or whose rules set nothing) is still drawn with the all-default symbolizer: white fill, black 1 px stroke, white 10 px Dot at the point, vertices, or centroid; (b) a feature that no rule selects is not drawn.
Implemented (a), following the NOTE literally. Consequence: in `core-opacity` every non-lake Landcover polygon is drawn as a white polygon with a black outline.

**A2. Which default properties apply to which geometry type (O). `/req/core/default-values`, `/req/vector/fill`, `/req/vector/stroke`.**
Words: "fill: default Fill", "stroke: default Stroke"; nowhere says fill is ignored for lines/points or stroke for points.
Implemented: fill only on polygons; stroke on line strings and polygon rings (exterior and holes), not on points (the marker draws points).

**A3. Order in which nested rules override later sibling rules (O). `/req/core/rules`, `/req/core/nested`.**
Words: "rules selected later override earlier ones"; "nested rules ... inherit from and override the parent".
Readings: (a) depth-first: a nested rule is evaluated straight after its parent, before the next sibling; (b) all rules of one level first, then nested ones; (c) the nested rule's position is the position of the parent.
Implemented (a). Only matters when a later sibling and an earlier sibling's nested rule set the same property.

**A4. Replace versus merge when `alter` is absent (O). `/req/json/partial-update`, `/req/core/instances`.**
Words: "set an object property with a complete new instance, or specifically override a particular member"; JSON: an object "with `alter` set to true" is a partial update.
The text never states in a requirement that an object without `alter` replaces the whole earlier value including members not mentioned (it only says so in the CSCSS example comment "completely replace stroke property"). Implemented: no `alter` means full replacement, members not given take class defaults (e.g. `"stroke": {"width": 0.0}` has color black). This also drops `casing`/`dashPattern` set by an earlier rule.

**A5. Identifier names (C). Clause 7 System Identifier tables, `/req/core/layers`, `/req/core/time`, JSON schema `systemIdentifier.sysId` enum, clause 8 table.**
Words: text and UML say `dataLayer.identifier`, `visualization.scaleDenominator`, `visualization.dateTime`, `feature.identifier`, `feature.geometryDimension` (singular in the table, plural in the UML); the JSON schema only allows `dataLayer.id`, `viz.sd`, `viz.dateTime`, `feature.id`, `feature.geometryDimensions`; CSCSS text uses `viz.sd`. The table row `visualization.timeInterval` is defined as "Current visualization time of day" (copy error). The `timeInterval.start.date` path used in the cases is only in the schema enum; in the UML `timeInterval.start` is a TimeInstant with `date` and `time`.
Implemented: accept both spellings and walk the Visualization class structure.

**A6. Comparing a text property with a Date, Date with DateTime (U). `/req/core/time`, `/req/core/relational`.**
Words: the relational operators say "first operand is smaller/greater..." with no type rules. `validDate` is a text property; `viz.timeInterval.start.date` is a Date; the view gives the interval as dates only, while TimeInterval is defined with TimeInstants.
Readings: (a) coerce an ISO text to a date when the other operand is a date; (b) comparison of text with Date is null/false; (c) compare as strings.
Implemented (a). Date vs DateTime: the date gets time 00:00:00. A missing time of day in the view's interval is taken as 00:00:00 (so the end date is an instant at midnight, and a feature dated exactly on the end date is included by `<=`).

**A7. Null and boolean logic (U). `/req/core/operations`.**
Words: "evaluating operation expressions with a null operand as specified by CQL2." CQL2 is not part of the text. Implemented SQL three-valued logic (null and false = false; null or true = true; otherwise null); a missing property is null; a selector that evaluates to null does not select (per the NOTE). Comparison `property = true` for a missing property is therefore not selected.

**A8. `zOrder` (C)/(O). `/req/core/z-order`, "Visual Ordering Constructs" table, UML comment.**
Words: `zOrder` is an "integer" in the requirement and "float" in the Visual Ordering table; the UML comment says "needs discussion on whether it should be relative or float". "features and coverage cells of a single rendering pass in increasing order".
Open: (1) whether zOrder orders across layers or only within a layer; (2) order of features with equal zOrder; (3) order of layers (not in the standard; I used the view's `layers` order).
Implemented: sort all features and coverage layers of all layers together by (zOrder, layer order in view, feature order in file). Float values accepted. Default 1. In `core-z-order` the zOrder values agree with the layer order, so the case does not discriminate.

**A9. Parameter values: which requirement classes are assumed (O). `/req/core/parameters`, `rc-parameter-values`, `rc-arithmetic`, `/req/vector/text` footnote.**
Words: without the Parameter Values class only literals are allowed. Cases use property references (text, label priority) and arithmetic (`core-parameters`). I assumed Parameter Values and Arithmetic are supported. The names in `rc-arithmetic` (`add`, `sub`, `div`) are not mapped to the JSON operators (`+`, `-`, `/`) anywhere in the text; the mapping is in the schema enum only. `/` is real division (stated).

**A10. Negative or zero computed sizes (U). `/req/parameter-values/null`, `/req/vector/dot`.**
`core-parameters` computes `(elevation - 900) / 100`; the data has elevations below 900 (878), giving a negative diameter. The text defines only NULL results (0 for numbers), not negative values. Implemented: size <= 0 draws nothing. Alternative: clamp to 0 (same result) or take the absolute value.

**A11. Capability identifiers (U).** `capabilities.*` all return true in my renderer; not used by the cases. The text does not say whether the vendor/optional `per`mission classes (dash lengths in percent) count as supported.

## B. Vector styling

**B1. Where the stroke is relative to the geometry, joins and caps (O). `/req/vector/stroke`, clause 8 "Strokes".**
Words: "By default the end of open subpaths are butt caped and at the corners of paths are miter joined"; nothing on position.
Implemented: stroke centered on the line / polygon boundary (half inside, half outside), each ring of a polygon stroked (holes too), butt caps, miter join. No miter limit is given; I used 4 (SVG default) and bevel beyond it. Alternative: no limit.

**B2. Stroke `width` 0 (U).** `"stroke": {"width": 0.0}` (`vector-marker-dot`). Readings: hairline of one device pixel, or nothing. Implemented nothing (the table for NULL also maps to 0 but does not say what a 0 width draws).

**B3. Units (C)/(O). `/req/vector/units`, "Graphical Units of Measure", CSCSS "Units of measure abbreviations", JSON `unitValue`, `/req/dashes/dash-pattern`.**
Words: the list of units differs: `/req/vector/units` lists "pixel, millimeter, inch, percentage, meter, foot"; the UML enum has pixels, meters, feet, percent, points, em, screenInches, screenCM, screenMM; the dashes requirement lists "pixels, points, millimeters, centimeters and inches"; the CSS table abbreviates inch as `inch`, the JSON schema uses `in`. `pc` ("percent") is "Relative value whose meaning depends on context" without saying what it is relative to for widths and distances. A bare number in the JSON: "defaults to pixels" for screen-space objects, but for "relative values like scaling" it is "100 times less than if pc is specified".
Implemented: `px`, `mm`, `cm`, `in`, `pt`, `m`, `ft` for lengths, bare number = pixels. `pc` for lengths: not defined, treated as percent of 0 (not used by the cases; used for `hotSpot` only, see B9). `em`: font size.
Pixel size: 0.28 mm from the view (`pixelSize_mm`), as the text says it is the default size. 1 pt = 1/72 inch = 0.3528 mm = 1.26 px.
Ground units: metres converted with metres per pixel = scaleDenominator x pixelSize (0.28 mm). The text does not say whether to derive the ground size of a pixel from the scale denominator or from the bbox and image size (equal in all cases) nor how to treat the projection scale factor (ignored).

**B4. Marker anchor points (O). `/req/vector/marker`, NOTE of `/req/core/default-values`.**
Words: "at the points of vector geometry (for points and line strings) and at the centroid of polygons".
Implemented: Point: the point; LineString: every vertex (the NOTE says "each vertex of a line"); Polygon: area centroid (may fall outside a concave polygon or inside a hole; the alternative would be a point inside the polygon); MultiPolygon: one per part (alternative: one for the whole feature); MultiPoint: every point. At each anchor all elements are drawn in array order (alternative: all anchors for element 1, then element 2).

**B5. Marker `elements` multiplicity (C). MultiGraphic table "1..*" versus NOTE "empty list of elements unsets it", UML `[0..*]`.** Implemented per NOTE: `elements: []` and `marker: null` draw nothing; `marker: {}` draws the default Dot.

**B6. Direction of Graphic `position` (U). `/req/vector/graphics`; `UnitPoint` table.**
Words: "uom-qualified 2D real position offsetting the graphic from its original position"; x "Horizontal position", y "Vertical position". Nothing says whether positive y points up (map/mathematics) or down (screen/image, as `hotSpot` seems to be). Implemented: y positive downwards (screen). The apparent intent of the test cases (an elevation text at `y: -6` with alignment `center top`, a label at `y: 8`) suggests the opposite for at least one of them, but the text does not say.

**B7. Dot (O). `/req/vector/dot`.**
Words: "filled circle whose diameter is its size". Default size 10 px, default color white. Opacity of the Graphic (`opacity`) multiplies with the symbolizer opacity. Dot `stroke` other than width and color (opacity, casing) ignored. "the value set last applies to both": with partial updates (`alter`) across rules there is no defined way to know which of `size` and `stroke.width` was set last. I do not track it; if both appear in the resolved element, `size` wins (JSON `req-json-dot-size-color` forbids both only within one rule).

**B8. Images (O)/(U). `/req/vector/image`, Image/Resource tables.**
- Size: the Image has no size property. Implemented: native pixel size, one image pixel = one map pixel, regardless of pixel size; no resampling (the top-left corner is rounded to a whole pixel).
- Resource: the text says `url` and `path`; the JSON schema says `uri` and `path`. The case has both `uri` (http://example.com/...) and `path`. Implemented: `path` only, relative to the case folder (the text says "(preferably relative) path" but not relative to what); the URL is never fetched. Also looked in `icons/` and `../icons/`.
- `type`, `ext`, `id`, `sprite` ignored.
- `alphaThreshold`: only a permission (`/per/vector/image-alpha-test`); not applied.
- Tint: formula given: `tint x v + blackTint x (1 - v)` per color component, applied to non-premultiplied color; alpha kept. Colour range of `tint` (0..1 vs 0..255) see B10.

**B9. `hotSpot` (C). Image table: "0,0 position in the image"; default "center of the image ({ 0.5, 0.5 })"; CSS unit table "(none): ... 100 times less than if pc".**
Open: origin and meaning of a bare number. Implemented: origin top-left, y downward; `pc` = percent of the image width/height (so `[50 pc, 100 pc]` is bottom centre); bare number = fraction of the image size (matches the default `{0.5, 0.5}`); `px` etc. = absolute offset from the top-left corner. This conflicts with the rule that a bare number is pixels in other places.

**B10. Color component range (C). `/req/coverage/color-channels` "each in the range 0 to 1"; Color class `r, g, b: float` without range; JSON schema `color` components 0 to 255 (integers), `color0to1` for `colorChannels`; named color table in 0..255; `tint` formula treats components as 0..1.**
Implemented: `Color` values written in the style (names, `#rrggbb`, `[r,g,b]`, `{r,g,b}`) are 0..255 and converted to 0..1; `colorChannels` is 0..1. `#rgb`/`#rrggbb` strings are accepted in JSON (the cases use them in colorMap; the schema only allows names, arrays, objects there). Color names are case-insensitive; table read from clause 17 (note `fuschia` spelling in the table and the schema).

**B11. Text graphics and fonts (O)/(U). `/req/vector/text`, `/req/vector/fonts`, Font and Text tables.**
- Font `size` is "(pt)" (points): converted with the 0.28 mm pixel (9 pt = 11.3 px); alternative 1 pt = 1 px. The em height of the font = size.
- Defaults for `face`, `size`, `color`, `opacity`, `bold`, `italic` are not defined anywhere. Implemented: Arial, 10 pt, black, opaque, regular. `underline` appears in the UML Font class only and is not implemented. A face name is not resolved by the text (substitution rules); Arial and Times New Roman files were used.
- Alignment names (C): TextAlignment table `horzAlignment`/`vertAlignment`; UML `horizontal`/`vertical`; JSON schema `hAlignment`/`vAlignment`, with a two-element array form (`["left","middle"]`) that is also used by the cases. All accepted. Default alignment (U): not defined; implemented center / middle.
- Meaning of `top`, `middle`, `bottom` (O): readings: (a) the anchor is at the top / middle / bottom edge of the text box (text lies below / centered on / above-ending-at the anchor); (b) the text lies above / on / below the anchor. Implemented (a). The text box is the font's line box (ascent + descent), not the ink bounding box, so the position does not depend on the characters. Horizontal: `left` starts at the anchor, `right` ends at it.
- Text content from a number (U): format not defined; implemented integers without `.0`, other numbers with Python's default text.
- Text opacity: the symbolizer opacity applies to Text graphics inside a marker (they are "graphics of markers") but not to labels (NOTE of `/req/core/opacity`).
- Glyph rendering (hinting, anti-aliasing, kerning, shaping) is not specified, so text cannot match pixel for pixel.

**B12. Font outline (O). `/req/font-outlines/*`.**
Words: "outline extending outward from the glyph contours by the thickness specified by the `size` property". Readings: the outline band is `size` wide (extends `size` px) or `size` is the total stroke width (extends size/2). Unit of `size` is not given (the schema has a bare number). Implemented: extends `size` pixels outward, bare number = pixels, round joins (join style not specified). The outline shape is drawn as glyph plus halo beneath the glyphs (so it is visible only outside the glyphs when the glyph is opaque); its `opacity` multiplies on its own, and `font.opacity` applies to the glyph only. Outline color default black.

## C. Fills

**C1. Hatches (C)/(O). `/req/hatches/*`, Hatch table, TODO(review) after it.**
- Angle direction (C): table "orientation clockwise degree" versus the TODO comment saying it should probably be counter-clockwise like other angles. Reference direction of 0 is not given. Implemented per the table: 0 degrees = horizontal lines, increasing clockwise on screen (45 = lines running from top-left to bottom-right, 90 = vertical).
- `distance`: between consecutive lines; readings: center to center perpendicular, gap between edges, or measured along the x or y axis. Implemented center to center, perpendicular.
- Phase of the line family (U): not given. Implemented: one global family anchored at the map image's origin (pixel 0,0), not per polygon. A per-polygon origin would give a different picture.
- Color of the lines and the background (U): the Hatch class has no color. Implemented: lines in `fill.color` with `fill.opacity`, nothing painted between lines.
- `width`, `distance` are "float" in the table; unit-qualified in the schema; default unit pixels. Defaults taken from the figure caption (1 px, 45 degrees, 10 px).
- Lines are clipped to the polygon; hatch is drawn before the polygon outline.

**C2. Dot patterns (U). `/req/dot-patterns/*`, TODO(review) #84.** Size and color of the points, the grid origin and whether rows are staggered are undefined. Implemented: 2 px diameter dots in `fill.color`, orthogonal grid with horizontal spacing and vertical spacing, points at (i x h + h/2, j x v + v/2) relative to the map image origin (global grid). `distance` can be an object or a two-element array (schema).

**C3. Stipples (U). `/req/stipples/ratio`, TODO(review) #84.**
Words: "Ratio of stippling dots according to area filled". Readings: fraction of the area covered by dots; fraction of grid positions that get a dot; number of dots per area. Dot size, arrangement (random or regular), and color undefined. Implemented: regular square grid of 2 px dots (fill color) with the cell size chosen so dot area / cell area = ratio (0.3 gives 3.2 px spacing). A random pattern would not be reproducible.

## D. Strokes: dashes, casing, center

**D1. Dash pattern and offset (O). `/req/dashes/*`, Dashes clause.**
- Pattern meaning: alternating dash, gap, ... starting with a dash. Odd-length arrays: not said; implemented as repeated twice (SVG). Units per element.
- `dashOffset` (O): "an offset on the rendering of the associated dash pattern"; figure caption "dash pattern preceded by an offset". Readings: (a) the pattern starts `offset` into itself (SVG/Cairo: positive offset shifts the pattern backwards along the line); (b) the line starts with a gap of `offset` before the first dash. Implemented (a). Negative offsets: modulo the pattern length.
- Where the pattern starts (U): at the first vertex in the order of the data, for each line string / each polygon ring separately, restarting for each part; the direction of digitisation therefore shows in the picture.
- Dash ends: butt caps; dash inherits the stroke's miter joins (joins computed per dash piece).
- Dash lengths in percent of the stroke width, or in meters/feet: permissions, not implemented.
- `dashOffset` is a "float" in the UML and "UnitValue" in the table; accepted as unit-qualified.

**D2. Casing (O). `/req/casing/casing`.**
- "extends the width of the casing beyond each side of the main stroke, for a total width of the main stroke's width plus twice the casing's width": implemented as a stroke of width (w + 2c) beneath the main stroke (so the whole body is under the main stroke; matters if the main stroke is translucent: reading (b) would paint only the two side bands).
- A casing "along the same geometry as the stroke": when the stroke is dashed, is the casing dashed? StrokeStyling has no dash pattern; implemented: casing and center line solid.
- "within a single visualization pass, the casings of all features with the same zOrder beneath the main strokes of all those features": implemented: for each zOrder value, first all casings (all layers), then everything else (fills, strokes, center lines, markers) of that zOrder. This puts casings below fills and markers of other features with the same zOrder; the text only says beneath the main strokes. Casings of the same color and opacity are merged into one shape so that translucent casings are not painted twice where they overlap; casings of different styles are drawn in order of first appearance.
- Casing of polygon outlines: drawn for rings the same way.
- Defaults for a missing casing color/width/opacity: not defined; I used the stroke defaults (black, 1 px, 1).
- `center` (C): text says `center`, JSON schema says `centerLine` (TODO(review) #120). Both accepted. The center line is drawn directly on top of its own feature's main stroke, before the next feature (not at the end of the pass).

## E. Coverages and hill shading

**E1. Which cell covers a pixel and how coverage is resampled (O). `/req/coverage/*` "portraying each coverage cell".**
Implemented: nearest cell at the pixel center (no interpolation between cells); ASCII grid `xllcorner`/`yllcorner` are the lower-left corner of the lower-left cell (stated by the file format, not by the text); NODATA and pixels outside the grid are transparent (background shows). Alternative (bilinear smoothing) would give a different picture when the pixel is smaller than the cell, as here (2 x 2 pixels per cell).

**E2. Color map interpolation (O). `/req/coverage/color-map`, `/rec/coverage/map-interpolation` and NOTE.**
The text says "interpolating between the colors of the two closest entries" and NOTE "The interpolation method is not specified: linear interpolation, or a smoother one, can be used". Implemented: piecewise linear interpolation of the red, green and blue values of the colors (0..1, as encoded, i.e. not in linear light), clamped to the first/last entry. Entries are sorted by value (not required to be sorted by the text). The opacity map likewise. Color space of the interpolation (sRGB-encoded versus linear light, Lab) is not specified.

**E3. Alpha combination (U).** Final opacity of a cell = opacityMap value x alphaChannel x Symbolizer opacity; composited over what is beneath. The text names the three channels but not how they combine.

**E4. Table errors in the coverage section (C).** The `ValueOpacity` table lists a `color` member instead of `opacity` and describes it as "Key value for selecting this color"; the UML names the legend text `label`, the tables `name`; the JSON encoding uses two- or three-element arrays `[value, color|opacity, name]`. Implemented the array form (`[value, color-or-opacity]`).

**E5. `singleChannel` default and gray (U).** Without a `colorMap`, `singleChannel` ("gray-scale output channel") is mapped as gray = clamp(value, 0, 1). The default-value table says `singleChannel` defaults to `fields[0]` for single-field coverages. `colorMap` without a `singleChannel`: undefined (not implemented beyond the default).

**E6. Coverage selectors and parameters per cell (limitation).** `/req/core/selector` says selectors apply per coverage cell. Implemented: the symbolizer of a coverage layer is resolved once per layer (selectors on cell values are not evaluated per cell); parameter-value expressions on `singleChannel`, `colorChannels` and `alphaChannel` are evaluated per cell. The cases need nothing more. `visibility` and `zOrder` and `opacity` are therefore per layer.

**E7. Hill shading: sample spacing and the gradient operator (O). `/req/hill-shading/hill-shading` and the NOTE.**
Words: "computing the terrain surface normal of each cell from the differences in elevation between neighbouring samples of the elevation coverage at the resolution being rendered, over the horizontal distance between those samples".
Open: (1) which samples, the coverage cells (150 m) or the output pixels (75 m, requiring resampling), "the resolution being rendered"; (2) which differences: forward/backward difference to one neighbour, central difference over two cells, or a 3 x 3 kernel (Horn, Zevenbergen-Thorne); (3) edges of the grid. Implemented: on the coverage cells; central differences (z[i+1] - z[i-1]) / (2 x cell size) in both directions; edge cells use a replicated border (so a one-sided difference over one cell). The NOTE that the same factor gives a stronger relief at finer resolution shows the result depends on this; all these choices give visibly different pictures.

**E8. Hill shading sun azimuth/elevation conventions (O). `/req/hill-shading/sun`.**
Words: "light source at the azimuth angle (in degrees clockwise from North, as a compass bearing) and elevation angle (relative to the ground)". Implemented: the vector towards the sun = (sin az cos el, cos az cos el, sin el) in (east, north, up); i.e. a sun at azimuth 315 lights slopes that face north-west. The reading "azimuth = direction in which the light travels" would flip it. `azimuth`/`elevation` may be a bare number (degrees) or a `{deg}`/`{rad}` object (schema).

**E9. Hill shading defaults (U).** `factor`, `sun`: no defaults defined. Implemented factor 1, sun azimuth 315 and elevation 45 (not used by the cases, which give both).

**E10. Hill shading formulas (O). `/req/hill-shading/hill-shading`, `/req/hill-shading/factor`.**
Normal = (-dz/dx, -dz/dy, 1) normalised; the horizontal components are multiplied by `factor` before normalising (for the unit normal or the unnormalised one the result is the same direction). Shade = clamp(n . s, 0, 1). The text defines this literally; a consequence is that flat terrain has shade sin(elevation) (0.5 at 30 degrees, 0.71 at 45), so the whole image is darkened relative to the colour map. I implemented it literally (no normalisation by sin(elevation)).
- Which band is the elevation (U): "the elevation coverage"; implemented: the band named `elevation`, else the first band.
- With a hillShading `colorMap` or `opacityMap`: implemented: the shade value (0..1) is looked up in them and replaces the Symbolizer's color/opacity map (the text says only "the color mapped from its computed shade value"); not exercised.
- Where the Symbolizer has `colorMap` on `singleChannel` and hillShading has none, the shade multiplies the colors from the Symbolizer's `colorMap` (stated: "multiplying the red, green and blue components of each cell by its shade value").

## F. Labels

**F1. What is a label placed at (U). `/req/labels/label`, Label overview.**
Anchors: Point: the point; Polygon: centroid (largest part of a multipolygon); LineString: positions along the line (see F3). Label elements are positioned relative to the anchor like marker elements (B6, B11). Label graphics are drawn after all vector features and coverages, over everything including markers (stated). Label rotation along lines (U): not specified; implemented horizontal, unrotated text centered at the anchor (curved text along the line is another reading).

**F2. Conflicts and priority (O). `/rec/labels/overlap`, `/req/labels/placement`.**
- "labels which cannot be placed without overlapping other labels": overlap means the bounding boxes of the label elements (text box including outline) overlap; touching is allowed; markers, lines and other features are not obstacles. Placement is greedy in descending priority; equal priority: drawing order (A8).
- Priority direction (O): "a label with a higher priority is placed in preference to ..."; TODO(review) #148 says "confirm that a higher `priority` value means a higher priority". Implemented: higher number wins. Default priority when `priority` is absent or null: 0 (U).
- Labels from different layers are placed in one pass (not per layer).
- A label partly outside the map (U): kept if any part is inside the image; dropped if entirely outside.
- Dropped labels do not leave an obstacle; the marker of the same feature is still drawn.
- Symbolizer `visibility: false` removes the label (the feature is not portrayed). Symbolizer `opacity` is not applied to labels (NOTE).

**F3. Repetition along lines: minSpacing, maxSpacing (O). `/req/labels/placement`.**
Words: "repeating a label so that the distance between repetitions of that label is at least minSpacing and, where space allows, at most maxSpacing".
Open: measured along the line or straight; what "that label" is (same feature, same text); where the first label goes; what happens without minSpacing (no repetition? one label?); whether repetition counts on the visible part of the line; what `maxSpacing` changes (no way to satisfy both when a label is placed greedily).
Implemented: for each line feature, the part inside the image; candidates at s/2, 3s/2, ... along that part with s = minSpacing (a single label at the middle if the visible part is shorter than s); no minSpacing means a single label at the middle of the longest visible part; a candidate is also rejected if a label with the same text was already placed within s (straight-line distance) so that the labels of a road split into several features are still at least s apart; `maxSpacing` is read but does not change the step (the step equals the minimum). Minimum spacing counts only among labels with identical text.

## G. Output and rasterisation

**G1. Pixel mapping, anti-aliasing, compositing (U).** The text has no requirement on how pixel coverage, anti-aliasing, pixel center convention or color blending are done, nor on gamma. Implemented: pixel (i, j) covers [i, i+1) x [j, j+1) of the bbox mapped linearly; 4 x 4 supersampling with box filtering; straight alpha "over" compositing in sRGB values (no gamma conversion); background white from the view.

**G2. Opacity grouping (O). `/req/core/opacity` versus `/rec/core/opacity-together`.**
The requirement says multiply the symbolizer opacity with the opacity of the fill, the stroke and the marker graphics (each individually: overlaps would show through); the recommendation says to apply it to them together. Implemented the recommendation: fill, stroke, center line and markers of one feature are drawn in a group and the group is blended with the symbolizer opacity (the result differs where the half of the stroke over the fill and Dot overlaps lie; the plain multiplication would give a darker overlap). Casing is not part of the group (drawn in the zOrder casing pass with symbolizer opacity multiplied on its own).

**G3. Order of a single feature's parts (U).** Fill, stroke, center line, marker; not stated except "casing beneath, center line on top of the main stroke". The text says nothing about whether the marker of a feature goes over its stroke (implemented: yes).

**G4. Layer type for `dataLayer.type` (U).** `/req/core/layers` says values `map`, `vector`, `coverage`; the Layer table says "vector, coverage, ..."; GeoJSON layers are `vector`, ASCII grids `coverage`; no definition of `map`.

**G5. Not exercised or not implemented:** variables and `$include`, `visualization.pass`, `feature.pass` (defined as identifiers but with no rule on how passes are numbered or on what a rule with a pass selector renders), vendor extensions, colorChannels from Sentinel-style data, text `underline`, image `alphaThreshold`, dash lengths in percent.
