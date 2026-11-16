# Notes: places where the requirement text leaves a choice open

Renderer: `renderer/render.py` (numpy, Pillow, shapely; 4x4 supersampling; fonts from C:\Windows\Fonts). Images: `out/<case>-<N>.png` (21 images for 20 cases; vector-units has two views).
Each entry: identifier, words that leave it open, readings considered, reading implemented.

## A. The ten points asked about

### 1. Direction of +y in a Graphic position
- Where: /req/vector/graphics ("uom-qualified 2D real position offsetting the graphic from its original position"); UnitPoint table ("x Horizontal position, y Vertical position"); Image table ("hotSpot: 0,0 position in the image").
- Open: neither says whether positive y points up (north, mathematical) or down (screen, image rows).
- Readings: (a) +y up; (b) +y down, as in image/screen/CSS coordinates.
- Implemented: (b) +y down (screen), for `position` and for `hotSpot` (origin = top-left of the image, so `50 pc 100 pc` is bottom centre).
- Why: UnitPoint is one class used for both; the test-case comment on hotSpot treats 100 pc as the bottom, which needs y down for hotSpot, and I applied the same to `position`. Under (a) the `0 -6, center top` text of vector-text would sit below its dot; under (b) it overlaps the dot. Reading (a) would be the more natural one for that case, so the two cases pull in opposite directions; the text is silent.

### 2. Meaning of dashOffset
- Where: /req/dashes/dash-offset ("dashing vector geometry based on a dashOffset property"); figure caption "a dash pattern preceded by an offset on the rendering of the associated dash pattern"; overview "an offset on the rendering of the associated dash array".
- Open: the sign, whether the offset is a phase shift into the pattern or a blank run before the pattern, and its unit (type is UnitValue).
- Readings: (a) SVG/Canvas semantics: the pattern is advanced, so the line starts `offset` into the pattern (8 px dash, 4 px gap, offset 4 -> starts with a 4 px dash remainder); (b) the line starts with a gap of length `offset`, then the pattern; (c) negative shift of (a).
- Implemented: (a). Offset resolved as a length in the same units rules as dashPattern (default px). The pattern restarts at the first vertex of each line (and each polygon ring) and runs continuously through vertices. Odd-length patterns are repeated to make an even one (SVG rule), not specified by the text. Caps are butt (from the Stroke paragraph). Casing and centre lines are drawn solid, not dashed (not specified).

### 3. Coverage cells to output pixels; which samples hill shading differentiates
- Where: /req/coverage/color-channels ("portraying each coverage cell"), /req/hill-shading/hill-shading ("differences in elevation between neighbouring samples of the elevation coverage at the resolution being rendered, over the horizontal distance between those samples"), NOTE under /req/hill-shading/factor.
- Open: how a 150 m cell becomes pixels at 75 m (or 28 m) per pixel (nearest, bilinear, area average), and what "samples ... at the resolution being rendered" are (source cells, or values resampled to the output grid) and with which resampling.
- Readings for colour: (a) the cell that contains the pixel centre (nearest, blocky); (b) bilinear interpolated value then map. Readings for slope: (a) central difference of source cells over 2 x 150 m; (b) forward difference of source cells; (c) resample the elevation to the output pixel grid and difference neighbouring output pixels.
- Implemented: colour/opacity = nearest cell containing the pixel centre (so each cell is a block); shade = (c): elevation bilinearly resampled at pixel centres (cell values taken at cell centres, edge clamped), central differences between the two neighbouring output pixels (np.gradient, one-sided at the image edge), divided by the ground distance of the output pixel (scaleDenominator-based, equal to bbox/size). Horizontal normal components multiplied by `factor`, then normalised; sun vector from azimuth (clockwise from north, compass) and elevation; shade = clamp(n.l, 0, 1); with no hill-shading colorMap, the RGB of each pixel is multiplied by shade, alpha untouched.
- Consequence worth noting: flat terrain gets shade sin(sun elevation) (0.5 at 30 degrees), so the whole map is darkened, not only slopes. This follows the text literally ("1 is no shade (sun in direction of normal)").
- Cells with NODATA (-9999) and pixels outside the grid are not painted. A selector that depends on the cell values is not evaluated per cell (rules are evaluated once per coverage layer; none of the cases need it).

