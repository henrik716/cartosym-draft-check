# Notes: places where the requirement text leaves a choice open

Renderer: `renderer/render.py` (Python, numpy, Pillow, pycairo, shapely). 21 images (20 cases, `vector-units` has two views) in `out/`.
Each entry: identifier, words that leave it open, readings considered, reading implemented.

## A. Directions, units, geometry

### A1. Direction of +y in a Graphic position (`/req/vector/graphics`)
- Words: "interpreting a positive `x` of the position as an offset to the right and a positive `y` as an offset upwards on the map, as for `Displacement` in SE 1.1".
- Clear in the requirement, but it conflicts with the unit table in clause 17: "(none) ... For screen-space objects, defaults to pixels" does not say which way y goes, and the screen convention (y down) is the common one for graphics. The case `labels-priority` has `position: 0 8` on a label; under this reading the label sits 8 px above the point.
- Implemented: +y = up on the map (screen y = anchor y - offset y). A unitless position number is taken as pixels.
- Open: "upwards on the map" for a map that is not north-up (no rotation exists here, so no issue).

### A2. Unit of a unitless length (Graphical Units of Measure; clause 17 units table)
- Words: "The portrayal unit 'pixel' is the default unit of measure" versus the clause 17 row "(none) | For relative values like scaling, 100 times less than if pc is specified. For screen-space objects, defaults to pixels."
- Readings: (a) pixels everywhere; (b) a fraction for relative values such as scaling and hotSpot, pixels elsewhere.
- Implemented: (b), for hotSpot only fractions (see A8); every other bare number is pixels (stroke widths, Dot size, positions, hatch width/distance, dash lengths, font outline size).
- Contradiction: the table of the units (clause 8 uses "pixel, millimeter, inch, percentage, meter, foot"; clause 17 and the JSON schema add pt, cm, em; `/req/vector/units` lists only "pixel, millimeter, inch, percentage, meter, foot"; `/req/dashes/dash-pattern` also lists points and centimeters). The abbreviations also differ: clause 8 says "pixel", clause 17 `px`, `inch`, JSON `in`.

### A3. How big is a pixel for ground units and for mm/pt
- Words: "If available, the pixel size depends on the viewer client resolution, otherwise it is equal to 0.28mm x 0.28mm" (clause 8). The view gives `pixelSize_mm` 0.28, `scaleDenominator` and a `bbox`.
- Readings: ground metres per pixel from (a) bbox width / image width; (b) scaleDenominator x pixelSize_mm.
- Implemented: (b) for unit conversion (m, ft); geometry placement from bbox. In all 21 views (a) and (b) agree. The text never says which one wins if they differ.
- `pt`: 1/72 inch = 0.3528 mm (clause 17 "One point is equal to 1/72 inch (0.3528 mm)"), so 1 pt = 1.26 px; `in` = 25.4 mm = 90.7 px; same for font sizes.
- `em` and `pc` for a stroke width, a dash length or a position: no meaning is defined ("Relative value whose meaning depends on context"); not implemented for lengths, only `pc` for hotSpot.

### A4. Pixel/geometry alignment
- Words: none. Nothing says whether a pixel's coordinates are its centre or its corner, or whether geometry is snapped.
- Implemented: map pixel (i,j) covers [i,i+1] x [j,j+1] with the top-left corner at (bbox minx, bbox maxy); no snapping of lines or markers; anti-aliased edges. (Only the coverage requirement says "each pixel of the map whose center lies in a cell".)

### A5. Stroke caps, joins, miter limit (Strokes)
- Words: "By default the end of open subpaths are butt caped and at the corners of paths are miter joined".
- Open: the miter limit (what happens at a sharp corner). Implemented: cairo's default of 10. Dash caps: butt. Casing caps/joins: same as the main stroke.

