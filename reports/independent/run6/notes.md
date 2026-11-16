# Notes: where the Part 1 (draft) text leaves a choice open

Renderer: `renderer/render.py` (Python, numpy, Pillow, shapely). Output: `out/<case>-<N>.png`, 21 images for 20 cases (vector-units has view-1 and view-2). Choices in the code are marked `CHOICE <id>`.

Each entry: identifier (requirement or clause), the words that leave the choice open, the readings considered, and the one implemented.

## A. Geometry, units and the pixel

**A1. Direction of +y in a Graphic position.** `/req/vector/graphics` ("uom-qualified 2D real position offsetting the graphic"); `UnitPoint` in clause 8 gives x and y without a direction.
- Readings: +y up (Cartesian, as in CRS north-up); +y down (screen coordinates).
- Implemented: +y up. Screen y = anchor y - offset in pixels. Applied to Dot, Text and Image positions and to label offsets.

**A2. hotSpot origin and direction.** `/req/vector/image` ("0,0 position in the image", default `{0.5, 0.5}`); the `Image` table gives `hotSpot` as UnitPoint (uom-qualified).
- Readings: image origin top-left, y down (pixel convention); or the same y-up convention as the Graphic position.
- Implemented: image pixel convention (top-left origin, y down). `{pc 50, pc 100}` is the bottom centre. This contradicts A1 (position y up), so the two conventions differ inside one Marker. Also, the text does not say whether percent refers to the image width/height (implemented that way).

**A3. Standard pixel and the pixel-to-mm conversion.** `/req/vector/units`: "If available, the pixel size depends on the viewer client resolution, otherwise it is equal to 0.28mm x 0.28mm". The view supplies `pixelSize_mm: 0.28`.
- Implemented: 1 px = 0.28 mm everywhere.

**A4. Units named in the text (contradictory lists).** `/req/vector/units` lists "pixel, millimeter, inch, percentage, meter, foot". `/req/dashes/dash-pattern` requires "pixels, points, millimeters, centimeters and inches". The GraphicalUnit enum (clause 8) lists pixels, meters, feet, percent, points, em, screenInches, screenCM, screenMM. The JSON schema uses px, mm, cm, in, pt, em, pc, m, ft. The cases use px, mm, m and pc.
- Implemented: all schema unit keys. `pt` = 1/72 in. `in` = 25.4 mm. `cm` = 10 mm. `m` and `ft` are paper mm at the view's scale (1000/scale mm per metre). `em` = 12 pt (undefined; no case uses it). `pc` = percent of stroke width for dash lengths (permission only, not used); percent of image size for hotSpot.

**A5. Map frame.** The text does not say how `bbox` maps to `width` x `height`.
- Implemented: bbox maps exactly onto the image, no aspect correction. The bbox aspect equals width/height in every view, so this makes no difference here.

**A6. Font size unit.** Font `size` is "(pt)" in the Font table, and the schema gives a plain numeric expression.
- Implemented: points (1/72 in). A 9 pt font is 11.34 px em at 0.28 mm/px.

**A7. Font outline size unit and meaning.** `/req/font-outlines/size` ("a `size` FontOutline property as a float"; "outline extending outward from the glyph contours by the thickness").
- Readings: pixels; points like the font; a fraction of the font size.
- Implemented: points, the same unit as the font size. The halo is the glyph ink dilated by a disc of radius `size` (outward from the contour). Outline opacity defaults to 1 and outline colour defaults to black (both undefined in the text; see D2).

## B. Colour and naming

**B1. RGB values of web colour names.** The schema's `webColorName` enum names colours (e.g. `steelBlue`, `darkRed`), but the spec gives no RGB values.
- Implemented: CSS / SVG values. `fuschia` (schema typo) is mapped to magenta. `grey` spellings are accepted.

**B2. Hex colour strings.** Cases use `"#8a7a5a"` in `colorMap`. The schema's colour types accept only an object, a 3-element array of 0-255 integers, or a web colour name, so hex strings are schema-invalid.
- Implemented: hex strings are accepted.