### 4. Labels partly outside the map
- Where: /req/labels/label, /rec/labels/overlap ("omit labels which cannot be placed without overlapping other labels"). Nothing about the map edge.
- Readings: (a) omit labels not fully inside the map; (b) draw labels whose anchor is inside and clip glyphs at the edge; (c) draw anything that intersects the map, including anchors outside.
- Implemented: (b). Anchor must be inside the map; the label is then drawn even if it is clipped by the edge. Labels with anchors outside are dropped. (A label whose anchor is outside but whose text reaches in is not drawn.)

### 5. Stipple dots (and dot-pattern dots)
- Where: /req/stipples/ratio ("Ratio of stippling dots according to area filled"), TODO(review) #84 "define the size and color of the stipple dots"; /req/dot-patterns/distance (TODO #84 same).
- Open: dot size, dot colour, dot placement (random or regular grid), what the ratio measures, background.
- Readings for ratio: share of the area covered by dots; share of pixels; number of dots per unit.
- Implemented: dots are circles of 2 px diameter in the fill colour (with the fill opacity), no background fill. Stipple: square grid anchored at the output image origin (top-left), spacing s = sqrt(pi r^2 / ratio) so that dot area / cell area = ratio (ratio 0.3 -> s = 3.24 px). Dot pattern: same dot, centres at (i * horizontal, j * vertical) from the output image origin. Dot pattern and stipple do not paint a solid underlay.