### A6. Stroke width 0 (`/req/vector/stroke`, example vector-marker-dot)
- Words: none about width 0. Dot says "drawing nothing for a Dot whose `size` is 0 or less", but no such sentence for strokes.
- Readings: no stroke; a hairline (1 device pixel).
- Implemented: no stroke drawn for width <= 0.
- Also: a `stroke` object that does not set `color` (the case has `stroke: { width: 0 }`) replaces the earlier stroke entirely (default colour black, default width 1 px apply to unset members), because a non-`alter` object replaces ("completely replace stroke property" in the instance-expression example of clause 7).

### A7. Marker position on polygons and lines (`/req/vector/marker`)
- Words: "at the points of vector geometry (for points and line strings) and at the centroid of polygons".
- Open: (1) "points of a line string" is read as every vertex, including end points; (2) "centroid" of a polygon: area centroid of the exterior with holes (it can lie outside a concave polygon) vs. a point guaranteed inside; (3) for polygons with several parts (MultiPolygon): one marker per part vs. one per feature; (4) for a line, markers at vertices only, not along segments.
- Implemented: all vertices; area centroid of each polygon part (shapely, with holes); one marker per part.

### A8. Image `hotSpot` origin and a number without a unit (`/req/vector/image`)
- Words: "interpreting the `hotSpot` in the coordinates of the image, from its top left corner with `x` to the right and `y` downwards, where a number without a unit is a fraction of the image's width or height, a value in `pc` is a percentage of it, and a value in another unit is a length from that corner."
- Contradictions/gaps: the same sentence is clear for the origin (top left, y down), unlike `Graphic.position` (y up). The Image table says "hotSpot | 0,0 position in the image", which can be read as the origin of the image being the hot spot; the default is `{ 0.5, 0.5 }` "center of the image". The NOTE says SE 1.1 AnchorPointY is measured from the bottom. The case uses `50 pc 100 pc` = bottom centre.
- Implemented: origin top-left, y down; unitless number = fraction (0.5 = centre); `pc` = percent of width/height; other units are lengths in pixels from that corner.
- Image size: no size property exists in the Image class. Implemented: 1 image pixel = 1 map pixel (no scaling). Resampling at a fractional position: not specified; implemented with cairo's default filter at the exact fractional offset (no snapping).
- Resource keys: the text lists `url` and `path`, the JSON schema and case use `uri` and `path`. Implemented: `path` relative to the case folder; `uri`/`url` is not used (the sample's `uri` is a placeholder online address, `http://example.com/icons/hut.png`). Which wins when both are given is not stated; chose `path` ("preferably relative path to local file").
- `tint` / `blackTint`: formula given, clear. Alpha is kept unchanged; the "Color" of tint with components 0..255 in encodings versus "each red, green and blue component v (between 0 and 1)" is read as 0..255 normalised to 0..1.
- `alphaThreshold`: not applied (the permission is optional, default 0, so no effect on the cases).

### A9. Default Dot colour vs default Stroke colour (Default class member values)
- Words: Stroke default colour "black", Dot "color | white", yet `/req/vector/dot` says the Dot's `color` "[is] the `color` of its stroke".
- Contradiction: a Dot's colour is its stroke's colour, but the defaults differ (white vs black). Implemented: for a Dot with no colour (and no stroke colour) white; size 10 px.

## B. Core

### B1. System identifier names (clause 7 vs JSON schema vs README)
- Words: clause 7 names `visualization.scaleDenominator`, `dataLayer.identifier`, `visualization.date`; clause 17 uses `viz.sd`, `viz.date`; JSON schema enumerates `dataLayer.id`, `viz.sd`, `viz.timeInterval.start.date`, `feature.id`. `/req/core/layers`: "`dataLayer.identifier` ... and `dataLayer.type`". The unit table mentions `feature.geometryDimension` while the UML says `feature.geometryDimensions`.
- Implemented: accepted all of `dataLayer.id|identifier`, `viz.sd|visualization.scaleDenominator`, `viz.date`, `viz.timeInterval.(start|end)[.date]`. The `dataLayer.type` values are strings (`vector`, `coverage`). The `dataLayer.type` data-type "enumeration: vector, coverage, ..." versus the requirement's "(`map`, `vector` or `coverage`)" ("map" is undefined).

### B2. Order in which rules override (`/req/core/rules`, `/req/core/nested`)
- Words: "Symbolizer properties specified in a StylingRule appearing later ... SHALL be interpreted as overriding ... earlier rules"; "a selected nested rule inheriting from, and overriding, the Symbolizer properties of its parent rule".
- Open: where a nested rule sits in the sequence relative to the parent's later siblings.
- Implemented: depth-first document order: a rule, then its nested rules, then the next sibling. A later top-level rule therefore overrides the nested rules of an earlier one.
- Open: whether overriding is per property or per whole object. Implemented: an object property without `alter: true` replaces the earlier value wholesale (members not given go back to their defaults); with `"alter": true` only the given members change (`/req/json/partial-update`). In CartoSym-CSS the same difference is `stroke: {..}` vs `stroke.color:`; I used the JSON file only.

### B3. Null in selectors (`/req/core/selector` NOTE, `/req/core/operations`)
- Words: "A `selector` evaluating to null does not evaluate to true"; "evaluating operation expressions with a null operand as specified by CQL2".
- Open: whether "as specified by CQL2" means three-valued logic. Implemented: comparison with null gives null; `and`/`or` use three-valued logic; the selector must be exactly true. A missing feature property is null.
- Open: how a property that is a date compares: the data type of `validDate` is "an ISO date" per README only. Implemented: when one operand is a date (`viz.timeInterval.start.date`) and the other a string, both are parsed as dates. `viz.timeInterval.end.date` is inclusive (`<=`), and a view interval given as dates only has no time of day (start and end compared as dates).

### B4. Features that no rule selects (`/req/core/symbolizer`) - choice (8)
- Words: "A Renderer SHALL support portraying, with the default values, the features and coverage cells that no StylingRule selects, so that a style hides data only by setting `visibility` to false".
- Clear for layers; the same applies per feature. Implemented: a feature that no rule selects is drawn with the defaults (fill white, stroke black 1 px, default Dot marker of 10 px white at points/vertices/centroids, opacity 1, zOrder 1, no label). Every layer in the 21 views has a layer rule, but features of layer rules that select further (class selectors) are reached through the nested rules, where the parent's properties apply.
- Open: a layer that appears in the view but that no rule mentions would be drawn with the defaults too (not exercised).
- Open: the default Marker applies "to features of every geometry type" (NOTE in clause 7) - implemented; the styles unset it with `marker: null`.

### B5. zOrder scope and ties (`/req/core/z-order`)
- Words: "portraying features and coverage cells of a single rendering pass in increasing order of their resolved `zOrder` property".
- Open: (1) across layers or per layer; (2) the order of equal zOrders (layer order from the view? feature order in the file?); (3) the default `zOrder` of 1 for all layers; (4) negative or null zOrder (null -> 0 per the null table); (5) the UML note "zOrder needs discussion on whether it should be relative or float".
- Implemented: one global sort over all layers and features by (zOrder, layer position in view, feature position in file), stable. Rendering passes (`visualization.pass`, `feature.pass`) are not implemented; not exercised.

### B6. Opacity (`/req/core/opacity`, `/rec/core/opacity-together`)
- Words: "multiplying it with the opacity of the fill, the stroke, the graphics of markers and the opacity channel of coverage cells"; recommendation: "apply ... to the fill, the stroke and the graphics of markers of each feature together, so that they do not show through each other where they overlap".
- Readings: (a) multiply each separately (the stroke over the fill shows the fill under half of its width); (b) draw each feature's fill, stroke and markers opaque in a group and composite the group with the opacity.
- Implemented: (b) (the SHOULD). Contradiction with casing/center: casings and centre lines are drawn in separate passes across features (`/req/casing/...`), so they cannot be in the feature group; for them the opacity multiplies each pass separately. Labels: "does not apply to labels" (NOTE), not applied.
- A fill's own `opacity` with a symbolizer `opacity`: multiplied (fill.opacity x opacity).

### B7. Parameter values: unit, null, numbers (`/req/parameter-values/null`, `/req/core/parameters`)
- Words: table "Integer or real ... | 0", "Marker or Label | null".
- Open: the dividing `/`: JSON `/` is mapped to `div` ("real-valued quotient ... including when both operands are integers") - clear. The result of the example in `core-parameters` is a unitless number as a Dot `size`: implemented as pixels, and a size of 0 or less draws nothing (stated for Dot).
- Open: the rule that a property whose expression evaluates to null becomes 0 / false / black / "" is applied only for an expression that returns null at runtime (e.g. missing property); a text label with a missing `number` property (null) becomes "" and draws nothing. For a text label ("Text | the empty string") the table does not say that an empty label is omitted from overlap tests; implemented: omitted.

### B8. Number to text conversion (`/req/vector/text`)
- Words: "`text` | string (unicode)^1^ ... identifier parameter value expression for the `text` property".
- Open: how a number is converted to the displayed string (the `elevation` integer in vector-text). Readings: shortest form; fixed decimals. Implemented: integers without decimals, floats that are whole numbers without the decimal part, other floats with Python's shortest representation. Booleans "true"/"false".

### B9. JSON encoding details not in the requirements
- `center` (clause 7, `/req/casing/center`) vs `centerLine` (JSON schema; the clause itself has a TODO: "the JSON schema names this property `centerLine` rather than `center` (see #120)"). The case uses `center`. Implemented: accept both.
- `stipple`, `hatch`, `dotpattern` as members of the fill object: in the JSON schema `dotpattern.distance` is an object or a pair; handled both. The schema for `dotpattern` has no `type` for the object (looks malformed) - ignored.
- Colour `0..255` in encodings versus `colorChannels` "each in the range 0 to 1" and the TODO in the default-values section (the default `colorChannels` unscaled): implemented 0..255 for `Color` objects/arrays/hex/names and 0..1 for `colorChannels`.
- `"alignment": ["left","middle"]` array form accepted (and `hAlignment`/`vAlignment` object keys from the schema vs `horzAlignment`/`vertAlignment` in the table of `TextAlignment`: another inconsistency).
- `Dot` `position` is not defined on Dot by the UML (position sits on Graphic; Dot also has `point`: UnitPoint in the UML). Implemented `position` as the offset; `point` ignored. Unclear why Dot has both.
- `Font.color` and `Font.opacity` appear in the UML but not in the Font table (which lists face, size, bold, italic). Implemented the UML (`color`, `opacity`, `outline`); defaults: colour black, opacity 1, size 10 pt, face Arial (none of these defaults is given by the text).

## C. Coverage

### C1. Mapping coverage cells to output pixels (choice 3) (`/req/coverage/single-channel`)
- Words: "portraying each coverage cell over the whole area of that cell, so that each pixel of the map whose center lies in a cell takes the color and opacity of that cell."
- Clear (nearest neighbour; no smoothing). In the cases the cell is 150 m and the pixel 75 m, so a cell covers 2x2 pixels. Implemented: pixel centre -> floor((X - xllcorner)/cellsize); ESRI ASCII rows run from north; the grid origin `xllcorner/yllcorner` is the lower-left *corner* of the lower-left cell (the README gives the file format only; the spec text does not mention the ASCII-grid format or whether the corner or the centre is meant). Pixels outside the grid are transparent; NODATA_value cells are transparent (not specified).
- Open: selectors that depend on cell values (a coverage selector using a band). Implemented: rules are evaluated once per coverage layer (property identifiers are null); not exercised.

### C2. Colour map and opacity map interpolation (`/req/coverage/color-map`, `/rec/coverage/map-interpolation`)
- Words: "interpolating between the colors of the two closest entries for other values within the range of the map"; NOTE "The interpolation method is not specified: linear interpolation, or a smoother one, can be used."
- Implemented: linear, per component in sRGB (no gamma, no Lab); entries sorted by value; outside the range the first/last entry; an entry's value is exact. Open: the colour space for the interpolation is not named. Open: with the opacity map and colour map, the result colour and opacity are separate; composited over the white background as straight alpha (colour x alpha + background x (1 - alpha)).
- `colorMap` entries as `[value, color]` arrays in the JSON (the table says `value`/`color` pairs "tagged with a `name`"; schema has an optional third string); the UML says `label`, the table `name`.
- If the coverage has no `colorMap` for `singleChannel`: undefined; I used gray = value clamped to 0..1.

### C3. Hill shading samples and normal (choice 3) (`/req/hill-shading/hill-shading`)
- Words: "using as samples the cells of the elevation coverage where the map's resolution is as fine as the coverage's or finer, and the coverage resampled to the map's resolution where the map's resolution is coarser, and taking for each direction the difference between the two samples on either side of the cell over twice the distance between samples (repeating the edge sample at the edge of the coverage)."
- Here the map (75 m/px) is finer than the coverage (150 m), so the samples are the elevation cells: central differences between the cells at either side, over 2 x 150 m, edge cells repeated; the shade is computed per cell and each pixel takes the shade of the cell containing its centre (so the shaded relief is blocky at 2x2 pixels). A reading in which the shade is computed on pixels (derived from the pixel-resolution map) would differ: it is excluded by the text ("as fine as ... or finer" gives the cells). The "coarser" branch (resampling method: nearest, bilinear, average) is not defined; not implemented (not exercised).
- Open: "the unit normal of the terrain surface" - orientation of the normal's horizontal axes is implied by the gradients: normal = (-dz/dx x factor, -dz/dy x factor, 1) with x east, y north, then normalised; `factor` multiplies "the horizontal components ... before normalizing". Clear.
- Sun vector: "azimuth angle (in degrees clockwise from North, as a compass bearing)" = the direction *to* the sun (towards the sun: "the unit vector pointing towards the sun"); elevation above the ground plane. So a sun at azimuth 315 lights slopes that face north-west. Clear.
- Flat terrain shade: sin(elevation) (0.707 for 45 deg): the result is a darker image than the colour map alone; implied by the formula, no "ambient" term is defined.
- Hill shading `colorMap` entries are "value (float) ... pairs", with the shade value 0..1; used as for the `colorMap` property. When the hill shading has no `colorMap`: "multiplying the red, green and blue components of each cell by its shade value" - the components of the cell colour from the symbolizer `colorMap`. When it has a `colorMap`: its colour replaces the symbolizer colour (clear: "color mapped from its computed shade value").
- The hill shading `opacityMap` combined with the symbolizer `opacityMap`: not specified; implemented multiply. 
- Elevation source: "the elevation coverage" - implemented as the band named by `singleChannel` (if it is an identifier); not stated how the elevation is identified.
- NODATA among the neighbours of a cell: not defined; not exercised.

## D. Labels

### D1. Labels partly outside the map (choice 4) (`/rec/labels/overlap`)
- Words: "A Renderer SHOULD omit labels which would extend beyond the edges of the map, except where the map is drawn in tiles that are put together."
- Readings: omit if any part of the label's box is outside; omit if the anchor is outside only; clip. Implemented: omit a label whose box (union of its elements) is not fully inside [0,w] x [0,h]. The "box" of a label: not defined for a label with a Dot or Image element; I used the bounding box of its elements. It is a SHOULD and I follow it. The images are single non-tiled maps.
- Open: the box of a text: "the edge or center of its box" (`/req/vector/text`): box = advance width x (font ascent + descent) from the font's metrics; glyph outline size not included.

### D2. Overlap and priority (`/rec/labels/overlap`, `/req/labels/placement`)
- Words: "omit labels which cannot be placed without overlapping other labels, unless a property of the Symbolizer allows the overlap" (no such property exists); "a label with a higher `priority` is placed in preference to a conflicting label with a lower `priority`".
- Open: (1) whether a higher number is a higher priority (the clause has the TODO: "confirm that a higher `priority` value means a higher priority (see #148)"); (2) default priority when not set; (3) ties; (4) what counts as overlapping (boxes? glyph shapes? with a margin? also with markers/Dots or other features?); (5) whether a label may be moved to another position (only one position is defined); (6) for a label with several candidate positions: first-come or best.
- Implemented: higher value = higher priority; default 0; ties by (zOrder, layer, feature) order; labels are placed greedily in descending priority; overlap = intersecting text boxes (no margin, outline not included) with already placed labels only (markers are not obstacles); a conflicting label is omitted (never moved). `priority` can be an expression (the case uses the feature's `elevation`).

### D3. Label repetition along lines (choice 7) (`/req/labels/placement`)
- Words: "repeating a label so that the distance between repetitions of that label is at least `minSpacing` and, where space allows, at most `maxSpacing`, both in pixels unless qualified with another unit"; "treating as repetitions of a label all labels with the same content from the same data layer (so that a road split into several features is labelled as one), and measuring the distance between repetitions on the map between their positions".
- Open: (1) where on a line the label goes, and the orientation of the text (horizontal vs. along the tangent; the text defines neither); (2) "distance ... on the map between their positions": straight-line (Euclidean) distance between anchor positions vs. distance along the line; (3) whether the distance applies between consecutive repetitions or any pair; (4) how often to repeat with no `maxSpacing` ("where space allows, at most"); (5) what to do with no `minSpacing` (one label per feature? per line? per layer?); (6) the first label's position; (7) whether a label can exist when the line's parts are outside the map.
- Implemented: text horizontal (unrotated), anchored at a point on the line with the Text's alignment (default centre middle); distance = Euclidean distance in map pixels between positions, any pair of repetitions with the same (data layer, label text); candidates are sampled along each line every 2 px from its start, and a candidate is accepted if its box is inside the map, it overlaps no placed label and it is at least `minSpacing` from every placed repetition of that label; so repetitions are spaced about `minSpacing`, which is "at most maxSpacing" when `maxSpacing` is unset or larger. With no `minSpacing`, one label per line at its midpoint. `maxSpacing` is read but not used to place extra labels. Roads without a `number` property: label text "" -> no label.

### D4. Which features carry the label
- Words: "drawing the graphical elements of the labels as a separate pass on top of all styled vector features and coverages."
- Implemented: labels for visible features only (a feature with `visibility` false has neither marker nor label); for points at the point; for polygons at the area centroid; for lines as in D3. Label offsets (`position`) are applied to the label's anchor before the box is tested.

## E. Font outlines (choice 10)

### E1. Outline size unit and meaning (`/req/font-outlines/size`)
- Words: "drawing the outline extending outward from the glyph contours by the thickness specified by the `size` property, in pixels."
- Readings: (a) the outline reaches `size` px outside the glyph contour (stroke width 2 x size, half of it under the glyph); (b) `size` is the total stroke width (reaches size/2 outside); (c) in points like the font size.
- Implemented: (a), unit pixels (a unit qualifier on `size` is not allowed by the schema; `size` is a plain number there, while `FontOutline.size` is "float").
- Open: join style of the outline (round vs. miter); implemented round. Outline default colour (not stated): black; default opacity 1 when omitted (the case `labels-spacing` omits `opacity`).
- The outline is drawn "beneath the glyphs themselves": drawn first, then the glyph fill on top.
- Open: the outline opacity vs. the font opacity: the outline uses its own `opacity` only.
- Open: whether the outline's alpha is composited as one shape or with the stroke self-overlap: drawn as a single stroked path (no double blending).

## F. Dashes and casing

### F1. Meaning of `dashOffset` (choice 2) (`/req/dashes/dash-offset`)
- Words: "as the distance into the dash pattern at which dashing starts at the beginning of each line (as `stroke-dashoffset` in SVG and SE 1.1), in the units of the dash pattern: with a `dashPattern` of `[ 8, 4 ]` and a `dashOffset` of 4, each line starts with a 4 pixel dash, then a 4 pixel gap."
- Readings: (a) the pattern is shifted so that the line starts `offset` into the pattern (as SVG); (b) the line starts with a gap of `offset`. The example settles (a).
- Implemented: (a): dash array [dash, gap, ...] starting `offset` into the pattern at the start of every line of a feature (cairo `set_dash(array, offset)`, which has the same semantics). The "units of the dash pattern": the case gives `dashOffset` as `{px: 4}`; the table says `UnitValue` while the UML says `float`. A bare offset number is pixels.
- Open: odd-length patterns (repeat the pattern as in SVG); a pattern that is all zeros (treated as solid); a negative offset; the dash pattern on polygon rings (each ring restarts; the ring's start vertex is the first coordinate); the dash pattern with a casing (casing and centre are not dashed).
- The `dashPattern` lengths `{mm: 1}` = 1 mm/0.28 = 3.57 px. Percent and ground units (MAY): ground units supported by the same conversion; percent not supported.

### F2. Casing and centre lines per feature or after all main strokes (choice 6) (`/req/casing/casing`, `/req/casing/center`)
- Words: "drawing, within a single visualization pass, the casings of all features with the same `zOrder` beneath the main strokes of all those features, so that the casings of crossing and joining lines merge"; centre: "the center lines of all features with the same `zOrder` on top of the main strokes of all those features".
- Readings: (a) per feature (casing, main, centre one feature after the other); (b) per zOrder group across all features and layers: all casings, then all main strokes, then all centre lines. The text says (b) ("all features with the same zOrder"); the NOTE says per-feature order needs passes.
- Implemented: (b) across all layers of the same zOrder (the text says "all features with the same zOrder", not "of the layer"). Order in a zOrder group: all casings; then for each feature in order: fill, main stroke, markers; then all centre lines. Open: whether fills and markers of the group belong before or after the casings; whether markers go above centre lines (implemented: markers beneath centre lines because they are in the main pass).
- Casing width: "extends the `width` of the casing beyond each side of the main stroke, for a total width of the main stroke's `width` plus twice the casing's `width`" - clear. A casing or centre line of a stroke with width 0: nothing is drawn for the casing (implemented: casing is skipped when the main width <= 0). Casing/centre colour and width defaults when missing: black; centre width 1 px; casing width 0.
- A casing for polygon outlines: same geometry (implemented for rings).
- Open: the join of casing at the open ends (butt, no extension).
- Open: how casing interacts with dashes (casing not dashed; the main stroke is).

## G. Fills (choices 5 and 9)

### G1. Hatch (choice 9) (`/req/hatches/hatch`, Hatch class table)
- Words: "drawn in the `color` and `opacity` of the Fill, without painting the area between the lines"; "placing the hatch lines of all features on one pattern aligned with the map, with a line through the top left corner of the map"; angle: "Orientation of the hatch lines, in degrees, where 0 gives horizontal lines and angles turn counter-clockwise as seen on the map"; distance: "Distance between the centers of two consecutive hatch lines, measured across the lines".
- Hatch colour: the colour of the Fill (olive etc.); there is no separate hatch colour; the polygon area between lines is not painted (no background fill colour). A fill with a hatch and with a `color` and no background: confirmed.
- Angle reference: 0 = horizontal lines, counter-clockwise on the map (45 degrees rises to the right); 90 = vertical. Implemented as direction (cos a, -sin a) in screen coordinates. Contradiction noted in the text itself (the TODO about the earlier clockwise wording in the table versus the figure; fixed to counter-clockwise).
- Phase: a line (its centre line) passes through the top-left corner of the map (pixel (0,0)); other lines are offset by multiples of `distance` along the normal (sin a, cos a) in screen coordinates; the sign of k is irrelevant because the grid is symmetric about the corner. Open: whether the line is centred on the corner or the corner is at the line's edge (implemented centred); "top left corner of the map" is the corner of the image (not of the bbox of a feature, not of a tile).
- Open: the hatch lines are clipped to the polygon's fill region (even-odd, holes excluded); stroke drawn on top. Butt ends. Defaults when members are missing: width 1 px, angle 45, distance 10 px (the figure caption "Default hatch properties (width: 1 px, angle: 45, distance: 10 px)" is the only place that states the defaults; the default table does not).
- Open: whether the distance is in the unit of the `distance` value (`{px: 8}`; the table says float). Implemented a bare number is pixels.
- Open: hatch width and distance in ground units are possible by the same conversion.

### G2. Dot pattern (`/req/dot-patterns/dotpattern`, `/req/dot-patterns/distance`)
- Words: "a regular grid of points ..., each drawn as a filled circle with a diameter of 2 pixels in the `color` and `opacity` of the Fill"; "with its first point half the horizontal and half the vertical distance from the top left corner of the map".
- Implemented: points at (h/2 + i h, v/2 + j v) from the top-left corner of the map; diameter 2 px; clipped to the polygon fill region (alternative: draw only dots whose centre is inside; differs only at edges). `horizontal` = spacing along x, `vertical` = along y. The clause TODO: "define the size and color of the rendered points (see #84)" (the text nevertheless gives 2 px and the Fill colour, in the requirement).

### G3. Stipple dots (choice 5) (`/req/stipples/ratio`)
- Words: "dots in the `color` and `opacity` of the Fill placed at random so that they cover the `ratio` fraction of the area, without painting the area between the dots"; NOTE "The size of the dots and their placement are left to the Renderer, so two Renderers do not draw the same dots; only the share of the area they cover is defined."
- Open: dot size (TODO #84), shape, how "cover the ratio fraction" is measured (overlapping dots count once? expected value or exact? per feature or overall), edge behaviour, random seed (not reproducible by definition).
- Implemented: round dots of 2 px diameter (the same as dot patterns); number of dots n = -ln(1 - ratio) x area / (pi r^2), r = 1 px, so that the expected union coverage with overlaps is `ratio`; dot centres uniformly random inside the polygon (rejection sampling with shapely; fixed seed per feature so that renders repeat); dots not clipped at the edge (centres inside). ratio >= 1: solid fill; ratio <= 0: nothing.

### G4. Fill and stroke order / default fill
- Implemented: fill (or pattern), then stroke, then markers within one feature; the fill opacity of a hatch/dot/stipple applies to the dots/lines.
- The `fill` object absent: default fill white opaque for polygons (so a polygon with no fill property but with visibility true is white). The `fill` with `opacity` only: colour default white.

## H. Misc

- `/req/core/default-values`: `opacity` of Fill/Stroke 1 etc. used. `colorChannels` default "For multi-field coverage: fields[0], fields[1], fields[2]" - the fields order of a coverage with several bands is not defined; I use the file-name sort order of the band files (not exercised).
- `/req/core/instances` vs `alter`: the JSON `alter: true` on `stroke` keeps the other stroke members from earlier rules (width 3 px kept, colour changed); clear.
- `visibility` on a parent and on a nested rule: the nested rule's later value overrides; `visibility: false` on a layer rule with nested `visibility: true` rules is the documented pattern (works).
- Rendering order of layers when `zOrder` is equal: from the view's `layers` order ("in drawing order").
- Font files: Arial from the system via cairo's toy font API; hinting/antialiasing of text is the font backend's; unspecified by the text.
- Feature coordinates outside the view are drawn (clipped by the canvas); labels of such features are omitted by D1.
- Properties of the case: `validDate` "is an ISO date" but the GeoJSON gives a string; `marked` booleans compare with `= true`.
- `capabilities.*` identifiers resolve to true in my renderer, though not all classes are implemented (e.g. no feature/visualization passes, no pattern fills with graphics, no variables, no functions beyond the operators used); the normative sentence "resolving to true if and only if the Renderer supports the corresponding requirements class" cannot be checked against the list of classes in a meaningful way because the classes (`rc-math`, `rc-text-manipulation`, ...) are defined elsewhere and I did not implement them. Not exercised by the cases.