**B3. Colour value ranges.** `Color` (clause 8 and 9) is r,g,b float; the schema's `color` is 0-255 integers; `color0to1` is 0-1 floats. `/req/coverage/color-channels` says 0 to 1.
- Implemented: 0-255 for `color` objects and arrays, named colours and hex; colorMap and fill use these. `colorChannels` is not implemented (no case uses it).

**B4. Name mismatches between spec and schema or cases.**
- `dataLayer.identifier` (`/req/core/layers`) vs `dataLayer.id` (schema, cases).
- `visualization.*` (clause 7 tables) vs `viz.*` (schema, cases).
- `feature.geometryDimension` (clause 8) vs `feature.geometryDimensions` (schema).
- Stroke `center` (`/req/casing/center`) vs `centerLine` (schema, cases; TODO #120 in the spec).
- Image `url` (`Resource`) vs `uri` (schema, cases). Cases give both `uri` and `path`; I use `path`.
- Implemented: both names of each pair are accepted; `viz.*` and `dataLayer.id` are used in evaluation.

## C. Core: rules, cascade and selection

**C1. Cascade order and nested inheritance.** `/req/core/nested`: "Symbolizer of a selected nested rule inheriting from, and overriding, the Symbolizer properties of its parent rule". `/req/core/rules`: later selected rules override properties set by earlier ones.
- Readings: (a) a nested rule starts from its parent's state as it was when the parent was applied (earlier nested siblings excluded); (b) a nested rule starts from the running state (earlier siblings included), i.e. a pre-order flattening.
- Implemented: (b), pre-order over document order, so a property set by an earlier sibling stays unless a later rule sets it. The two readings differ only when two nested siblings set the same property (no case has this).

**C2. Features matched by no rule (R-unselected).** `/req/core/selector` says a feature is portrayed "only if the rule has no selector or if its selector evaluates to true". The defaults table makes the default Marker (a Dot) visible on every feature.
- Readings: (a) features that no rule selects are not drawn; (b) they are drawn with all defaults (visible, default Dot marker, white fill, black 1 px stroke).
- Implemented: (a). Reading (b) would draw a Dot on every feature of every unselected layer, which contradicts the sense of a selector.

**C3. Object property replaced vs partially updated.** `/req/core/instances` and the JSON section: a complete instance replaces the property; with `alter: true` only given members change. The defaults table fills the rest.
- Implemented: a plain object replaces the whole property, and members not given take their defaults (not the earlier value). Only `alter: true` keeps earlier members.

**C4. NULL results.** `/req/parameter-values/null` gives a table (number 0, Boolean false, colour black, text empty, enumeration default, Marker null). Selectors: `/req/core/selector` NOTE: null does not select. `CQL2` null rules for operators (`/req/core/operations`) are referenced but not spelled out.
- Implemented: selector null is not selected. Operators use three-valued logic (`and`, `or`, `not`). A comparison with null is null. Null visibility is false, null opacity or zOrder is 0, null text is `""`. `?:` takes the else branch unless the condition is true.

**C5. Date comparisons.** `validDate` is a string in the GeoJSON; `viz.timeInterval.*.date` is a date (clause 7 `Date`). Comparison of a string to a date is not defined.
- Implemented: ISO date strings compared as strings (same order as dates).

**C6. Equality of mismatched types.** Not defined (`=` between a number and a string).
- Implemented: unequal (False).

**C7. Zero-width stroke.** Not stated (`width 0.0` appears in vector-marker-dot).
- Implemented: no stroke drawn.

**C8. Feature order and z-order.** `/req/core/z-order`: features of a single rendering pass are drawn "in increasing order of their resolved zOrder". Within one zOrder the text does not give an order; the view gives "the layers in drawing order".
- Implemented: sort by zOrder, then by view layer order, then by feature order in the file. Labels are a separate pass on top of all features (`/req/labels/label`).

**C9. Coverage selectors per cell.** `/req/core/selector` applies "to a feature or coverage cell". Selectors on band values per cell are not described in the text.
- Implemented: the coverage layer is selected at layer level (band names are not visible to selectors). Selectors on band values are not supported; no case uses them. This is a limitation of this renderer, not a spec choice.

**C10. Opacity applied together.** `/req/core/opacity` multiplies opacity by "the fill, the stroke, the graphics of markers"; `/rec/core/opacity-together` (SHOULD) asks them to be applied together.
- Implemented: fill, stroke and markers of a feature are composited as one group, then the group is multiplied by the symbolizer opacity (satisfies the SHOULD).

**C11. Default fill and stroke for polygons.** The defaults table gives fill white and stroke black 1 px.
- Implemented: a visible polygon with no fill set is white; no stroke set means black 1 px outline. No case relies on either.

## D. Vector: fills, strokes, markers, dots

**D1. Dots.** `/req/vector/dot`: size is the stroke width, colour is the stroke colour, "drawn as a filled circle". Negative size: not stated. `core-parameters` produces negative sizes (SpotHeights has elevation 878, size (878-900)/100 = -0.22).
- Implemented: a size of 0 or less draws nothing (anti-aliased disc otherwise).

**D2. Dot outline and missing defaults.** `/req/vector/dot` NOTE: "A Dot with an outline is drawn with two concentric Dots". Default colours are not given for FontOutline and Font (only Stroke, Fill, Dot and Image).
- Implemented: font colour default black; outline colour default black; outline opacity default 1; text alignment default centre/middle (see G5). Fonts other than Arial fall back to Arial (only Arial files are installed).

**D3. Marker anchors on lines and polygons.** `/req/vector/marker` says markers are drawn "at the points of vector geometry (for points and line strings) and at the centroid of polygons". "Points of line strings" can mean vertices or any point. The NOTE on the default marker says "at each vertex of a line".
- Implemented: every vertex of a line. Polygons: area centroid (shapely `centroid`); the text does not say which centroid for polygons with holes.

**D4. Marker elements order.** Not stated.
- Implemented: elements drawn in array order, each at the anchor plus its own position offset.

**D5. Image size and scale.** `/req/vector/image` gives no size property (`GraphicSize` is abstract and has no members). Image size is not specified.
- Implemented: 1 image pixel = 1 px (0.28 mm), nearest-neighbour when supersampled. Image path resolved relative to the case folder (README).

**D6. Image recolouring and alphaThreshold.** The recolour formula `tint × v + blackTint × (1 − v)` is given; `alphaThreshold` has only a permission (MAY).
- Implemented: the formula, applied per channel; alpha kept. `alphaThreshold` ignored (permitted).

## E. Strokes, dashes and casings

**E1. Dash offset sign and origin.** `/req/dashes/dash-offset`: "dashing ... based on a dashOffset property" (figure caption only). Sign and direction are not given.
- Implemented: pattern position at arc length s is (s + offset) mod L, as SVG `stroke-dashoffset`: a positive offset shifts the pattern backwards, so the first dash starts earlier. The pattern starts at the first vertex of each line (and at the first vertex of each ring, for polygons).

**E2. Dash arrays with an odd number of entries.** Not stated.
- Implemented: the array is doubled (SVG-like), so the on/off order alternates on every repetition.

**E3. Dashes over vertices and ends.** Not stated. The text gives butt caps and miter joins as defaults (clause 8, stroke) — these are from the spec text.
- Implemented: dash length measured along the polyline (continuous over vertices); each dash has butt caps and miter joins (miter limit 5, the shapely default; the limit itself is not in the spec).

**E4. Casing width.** `/req/casing/casing`: "a total width of the main stroke's width plus twice the casing's width" (in the text). The casing's default and dashes are not stated.
- Implemented: total width = main + 2 × casing width; casings are solid even when the main stroke has dashes; a casing with no width given uses the stroke default of 1 px.

**E5. Order of casing, fill and centre line.** `/req/casing/casing`: the casings of all features of the same zOrder are drawn beneath the main strokes of all those features. `/req/casing/center`: the centre line is "on top of the main stroke" (no ordering relative to other features).
- Readings: (a) centre lines after all main strokes of the same zOrder; (b) each centre line immediately after its own main stroke.
- Implemented: (a). Pass order per zOrder: all casings, then per feature: fill, main stroke, markers; then all centre lines. A polygon fill of the same zOrder is drawn after line casings, so it can cover a casing (the text does not say).

## F. Hatches, dot patterns and stipples

**F1. Hatch angle reference and direction.** `/req/hatches/angle`: "Hatches orientation clockwise degree"; the TODO (#146) notes that the zero direction and turning direction differ from gradient angles.
- Readings: 0 = horizontal, 90 = vertical; clockwise on screen (y down) or counter-clockwise.
- Implemented: 0 = horizontal lines, 90 = vertical, turning clockwise on the screen; 45 gives lines running down to the right.

**F2. Hatch width, distance and phase.** `/req/hatches/distance` gives no measure of "distance" (perpendicular or along the line); phase is not given.
- Implemented: distance is perpendicular spacing in px; lines are at multiples of the distance measured from the image's top-left corner (fixed phase across features); anti-aliased; width is the line thickness in px.

**F3. Hatch colour and background.** The Fill's `color` is the only colour given. Whether the solid fill is also drawn under the hatch is not stated.
- Implemented: hatch lines in the fill colour with the fill opacity; no solid background when a hatch is set. A caption gives the default hatch values (width 1 px, angle 45 degrees, distance 10 px); the normative table has no defaults. I used the caption values as defaults.

**F4. Stipple dot size, colour and ratio meaning.** `/req/stipples/ratio`: "Ratio of stippling dots according to area filled"; the TODO (#84) says dot size and colour are not defined.
- Readings: ratio as the fraction of the area covered by dots; ratio as the fraction of grid cells with a dot.
- Implemented: dots on a regular 4 px grid from the image origin, with radius chosen so that dots cover `ratio` of the area (π r² / pitch² = ratio). Colour is the fill colour with the fill opacity. Dots are clipped to the polygon.

**F5. Dot pattern dot size and colour.** `/req/dot-patterns/distance` gives the spacing; TODO (#84) notes that dot size and colour are not defined. Default spacing is not given.
- Implemented: dots of diameter 2 px on a grid of horizontal × vertical spacing from the image origin, colour = fill colour, clipped to the polygon. Default spacing (not used): 10 px.

**F6. Precedence of fill patterns.** Hatch, dotpattern and stipple can all be set on one Fill; the text does not say what happens.
- Implemented: hatch, then dotpattern, then stipple (only one is drawn).

## G. Coverage, hill shading and colour maps

**G1. Cells to pixels.** `/req/coverage/*` describe a cell's colour and opacity but not how a cell covers output pixels. `rec/coverage/map-interpolation` concerns colour between map entries only.
- Implemented: nearest-neighbour sampling at each output pixel centre (4× supersampled, then averaged). Cells larger than the pixel show as blocks; no interpolation between cells.

**G2. No-data cells.** The ASC grids have `NODATA_value -9999`. The text does not mention no-data.
- Implemented: no-data cells are not drawn (alpha 0) and are excluded from hill-shading neighbours.

**G3. Resolution used for hill shading.** `/req/hill-shading/hill-shading`: slope is computed "from the differences in elevation between neighbouring samples of the elevation coverage at the resolution being rendered, over the horizontal distance between those samples". "At the resolution being rendered" can mean the native cell size, or resampling to the output pixel.
- Implemented: the native cell size (150 m here). Shade is computed once per cell and sampled to pixels (G1). The view at 75 m/px therefore shows each cell as 2 × 2 px blocks.

**G4. Edge cells and missing neighbours.** Not stated.
- Implemented: central difference when both neighbours exist; one-sided difference when one neighbour exists; zero slope when none exists. The north row is row 0 of the ASC grid.

**G5. Which samples hill shading differentiates.** The text says each cell gets a shade from its own elevation and its neighbours; `factor` and `sun` define the normal and light.
- Implemented: for each cell, the normal is (−factor·∂z/∂E, −factor·∂z/∂N, 1) normalised, with ∂z/∂E from east-west neighbours and ∂z/∂N from the north and south neighbours; shade = clamp(n · s, 0, 1), s = (sin az cos el, cos az cos el, sin el).

**G6. Defaults for hill shading.** `factor` is "0..1" in the table with no default; `sun` has no default.
- Implemented: factor 1 when absent; sun azimuth 315 and elevation 45 when absent (undefined in the text; not used by any case).

**G7. Symbolizer colorMap with hillShading.** `/req/hill-shading/hill-shading`: "where the HillShading has no colorMap, multiplying the red, green and blue components of each cell by its shade value". The text does not say where the colour of a cell with a Symbolizer colorMap comes from when hillShading is also set.
- Readings: (a) the Symbolizer colorMap gives the base colour, which is multiplied by shade; (b) hillShading ignores the Symbolizer colorMap.
- Implemented: (a). With a HillShading colorMap, the shade indexes that map and replaces the base colour (it does not multiply). The HillShading opacityMap multiplies the alpha. With no colour map at all, the base is white (colorChannels default is not given for single-field coverages).

**G8. Colour and opacity interpolation.** `/req/coverage/color-map`: "interpolating between the colors of the two closest entries". `rec/coverage/map-interpolation` (SHOULD) allows linear or smoother methods; the NOTE leaves the method open.
- Implemented: linear interpolation of r, g, b (and of opacity) in the stored colour space (no gamma handling). Values outside the map take the first or last entry.

**G9. Alpha channel.** `alphaChannel` (`/req/coverage/alpha-channel`) and the opacityMap both give opacity; the product is not specified.
- Implemented: alpha = alphaChannel × opacityMap value × HillShading opacityMap value, then multiplied by the symbolizer opacity.

## H. Labels

**H1. Priority direction.** `/req/labels/placement`: "placed in preference to a conflicting label with a lower priority"; TODO (#148) asks whether a higher priority value means higher priority.
- Implemented: higher value = higher priority. Null priority = 0.

**H2. Overlap rule.** `/rec/labels/overlap` (SHOULD): omit labels that "cannot be placed without overlapping other labels". The text gives no algorithm and does not say whether markers or Dots take part.
- Implemented: greedy placement in priority order (ties: document order). A label is omitted when its box overlaps any placed label box (box = union of its Text boxes plus halo; Dots included). Markers (and text inside markers) do not take part, so overlaps with markers are allowed.

**H3. Label boxes.** The text does not define the label extent.
- Implemented: box = advance width × (ascent + descent) line box, plus the halo radius.

**H4. Anchor for polygons.** Not stated.
- Implemented: area centroid. A label on a line is placed at the arc-length positions in H5.

**H5. Label repetition along lines.** `/req/labels/placement`: "repeating a label so that the distance between repetitions of that label is at least minSpacing and, where space allows, at most maxSpacing, both in pixels". Not stated: the position of the first repetition, use of maxSpacing when only minSpacing is given, and what a line without minSpacing gets.
- Implemented: repetitions at spacing = minSpacing, symmetric about the line midpoint (midpoint is always one), measured along the line in device pixels. maxSpacing is not used (not given by any case). A line without minSpacing gets one label at its midpoint.

**H6. Label orientation.** The text does not say whether text on a line follows the line direction.
- Implemented: all labels are horizontal (not rotated).

**H7. Labels partly outside the map.** Not stated.
- Implemented: a label is omitted only when its anchor is outside the map; a label that extends past the edge is drawn and clipped by the image edge.

**H8. Label visibility.** The text does not say whether a label belongs to a feature whose Symbolizer has visibility false.
- Implemented: a label is drawn only for features whose resolved visibility is true.

**H9. Label opacity.** `Symbolizer opacity` "does not apply to labels" (NOTE, `/req/core/opacity`).
- Implemented: labels are not multiplied by the symbolizer opacity; their font opacity applies.

**H10. Text alignment defaults and "middle".** The Text table gives `alignment` as optional, with no default.
- Implemented: default horizontal `center`, vertical `middle`. `top` and `bottom` align the ascent and descent lines; `middle` is the centre of the ascent+descent box.

**H11. Font face.** The Font face is a string; the text does not say what happens with unknown faces.
- Implemented: Arial in regular, bold and italic (the only faces installed).

**H12. Repetition of text outlines.** Not an issue; included for completeness: outline and text are drawn per Text element, and each halo sits under its own glyph.

## I. JSON encoding and expressions

**I1. Named object members.** `/req/json/expressions` says CQL2-JSON "extended as specified by the JSON Schema". The schema's operator set (`=`, `<`, `and`, `+`, `/`, `?:`, `isNull`, `in`, `between`, ...) is used by the cases. `bitwise` and spatial operators are in the schema but unused and not implemented.
- Implemented: the operators the cases use, plus `^`, `in`, `between`, `isNull`, `?:`. Other operators raise an error.

**I2. Schema bugs.** `colorComponent0to255` has `"mininum"` (typo, so the minimum is not enforced); `webColorName` has `"fuschia"`; colour names in the enum are not consistently cased (`lightGoldenRodYellow`, `honeyDew`).
- Implemented: the typos are not relied upon (fuschia mapped to magenta).

**I3. Array-form alignment and hotSpot.** The schema allows `alignment` and `hotSpot` as arrays or objects; the spec uses separate members (`horzAlignment`, `vertAlignment`, `hotSpot` as UnitPoint).
- Implemented: both forms are accepted.

**I4. Identifiers that are not in the schema.** The cases use `visualization`-style names only through the schema's `viz.*` identifiers (see B4). `viz.timeInterval.start.date` and `end.date` exist in the schema.
- Implemented: schema names.

**I5. Variables, includes, functions.** Not used by any case.
- Not implemented (`$variables`, `$include`, function calls).

## J. Clause and table errors found

- clause 7, `Visualization System Identifiers`: `visualization.timeInterval` is described as "Current visualization time of day" (copy error; it is a TimeInterval).
- clause 7, `TimeOfDay` table: `minutes` has data type `Month` (copy error).
- clause 7 defaults: `colorChannels` default "uses the first three fields unscaled, while colorChannels is 0 to 1" (TODO #150) — the default is contradictory with the 0-1 range.
- clause 8: the `uom` inheritance rule for Graphic and Font is only in commented-out text (marked TOCHECK), while `/req/vector/units` says each distance is "uom-qualified". Which unit scope applies is therefore not settled; the renderer uses the unit on each value.
- `/req/core/time` requires `visualization.dateTime`, `date`, `timeOfDay` and `timeInterval`; the schema names them `viz.dateTime`, `viz.date`, `viz.timeOfDay` and `viz.timeInterval`. Naming differs (see B4) but the set is the same.
- `/req/casing/center` and the schema disagree on `center` vs `centerLine` (TODO #120).
- `/req/labels/placement` priority direction (TODO #148).
- `/req/hatches/angle` direction (TODO #146).
- `/req/stipples/ratio` and `/req/dot-patterns/distance`: dot size and colour undefined (TODO #84).
- The defaults for `Font` (size, colour) and `FontOutline` (opacity, colour) are not given in any table.
- Figure captions contain default values (hatch 1 px, 45°, 10 px) that the normative tables do not repeat.

## K. Data observations (not renderer choices)

- `font-outlines/Places.geojson`, `labels-priority/Places.geojson` and `vector-text/Places.geojson` hold names that are double-encoded UTF-8 (for example `BjÃ¸rnhollia`); they are rendered as stored.
- `Landcover` `area` values are in square metres as stored; no unit conversion is applied.
- `core-parameters` has SpotHeights with elevations below 900 (minimum 878), so the Dot size formula gives negative sizes (see D1).
- `$comment` fields in the case styles are not used for rendering.
- `vector-units` has two views, so 20 cases give 21 images.