### 6. Centre lines: per feature or after all main strokes
- Where: /req/casing/center ("drawing the center line ... on top of the main stroke") vs /req/casing/casing which says explicitly "casings of all features with the same zOrder beneath the main strokes of all those features".
- Readings: (a) per feature, immediately after its main stroke (centres of earlier features can be covered by later features' main strokes at crossings); (b) after all main strokes of the same zOrder.
- Implemented: (b), by analogy with the casing wording: within one zOrder, order is casings of all features, then each feature's fill/stroke/marker, then centre lines of all features.

### 7. Label repetition along lines
- Where: /req/labels/placement ("repeating a label so that the distance between repetitions of that label is at least minSpacing and, where space allows, at most maxSpacing, both in pixels").
- Open: what is repeated (per feature, per road), distance measured along the line or straight, between anchors or between text boxes, where the first label goes, label orientation, what happens with only minSpacing, line pieces outside the map, and short lines.
- Implemented: per feature; the line is first clipped to the map; each remaining piece of length Lp gets n = max(1, floor(Lp / minSpacing)) anchors at Lp * (i + 0.5) / n (evenly spread, first at half a step, so spacing along the line >= minSpacing); if `maxSpacing` is set and Lp / n exceeds it, n is raised to ceil(Lp / maxSpacing) when that keeps spacing >= minSpacing. Distance is along the line, between anchors. Text is horizontal (not rotated, not curved), centred on the anchor, because no rotation is specified. Spacing is not enforced between different features of the same road (same number). Each repetition still goes through the overlap test, so repetitions can be dropped.

### 8. Features no rule selects
- Where: /req/core/symbolizer ("using the default values for properties not set by any selected rule"), /req/core/default-values, NOTE after the default tables ("so that every feature is visible by default"), vs /req/core/selector ("applying the Symbolizer of a StylingRule ... only if ... selector evaluates to true").
- Readings: (a) a feature selected by no rule is portrayed with all defaults (white fill, black 1 px stroke, 10 px white Dot marker); (b) a feature selected by no rule is not portrayed.
- Implemented: (a), following the default-values NOTE. This matters for core-opacity (only `lake` is selected; the other polygons get white fill, black 1 px outline and a white 10 px dot at the centroid).
- Related: an unset `stroke`/`fill` on a selected rule also gets the defaults and is drawn (a polygon with no `stroke` property gets a black 1 px outline). `marker: null` draws nothing; an unset marker draws the default Dot.

### 9. Hatch colour, angle reference and direction, phase
- Where: /req/hatches/hatch ("pattern of parallel lines"), Hatch table ("angle: Hatches orientation clockwise degree"), TODO(review) #146 (says other angles are counter-clockwise from pointing right), "Distance between two consecutive hatches", "Thickness of hatch".
- Open: colour of the lines (Hatch has no colour member), what is painted between lines, reference direction of 0, rotation direction, distance measured along which axis, line phase.
- Readings, colour: lines in `fill.color`, nothing between them; or solid fill.color plus lines in another colour. Angle: (a) clockwise from the +x axis (0 = horizontal lines, 90 = vertical, 45 = lines running top-left to bottom-right "\"); (b) counter-clockwise from +x ("/" for 45). Distance: perpendicular between lines (centre to centre) or along x. Phase: per polygon bbox, or global.
- Implemented: lines in the fill colour and fill opacity with a transparent background; angle clockwise on screen from the horizontal (table wording, not the TODO), so 45 gives "\"; `distance` is perpendicular line-to-line (centre line to centre line), `width` the perpendicular thickness; lines pass through the output image origin (global phase: line k is the set of points whose distance from the origin line is k * distance), so neighbouring polygons share a pattern. Hatch does not alter the stroke of the outline. Default hatch values (1 px, 45, 10 px) are implemented for omitted members. `angle` is a plain number (degrees).

### 10. Font outline size unit and meaning
- Where: FontOutline table ("size: Size of the outline, float"), /req/font-outlines/size ("outline extending outward from the glyph contours by the thickness specified by the size property").
- Open: unit (pixels, points, em, a fraction of the font size) and whether "thickness" is the outward extension (a total stroke width of 2 x size) or the total stroke width.
- Implemented: unit pixels (the default unit of every uom-qualified property; "no unit: for screen-space objects, defaults to pixels"); outline extends `size` pixels outward from the glyph contour (stroke_width = size, the glyph is drawn on top so the visible band is size px). Outline `opacity` default 1, `color` default black (no default given). Outline is painted beneath the glyphs and is not clipped to its own colour inside the glyph.

## B. Other open or inconsistent places

### B1. Pixel size, font size and points
- /req/vector/fonts says `size` in points; Units table: "points ... one point = 1/72 inch"; pixel = 0.28 mm. Font size in px = pt * (25.4/72) / 0.28 = 1.26 px per point (9 pt = 11.3 px). Alternative 96-dpi (1.333) or 1 pt = 1 px not used. The "em size" of the font is taken as the font size (Pillow's size = em in px). Text box height for vertical alignment: ascent + descent of the font (not cap height, not the ink box).
- Default text alignment is not defined: center middle implemented.
- Default Font face, size, colour not defined: Arial, 10 pt, black implemented.
- Number rendered as text (elevation): integer-valued numbers printed without decimals; no formatting rule exists.
- Text with null value -> empty string (from the NULL table), nothing drawn.

### B2. Units
- /req/vector/units lists "pixel, millimeter, inch, percentage, meter, foot"; /req/dashes lists "pixels, points, millimeters, centimeters and inches"; the schema adds `em`, `cm`, `pt`, `pc`; the unit enumeration (GraphicalUnit) names pixels, meters, feet, percent, points, em, screenInches, screenCM, screenMM. Inconsistent sets. Implemented all of px, mm, cm, in, pt, em, m, ft.
- Ground units (m, ft) converted with scaleDenominator * pixelSize_mm (equal to bbox width / image width in every case). `percent` for a width is context dependent and not defined; not implemented for lengths (hotSpot only).
- A bare number where a UnitValue is expected (e.g. `"width": 0.0`, Dot `size` computed by an expression, `position` in CSS `12 -12`) is read as pixels ("(none) ... For screen-space objects, defaults to pixels", but the same table says "(none): For relative values like scaling, 100 times less than if pc is specified" - two meanings).
- hotSpot: `pc` is a percentage of the image size; a bare number is a fraction (default `{0.5, 0.5}`); see 1 for direction.
- Image size on the map is not specified: images drawn at native pixel size (1 image px = 1 output px).
- alphaThreshold: not used (permission only).

### B3. Dot
- /req/vector/dot: "size ... and color ... are the same values as width and color of its stroke". A Dot with an explicit `stroke` is drawn with `stroke.width`/`stroke.color` when `size`/`color` are absent. Default size 10 px, default colour white (Dot defaults table) - white on a white background is invisible; implemented as specified.
- The NOTE says "A Dot with an outline is drawn with two concentric Dots" but no member defines an outline colour apart from `stroke`; the case styles never use `stroke` on a Dot, so I did not implement the outline form.

### B4. Opacity
- /req/core/opacity: "multiplying it with the opacity of the fill, the stroke, the graphics of markers"; /rec/core/opacity-together is only SHOULD. Implemented the recommendation: fill, stroke and markers of one feature composited as a group with the symbolizer opacity (no show-through). Casing and centre line use opacity separately (own opacity x symbolizer opacity). Text in markers: opacity applies (the NOTE excludes labels only, and labels are not affected).
- Symbolizer `opacity` for coverage cells multiplies with the alpha from the opacityMap and alphaChannel.

### B5. Rule evaluation and merging
- /req/core/rules: "overriding all Symbolizer properties set by earlier rules": object-valued properties (stroke, fill, marker, ...) set without `alter` replace the whole object (members not given revert to defaults); with `"alter": true` only the given members change. This is how I read /req/core/instances and /req/json/partial-update; the CSS example in clause 7 (`stroke: { gray }` then `stroke.width: 5px`) agrees.
- Order of evaluation: top-level rules in order; for a selected rule apply its symbolizer, then its nested rules in order, recursively. Nested rules therefore override the parent, and later top-level rules override earlier ones, including their nested rules.
- Selector evaluating to null counts as not selected (NOTE under /req/core/selector). Boolean connectives use three-valued logic (CQL2, "as specified by CQL2" in /req/core/operations).
- `visibility: false` also suppresses the label of the feature (not stated).
- Null for Parameter Values: numbers -> 0, booleans -> false, colour -> black, text -> "" (table); a null `priority` -> 0.
- `size: (elevation - 900) / 100`: division is real division (no `div` operator used); intDiv exists separately. Result in px as a bare number.
- Arithmetic operators and expressions in parameter values are not conformance-class gated in my renderer (everything on).

### B6. Identifiers and encodings (contradictions)
- Clause 7 names `dataLayer.identifier`, `visualization.scaleDenominator`, `visualization.timeInterval`; the JSON schema enumerates `dataLayer.id`, `viz.sd`, `viz.timeInterval.start.date`; CSS examples use `viz.sd`; vector table has `feature.geometryDimension` vs UML `geometryDimensions` vs schema `dataLayer.featuresGeometryDimensions`. The styles use `dataLayer.id`, `viz.timeInterval.start.date`. I accept both `dataLayer.id` and `dataLayer.identifier` and also `viz.*` names.
- Core table says `Visualization.timeInterval` is TimeInstant start/end (date + time); the views give only dates. `validDate >= viz.timeInterval.start.date` compares a text property with a Date: I convert an ISO date string to a date (comparison coercion is not defined). A feature without `marked` evaluates `marked = true` to null -> not selected.
- Clause 7 says `zOrder` is "int" in the Symbolizer table and "float" in the ordering table; implemented as a number. Default zOrder 1.
- `centerLine` (schema) vs `center` (requirement); the JSON files use `center`. Implemented `center`.
- JSON `alignment` is an array `["left","middle"]` in the schema and an object `hAlignment/vAlignment` while the text names `horzAlignment/vertAlignment`: accepted all.
- Color: the schema and CSS clause give 0..255 components, /req/coverage/color-channels says 0..1 for colorChannels (and the TODO notes the mismatch); colorChannels not used in the cases: 0..1 implemented. Hill-shading colorMap values are 0..1 in the schema (shade value); hillShading opacityMap likewise.
- Image `image` Resource has both `uri` and `path` in the case (`http://example.com/...` and `../icons/hut.png`): precedence not defined; `path` used first, resolved relative to the case folder (so `../icons/hut.png` = cases/icons/hut.png), `url` never fetched.
- Text label elements may also be Dot or Image; handled in the same way.
- `stipple`, `dotpattern`, `hatch` in the same Fill: precedence undefined; hatch > dotpattern > stipple, and any of them replaces the solid fill.

### B7. Layer order, z-order and passes
- /req/core/z-order: "increasing order of resolved zOrder" within a pass. Between layers, the view lists layers "in drawing order". Implemented: all features of all layers are sorted by (zOrder, layer order, feature order); so zOrder overrides layer order. A coverage layer counts as one item with the zOrder of its symbolizer. visualization passes and feature passes are not used (single pass, `viz.pass` = 1).
- Labels are one separate pass on top of everything ("separate pass on top of all styled vector features and coverages"); marker Text graphics are not labels and are drawn with the feature at the feature's zOrder (no collision test).

### B8. Labels
- /rec/labels/overlap is SHOULD; implemented: candidates sorted by priority descending (higher number first, per TODO #148 unconfirmed), ties by feature order; a candidate is dropped when its text box (with the outline extension) intersects an accepted label's box (bounding boxes, no padding). Collisions with markers, other layers' geometry and with Dots/Images inside a label are only tested via their own boxes.
- Label anchor: point for points; centroid for polygons; spaced anchors for lines (see 7). Label `position` offset as in 1.
- Label graphics other than text use the same drawing as markers.
- Label opacity: the NOTE says the symbolizer opacity does not apply to labels: implemented; font `opacity` and graphic `opacity` do.

### B9. Strokes and geometry
- Stroke geometry: centred on the geometry; butt caps; miter joins (stated) with a miter limit of 4 (SVG default; not stated: beyond it the join is bevelled).
- Stroke width 0 draws nothing. Polygon strokes include holes. Point features have no stroke/fill.
- Marker positions: points; every vertex of lines (including those outside the map, which are clipped); polygon centroid (shapely centroid, which can lie outside a concave polygon; "centroid" not further defined). Multi-geometries: each part separately.
- Casing: total width = main width + 2 x casing width (stated). Casing and main stroke are not dashed together; the casing is solid. Casing join/caps = same as main.
- Pixel centres: geometry in output pixel coordinates (0,0) = top-left corner of the top-left pixel, pixel centre at +0.5; the bbox maps exactly to the image.
- Antialiasing: 4 x 4 supersampling with box downsampling; the standard says nothing, so pixel values will differ at edges between implementations.

### B10. Colour-map interpolation
- /req/coverage/color-map and /rec/coverage/map-interpolation + NOTE: "interpolation method is not specified: linear ... or a smoother one". Implemented linear interpolation per RGB component in sRGB values (not linear light, not Lab), clamped to the first/last entry outside the range; opacityMap linear. Entries are sorted by value.
- opacityMap entry form: ValueOpacity table lists a `color` member (copy-paste error) while the text and schema use `opacity`.
- Opacity maps with no colourmap: alpha only, colour then from colorChannels or singleChannel as a grey value (not exercised).

### B11. Miscellaneous
- Default `Stroke` and `Fill` are implemented for unspecified symbolizer properties as in B5/8. A Fill with only `opacity` uses white.
- `visibility` of a coverage applies to the whole layer item.
- Time: the `visualization.date` and `timeInterval` come from the view; time of day not given, not needed.
- The Dot spec "size" with expression in px: negative values -> nothing drawn.
- The `alpha`/`index` partial updates are implemented for objects and arrays (`elements`, `dashPattern`), but no case uses `index`.
