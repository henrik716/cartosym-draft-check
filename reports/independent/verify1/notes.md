# Notes: choices made where the requirement text leaves rendering open

Renderer: `renderer/render.py` (Python, numpy, Pillow, pycairo, shapely). Output: `out/<case>-<N>.png`, 21 images for 20 cases (`vector-units` has two views). Every case rendered.

Each entry gives the requirement (or clause/table), the words that leave the choice open, the readings I considered, and what I implemented (**Implemented**). Entries marked **Contradiction** or **Undefined** are places where the text disagrees with itself or uses something it does not define.

General: the `include::../examples/...` blocks and all figures are not in `spec/`, so the worked examples the text refers to ("as example 11 does", "example 6", the figures for hatches, dashes and stipples) could not be used.

---

## A. Core

### A1. Features that no rule selects (`/req/core/symbolizer`, part 3)
- Words: "A Renderer SHALL support portraying, with the default values, the features and coverage cells that no StylingRule selects".
- Readings: (a) draw them with the default Symbolizer (white fill, 1 px black stroke, default Marker = one white 10 px Dot); (b) leave them out, as many SLD renderers do.
- **Implemented (a)**, literally. Consequence: in `core-opacity` the rule is `Landcover[class = 'lake']`, so every non-lake polygon is drawn with a white fill, a black 1 px outline and a white 10 px Dot at its centroid. White fills of large polygons that come later in the data hide what was drawn before them. The text is clear, but it is easy to miss that this also brings in the default Marker (see A7).

### A2. What a later rule replaces (`/req/core/rules`, `/req/core/instances`, `/req/json/partial-update`)
- Words: "SHALL be interpreted as overriding all Symbolizer properties set by earlier rules"; JSON `alter`.
- Readings: when a later rule sets an object property *without* `"alter": true`, the members it does not give (a) fall back to their defaults, or (b) keep the values from earlier rules.
- **Implemented (a)**: an object without `alter` replaces the whole earlier value; only `alter: true` merges member by member (recursively); `{index, value}` replaces one array element. Example: in `vector-marker-dot`, `stroke: { width: 0 }` resets the stroke colour to the default black (it does not matter here because the width is 0).

### A3. Names of system identifiers (Core, "Visualization System Identifiers" and "Layer System Identifiers" tables)
- **Contradiction/Undefined**: the text names `visualization.scaleDenominator`, `visualization.timeInterval` and `dataLayer.identifier`. The cases (and the JSON schema's `sysId` enum) use `dataLayer.id`, `viz.sd` and `viz.timeInterval.start.date`. The CSCSS examples use `viz.sd` but never define `viz`/`sd` as aliases. `…timeInterval.start.date` exists only through the UML (TimeInterval.start: TimeInstant, TimeInstant.date), not in any table. The feature table says `feature.geometryDimension` while the UML and schema say `feature.geometryDimensions`.
- **Implemented**: `viz.` = `visualization.`, `sd` = `scaleDenominator`, `dataLayer.id` = `dataLayer.identifier`; members of the time interval follow the UML.

### A4. Comparing a date with a text value (`/req/core/relational`)
- Words: "The first operand is greater than or equal to the second one". The text does not say how a property holding the text `'2019-05-01'` compares with a Date.
- Readings: (a) parse an ISO date text as a date; (b) compare as text; (c) the comparison is null (type mismatch).
- **Implemented (a)**. For ISO dates (a) and (b) give the same order.

### A5. A property missing from a feature (`/req/core/expressions-field-identifiers`)
- Words: "resolving an Identifier Expression to the value of the named feature property". In `dashes`, `marked` is missing from some features.
- **Implemented**: a missing property is null. Comparisons with null give null (CQL2), and null does not select (the NOTE under `/req/core/selector`).

### A6. zOrder ties and scope (`/req/core/z-order`)
- Words: "portraying features and coverage cells of a single rendering pass in increasing order of their resolved zOrder".
- Open: the order among equal zOrder values, and whether zOrder sorts across layers.
- **Implemented**: a stable sort over all layers of the view. Ties keep the view's layer order, then the feature order in the file. zOrder sorts across layers ("modify default order of features / layers" in the Visual Ordering table). The default zOrder is 1.

### A7. Default Marker on lines and polygons (`/req/core/default-values`, NOTE; `/req/vector/marker`)
- Words: "draws a Dot at each point, at each vertex of a line and at the centroid of each polygon".
- Open: "centroid" can mean the area centroid (which can fall outside the polygon) or a point on the surface.
- **Implemented**: the area centroid of the polygon with its holes (shapely `centroid`). A marker on a line goes on every vertex, including the first and last.

### A8. Default Dot vs default Stroke (`/req/core/default-values` vs `/req/vector/dot`)
- **Contradiction**: a Dot's size and colour *are* its stroke's width and colour, but the default table gives Dot size 10 px / white while the Stroke default is 1 px / black.
- **Implemented**: the Dot table (10 px, white) for a Dot.

### A9. Opacity applied together, with casing and centre lines (`/rec/core/opacity-together` vs `/req/casing/*`)
- Words: "apply the Symbolizer opacity to the fill, the stroke and the graphics of markers of each feature together".
- **Implemented**: each feature's fill, main stroke and marker go into one group, which is composited with the Symbolizer opacity. Because casings and centre lines must be drawn in separate passes (C1), they are composited in their own groups with the same opacity, so a feature's casing shows through its main stroke where both are translucent. No case combines the two.

### A10. Order inside one feature (not stated normatively)
- Open: whether the fill, stroke and marker are drawn in that order. Only the informative Annex F says "the filling is rendered first and then the stroking".
- **Implemented**: fill, then stroke, then marker. Marker elements are drawn in list order, first at the bottom (as the NOTE on Dot outlines implies: "the larger one first").

---

## B. Basic vector styling

### B1. (Choice 1) Direction of +y in a Graphic position (`/req/vector/graphics`)
- Words: "a positive `x` of the position as an offset to the right and a positive `y` as an offset upwards on the map, as for `Displacement` in SE 1.1".
- **Implemented**: +y is upward, so `position: 12 -12` puts the small Dot 12 px right of and 12 px below the hut, and the label `position: 0 8` sits 8 px above the peak.
- **Contradiction**: Annex B maps "Marker position" to `<AnchorPoint>`, not to `<Displacement>`. The Image `hotSpot` uses y downwards (B6), so the two point types in one Graphic run in opposite directions.
- A number without a unit in a position is pixels (clause 17 units table: "For screen-space objects, defaults to pixels").

### B2. Which geometries get fill and stroke (`/req/vector/fill`, `/req/vector/stroke`)
- Words: "filling vector geometry", "drawing the stroke of vector geometry".
- Open: whether a point gets a fill or stroke, and whether a line gets a fill.
- **Implemented**: fill only on polygons. Stroke on lines and on every polygon ring, holes included. Points get neither, only markers. The polygon fill rule is even-odd, so holes are left empty; the text does not give a fill rule.

### B3. Joins, caps and anti-aliasing (clause 8, "Strokes")
- Words: "butt caped and … miter joined". No miter limit is given, and anti-aliasing is not mentioned anywhere.
- **Implemented**: butt caps, miter joins with a miter limit of 4 (the SVG default), anti-aliased drawing with cairo.

### B4. Units (`/req/vector/units`, `/req/dashes/dash-pattern`, clause 17 units table, JSON schema `unitValue`)
- **Contradiction**: the unit lists differ. `/req/vector/units` has pixel, millimeter, inch, percentage, meter, foot. Dashes add points and centimeters. Clause 17 has px, m, ft, pc, pt, em, inch, cm, mm. The schema has px, mm, cm, in, pt, em, pc, m, ft. Percent of a stroke width is undefined.
- Open: the pixel size and the ground scale. Words: "If available, the pixel size depends on the viewer client resolution, otherwise it is equal to 0.28mm".
- **Implemented**: mm per pixel from the view's `pixelSize_mm` (0.28). Metres per pixel = bbox width / width in pixels; that equals `scaleDenominator × pixelSize` in both views of `vector-units`, so it does not matter which one is used. 1 pt = 25.4/72 mm; the table's "0.3528 mm" is rounded. A bare number is pixels.

### B5. Dot (`/req/vector/dot`)
- **Implemented**: an anti-aliased filled circle of diameter `size`. `Graphic.opacity` and the Dot's stroke opacity multiply; neither has a default in the defaults table, so I use 1. A size of 0 or less draws nothing (stated). `core-parameters` computes a unitless size, (elevation − 900)/100, which I read as pixels.

### B6. (Choice 11) Image hotSpot and a number without a unit (`/req/vector/image`)
- Words: "from its top left corner with `x` to the right and `y` downwards, where a number without a unit is a fraction of the image's width or height, a value in `pc` is a percentage of it, and a value in another unit is a length from that corner".
- **Implemented**: as written. The origin is the top-left corner, and `50 pc 100 pc` is the bottom centre (12, 24) of the 24×24 icon. A bare number is a fraction, so 0.5 is the middle; another unit is a length (px).
- **Contradiction**: the clause 17 units table says a number without a unit "For screen-space objects, defaults to pixels", which would make a bare hotSpot of 0.5 mean half a pixel. Only "For relative values like scaling, 100 times less than if pc" agrees with the requirement.
- **Undefined**: the size at which an Image is drawn; there is no size or scale property. **Implemented**: native size, one image pixel per map pixel. The top-left corner is snapped to the pixel grid so the icon is not resampled; the alternative is drawing at the exact sub-pixel position with bilinear filtering.
- **Contradiction**: the Resource table says `url`, the schema and the case say `uri`. A relative `path` is not said to be relative to what. **Implemented**: relative to the folder of the style file.
- Tint: `tint × v + blackTint × (1 − v)` on the 8-bit sRGB values divided by 255 (not linear light, which the text does not specify). Alpha is unchanged. `alphaThreshold` is not used (the MAY in `/per/vector/image-alpha-test` is not taken).

### B7. Text (`/req/vector/text`, `/req/vector/fonts`)
- **Contradiction**: the alignment member names differ: the UML uses `horizontal`/`vertical`, the TextAlignment table `horzAlignment`/`vertAlignment`, the schema `hAlignment`/`vAlignment`. The cases use the array form, so it did not matter here; all three are accepted.
- Words: "`top` the top of the font's ascent, `bottom` the bottom of its descent". Open: which ascent metric (hhea, OS/2 typo, win). **Implemented**: the font's ascent and descent as cairo reports them (on Windows, the GDI/win metrics; for Arial about 0.905 and 0.212 em). "Start" and "end" of the text use the advance width, not the ink bounds.
- Font `size` "(pt)": I read it as the em size, so 9 pt = 9 × 1.26 = 11.34 px.
- **Undefined**: `Font.color` and `Font.opacity` appear only in the UML, not in the Font table. There are no defaults for face, size or colour. **Implemented**: if unset, Arial, 10 pt, black, opacity 1; every case sets face, size and colour.
- **Undefined**: how a number becomes text (`text: elevation`). **Implemented**: integers as-is ("2016"), integral reals without decimals.
- Text in a Marker is drawn with the feature (Symbolizer opacity applies) and is never checked for collisions, so the two co-located peaks in `vector-text` overprint each other.

---

## C. Casing, centre lines and dashes

### C1. (Choice 6) Centre lines per feature or after all main strokes (`/req/casing/center`, `/req/casing/casing`)
- Words: "drawing, within a single visualization pass, the center lines of all features with the same `zOrder` on top of the main strokes of all those features" (casing: "the casings of all features with the same `zOrder` beneath the main strokes of all those features").
- **Implemented**: after all main strokes. For each zOrder: (1) every casing; (2) every feature in turn (fill, main stroke, marker); (3) every centre line.
- Open: where fills and markers go relative to these passes; the text only places casings and centre lines relative to *main strokes*. With my order, a polygon fill at the same zOrder covers casings drawn earlier, and markers are under centre lines.
- Casing: one stroke of width main + 2 × casing width, with the same caps and joins, beneath the main stroke ("for a total width of the main stroke's `width` plus twice the casing's `width`"). Open: whether the main stroke's dash pattern applies to the casing or centre line. **Implemented**: it does not (not used in the cases).
- **Contradiction**: the property is `center` in the text but `centerLine` in the schema (TODO in the text). Both are accepted; the case uses `center`. There are no defaults for casing or centre-line members; the Stroke defaults are used.

### C2. (Choice 2) Meaning of dashOffset (`/req/dashes/dash-offset`)
- Words: "as the distance into the dash pattern at which dashing starts at the beginning of each line (as `stroke-dashoffset` in SVG and SE 1.1) … with a `dashPattern` of `[ 8, 4 ]` and a `dashOffset` of 4, each line starts with a 4 pixel dash, then a 4 pixel gap".
- **Implemented**: SVG semantics (cairo `set_dash(pattern, offset)`). The pattern restarts at the start of each line and of each polygon ring and runs on across vertices. Each dash has butt caps.
- Open: "in the units of the dash pattern", when each pattern element can carry its own unit. **Implemented**: dashOffset is converted with its own unit (px if none). The UML gives `dashOffset: float` while the table gives `UnitValue`.
- `1 mm` dashes are 3.571 px long, which is not a whole number of pixels, so they come out anti-aliased.

---

## D. Fills

### D1. (Choice 9) Hatch colour, angle reference and direction, and phase (`/req/hatches/hatch`, Hatch table)
- Colour. Words: "drawn in the `color` and `opacity` of the Fill, without painting the area between the lines". **Implemented**: the Fill colour and opacity; nothing between the lines.
- Angle. Words: "in degrees, where 0 gives horizontal lines and angles turn counter-clockwise as seen on the map". **Implemented**: 0 is horizontal, 45 rises to the right, 90 is vertical. The TODO under the table says the earlier text said clockwise and was changed to match a figure, so this point had already been contested.
- Phase. Words: "with a line through the top left corner of the map". Open: the corner point of the image (0, 0), or the centre of the top-left pixel (0.5, 0.5). **Implemented**: the corner point. Line centres are at signed distances k × distance from (0, 0), measured across the lines.
- **Undefined**: default hatch values appear only in a figure caption ("width : 1 px, angle : 45 °, distance : 10 px"), not in the defaults table. **Implemented**: those values. Lines are anti-aliased and clipped to the polygon; the polygon stroke is drawn on top.

### D2. Dot patterns (`/req/dot-patterns/*`)
- Words: "each drawn as a filled circle with a diameter of 2 pixels"; "its first point half the horizontal and half the vertical distance from the top left corner of the map".
- Open: a dot that straddles the polygon edge. Readings: draw only dots whose centre is inside, or clip every dot to the polygon. **Implemented**: clip to the polygon.
- **Contradiction**: the TODO "define the size and color of the rendered points (see #84)" is stale, because the requirement now defines both. The schema's `dotpattern` object is malformed (`distance` is not under `properties`). There is no default distance; I use 10 px, but it is not needed here.

### D3. (Choice 5) Stipple dots (`/req/stipples/ratio`)
- Words: "dots … placed at random so that they cover the `ratio` fraction of the area"; NOTE: "The size of the dots and their placement are left to the Renderer".
- **Implemented**: dots of one pixel (1×1, not anti-aliased). Each pixel whose centre is inside the polygon is painted when a fixed, seeded random value for that map pixel is below `ratio`. The seed is a constant, so the result is repeatable and the same pixel gets the same decision in every feature. The covered share equals `ratio` in expectation.
- Readings not chosen: round dots of a few pixels with Poisson-disc spacing, or a seed per feature. Two renderers cannot be expected to match on this point.

---

## E. Coverages and hill shading

### E1. (Choice 3, part 1) How coverage cells map to output pixels (`/req/coverage/single-channel`, part 3)
- Words: "each pixel of the map whose center lies in a cell takes the color and opacity of that cell".
- **Implemented**: nearest cell by pixel centre, with no interpolation between cells. Pixels outside the grid are left transparent.
- Open: a pixel centre that lies exactly on a cell edge. This happens in `font-outlines`: the pixel centre at x = 222550 m lies on a cell boundary. **Implemented**: cells are half-open: column = floor((x − xll)/cellsize), row = floor((ytop − y)/cellsize). A pixel centre on a vertical edge goes to the cell to the east, and one on a horizontal edge to the cell to the south.

### E2. (Choice 3, part 2) Which samples hill shading differentiates (`/req/hill-shading/hill-shading`)
- Words: "using as samples the cells of the elevation coverage where the map's resolution is as fine as the coverage's or finer … taking for each direction the difference between the two samples on either side of the cell over twice the distance between samples (repeating the edge sample at the edge of the coverage)".
- **Implemented**: in all three coverage cases the map is finer (75 m and 28 m per pixel, against 150 m cells), so the samples are the 150 m cells. dz/dx = (z[c+1] − z[c−1]) / (2 × 150 m), and likewise north–south. At the edges the edge cell is repeated and the divisor stays 2 × cellsize, as the words say, which halves the slope in the edge cells (the alternative would be a one-sided difference over 1 × cellsize). The shade is computed per cell and then mapped to pixels as in E1. The case of a coarser map than the coverage is not implemented, since no case needs it.
- Normal: n = (−f·dz/dx, −f·dz/dy, 1), normalised after multiplying the horizontal components by `factor` (`/req/hill-shading/factor`). Shade = clamp(n · s, 0, 1).
- Open: "North" in "degrees clockwise from North, as a compass bearing" can be grid north or true north. **Implemented**: grid north (up on the map). In EPSG:25833 at about 9.8°E, 62°N, the meridian convergence is about 4.5°, so the two readings give visibly different shading.
- Elevation and horizontal distances are both taken as metres. The grid has no vertical unit; the text asks for "the same units as the elevation".
- No HillShading `colorMap`: the RGB from the Symbolizer `colorMap` is multiplied by the shade. Alpha is unchanged (opacity map and alpha channel of the cell). There are no defaults for `factor` or `sun`; I use 1 and 315°/45°, but they are not needed.

### E3. colorMap / opacityMap interpolation (`/rec/coverage/map-interpolation`)
- Words: "The interpolation method is not specified".
- **Implemented**: linear interpolation. The colour space is not specified either; I interpolate the sRGB-encoded components (not linear light, not Lab). Values outside the map take the first or last entry (stated).

### E4. Combining opacities on coverages (`/req/coverage/alpha-channel`, `/req/coverage/opacity-map`, `/req/core/opacity`)
- Open: how `alphaChannel` (default 1) and `opacityMap` combine.
- **Implemented**: multiplied, then multiplied by the Symbolizer `opacity`.
- **Contradiction**: the schema types `singleChannel` and `alphaChannel` as `zeroToOne`, but `singleChannel: elevation` carries values of 285 to 2159 m. The TODO on the default `colorChannels` (unscaled fields vs 0 to 1) is also open.

---

## F. Labels and font outlines

### F1. (Choice 4) Labels partly outside the map (`/rec/labels/overlap`)
- Words: "SHOULD omit labels which would extend beyond the edges of the map, except where the map is drawn in tiles".
- **Implemented**: omitted. A label is dropped if its box crosses an edge.
- Open: what "the label" is in size. **Implemented**: the union of its elements' boxes. For text, the box is the advance width by the font ascent plus descent, grown by the outline size on every side; the alternative would be the ink bounds.
- Overlap: "SHOULD omit labels which cannot be placed without overlapping other labels, unless a property of the Symbolizer allows the overlap". **Undefined**: no such property exists in Part 1. **Implemented**: no two label boxes may overlap. Labels are not tested against markers or lines.

### F2. Priority (`/req/labels/placement`)
- Words: "a label with a higher `priority` is placed in preference". The TODO under it says the meaning of "higher" is not confirmed.
- **Implemented**: a larger number wins. **Undefined**: the default priority; I use 0. A null priority (peaks without `elevation`) is 0, from the null table in `/req/parameter-values/null`. Ties keep drawing order (zOrder, layer, feature).

### F3. Where a label goes (`/req/labels/*`)
- **Undefined**: the anchor of a label. Only Markers have a stated anchor.
- **Implemented**: a point for point features, the centroid for polygons (as for markers), and the Graphic `position` offset from there (B1). Default alignment is centre/middle.
- For lines, nothing is said about position or orientation. **Implemented**: candidate anchors every 4 px of length along each line, starting at its first vertex, tried in order. Text stays horizontal, because Part 1 has no rotation or follow-line property. Without `minSpacing`, a line gets one label at mid-length.

### F4. (Choice 7) Label repetition along lines (`/req/labels/placement`, parts 3 and 4)
- Words: "repeating a label so that the distance between repetitions of that label is at least `minSpacing` and, where space allows, at most `maxSpacing` … treating as repetitions of a label all labels with the same content from the same data layer … measuring the distance between repetitions on the map between their positions".
- **Implemented**: greedily, a candidate (F3) is accepted if it is inside the map, overlaps no placed label, and lies at least `minSpacing` px (straight-line distance between anchors) from every placed label with the same text in the same layer. Labels therefore repeat as often as `minSpacing` allows. Features are processed in data order and each line from its start; this order is my choice and affects where the labels land.
- Open: "on the map" can mean straight-line distance or distance along the line. **Implemented**: straight-line.
- Open: "where space allows, at most `maxSpacing`" gives no procedure. With no `maxSpacing` set there is no upper limit; my greedy walk does not enforce one (no case sets it). In `labels-spacing` the "6" labels end up about 285 to 290 px apart, which satisfies "at least 150" but shows how loosely the result is defined.
- **Undefined**: the default `minSpacing`. **Implemented**: no spacing limit (each point feature gets its own label).
- The unit of `minSpacing` is "pixels unless qualified", but the schema types it as a plain number with no unit object.

### F5. Label pass and opacity (`/req/labels/label`, NOTE under `/req/core/opacity`)
- **Implemented**: all labels are drawn after every layer and zOrder, in placement order. The Symbolizer opacity is not applied (the NOTE says so); the font opacity and the outline opacity are.

### F6. (Choice 10) Font outline size: unit and meaning (`/req/font-outlines/size`)
- Words: "drawing the outline extending outward from the glyph contours by the thickness specified by the `size` property, in pixels".
- **Implemented**: the unit is pixels (a bare number), not points like the font size. The glyph outline path is stroked with a line width of 2 × size, centred on the contours, with round joins; then the glyphs are filled on top. The visible outline therefore reaches `size` px outside the glyph edge. The join style is not specified; I use round.
- **Undefined**: no default outline colour, opacity or size. `labels-spacing` leaves out `opacity`; I use 1. The default colour (white) and size (1) are not needed.
- **Contradiction**: the "Extended Text Class" table puts `outline` on Text, while the UML, the schema and the requirement put it on Font.
- Each label's outline is drawn beneath its own glyphs only. Labels never overlap (F1), so it never covers another label.

---

## G. Other things found

- Colours: the schema gives JSON colours in 0 to 255 (array or `{r,g,b}`), while the Color class says `float` with no range, and the coverage `colorChannels` are 0 to 1. Named colours are matched without regard to case against the clause 17 table, which the renderer reads from the spec file. That table spells `fuschia` (should be `fuchsia`).
- The view's `background` (white) is painted first; the text does not mention a background.
- Coverage selectors are evaluated once per layer, since the selectors in these cases test only the layer. The coverage gets the default zOrder 1 and is drawn in its layer position within that zOrder.
- `capabilities.*` resolves to true for the classes this renderer implements; none of the cases uses them.
