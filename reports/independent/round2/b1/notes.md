# Independent rendering from the requirement text: notes

I wrote the renderer in `renderer/` from the files in `spec/` only, and it renders from `style.cs.json`:

- `cs_expr.py`: CQL2-JSON expressions
- `cs_style.py`: Symbolizer classes, defaults, rule cascading, `alter` and `index`
- `cs_render.py`: drawing, coverages, markers and labels

Run it with:

```
uv run --no-project --with numpy --with pillow --with pycairo python renderer/cs_render.py
```

General-purpose libraries used:

- **pycairo** for anti-aliased 2D drawing and glyph outlines.
- **Pillow** to read the PNG icon, rasterize label footprints and write the PNGs.
- **numpy** for arrays.

The system font Arial (regular, bold, italic) comes through cairo's Windows font backend. The other files in `renderer/` (`data_survey*.py`, `contact_sheet.py`, `debug_lines.py`) only helped me look at the data and the output.

All 36 cases render. One feature is not implemented: SVG images. No case reaches it at its scale (see "Not implemented").

Each choice below gives:

- **Where**: the requirement identifier, or the clause and table.
- **Words**: the exact words that leave the choice open.
- **Readings**: the readings I considered.
- **Chosen**: the reading I implemented.
- **Relied on**: the words of the text I relied on.

The `C-nn` numbers also appear in comments in the code.

---

## Choices

### C-01 Mapping the bbox to pixels
- **Where**: README / `view-1.json`. The spec itself says nothing about the pixel grid.
- **Words**: "`bbox` (EPSG:25833) … `width` and `height` in pixels".
- **Readings**:
  - (a) The bbox is the outer edge of the image, so pixel (0,0) covers [minx, minx+res] × [maxy−res, maxy].
  - (b) The bbox runs through the centres of the corner pixels.
- **Chosen**: (a). One pixel is (maxx−minx)/width metres: 14 m at 1:50 000 and 28 m at 1:100 000. This agrees with `scaleDenominator` × 0.28 mm in every view.
- **Relied on**: "`scaleDenominator`" and "`pixelSize_mm` (0.28 mm, the standard pixel)". Reading (a) is the only one where these agree exactly.

### C-02 Drawing order: `zOrder` across data layers, or the order of the layers first?
- **Where**: `/req/core/z-order`; README "the layers, in drawing order".
- **Words**: "portraying features and coverage cells of a single rendering pass in increasing order of their resolved `zOrder` property". The text doesn't say how `zOrder` combines with the order of the data layers.
- **Readings**:
  - (a) `zOrder` is global: all features and cells with zOrder 1, from every layer, are drawn before any with zOrder 2. Layer order only breaks ties.
  - (b) Each layer is drawn whole in layer order, and `zOrder` sorts only inside a layer.
- **Chosen**: (a).
- **Relied on**: the requirement names "features and coverage cells" without mentioning layers. The caption of the `/req/labels/label` example says "pond names in a marker are covered by the lakes drawn above them". In that style (case 15) the lakes (layer 1, `zOrder: 2`) cover the names of Places (layer 2, default `zOrder` 1), which is only possible under (a). The commented-out painter's algorithm in clause 7 ("For each distinct zOrder: … For each data layer") agrees, but it is commented out.
- **Effect**: case 15 hides parts of the pond names under the lakes. Under (b) the names would be on top.

### C-03 Members without a default value (Font, FontOutline, Hatch, Dotpattern, Stipple)
- **Where**: clause 7 "Default class member values"; the Font class table (clause 8); `/req/vector/font-inheritance`.
- **Words**: the Font table lists only `face`, `size`, `bold`, `italic`. The JSON schema and the UML also have `color`, `opacity`, `underline` and `outline`. The only default is "the default font, whose `size` is 16 px".
- **Readings** for the default font colour:
  - black;
  - the colour of something else.
- **Chosen**:
  - Font colour black, `opacity` 1, `bold` and `italic` false, face Arial.
  - FontOutline `size` 1, `opacity` 1, `color` white.
  - Hatch 1 px / 45° / 10 px, taken from the caption "Default hatch properties (width : 1 px, angle : 45 °, distance : 10 px)".
  - Dot pattern distance 10 × 10 px.
  - Stipple ratio 0.5.
- **Effect on the cases**: none. Every case sets face, size and colour, and every outline sets `size` and `color`.

### C-04 Fills, strokes and markers under one `zOrder`, and Symbolizer opacity "together"
- **Where**:
  - `/req/vector/stroke` part 5 and `/req/vector/marker` part 3, with the NOTE after it;
  - `/req/core/opacity`;
  - `/rec/core/opacity-together`.
- **Words**:
  - "the strokes of all features with the same `zOrder` on top of the fills of all those features";
  - "multiplying it with the opacity of the fill, the stroke, the graphics of markers";
  - "either for each feature or for all features of a data layer with the same `zOrder` drawn at once … Which of these to recommend is still under consideration."
- **Readings**:
  - (a) Multiply each fill, stroke and marker opacity separately. A translucent fill then shows through under its own stroke.
  - (b) Apply it per feature, to the feature drawn as a group.
  - (c) Apply it per group of features with the same `zOrder`, drawn as one group.
- **Conflict**: (b) breaks the requirement that all fills come before all strokes. The "per data layer" grouping of the recommendation breaks the same requirement when two layers share a `zOrder`, because the requirement says "all features with the same zOrder", not "of the same layer".
- **Chosen**: for each `zOrder`, group the features by their resolved opacity. Draw each group into an offscreen buffer in the order fills → casings → main strokes → centre lines → markers (markers in feature order), then composite the buffer once with the group's opacity.
- **Effect**: in case 01 every polygon has `opacity: 0.8`, so the strokes don't show the fills through them. The fill reaches the map at 0.5 × 0.8 = 0.4. Under (a), a 0.75 px stroke over a 0.4 fill would blend differently.

### C-05 An object property set to `null`, or evaluating to NULL
- **Where**: `/req/parameter-values/null` and its table.
- **Words**: the table lists `integer` or `number`, `boolean`, Color, `string`, Enumeration, and "Marker or Label | `null`, emptying its graphical elements". Fill, Stroke, Font and the other objects are missing.
- **Readings** for `fill: null` and `stroke: null`:
  - draw nothing;
  - use the default Fill or Stroke.
- **Chosen**: draw nothing, like Marker and Label. Scalar members that evaluate to NULL take the table's value: 0, false, black, or the empty string.
- **Effect on the cases**: none of them sets `fill` or `stroke` to null. `marker: null` is used and draws nothing.

### C-06 Units
- **Where**: `/req/vector/units`, the CartoSym-CSS units table, `/req/vector/fonts`.
- **Words**:
  - "One point is equal to 1/72 inch (0.3528 mm)". The two values differ at the 5th digit.
  - "(none) | For relative values like scaling, 100 times less than if _pc_ is specified. For screen-space objects, defaults to pixels."
- **Chosen**:
  - px = 1. mm = 1/0.28. cm = 10/0.28. inch = 25.4/0.28.
  - pt = (25.4/72)/0.28 = 1.2599 px.
  - m = 1 / (ground metres per pixel). ft = 0.3048 m.
  - A number without a unit is in pixels, except in a `hotSpot`, where it is in pixels of the image file (C-14).
- **Resulting sizes**: 8 pt = 10.08 px, 9 pt = 11.34 px, 10 pt = 12.60 px, 12 pt = 15.12 px, 14 pt = 17.64 px, 10 mm = 35.71 px.
- **Cases 17 and 18**: `size: 8` has no unit, so it is 8 px, while cases 22 to 24 use `8 pt` = 10.08 px.
- **Relied on**: "a uom-qualified `size` (in pixels when no unit is given, as for any uom-qualified property)" (`/req/vector/fonts`).

### C-07 Comparing a date property, stored as a string, with a Date System Identifier
- **Where**: `/req/core/time`, `/req/core/relational`, "Data Types". The README says "dates are ISO dates".
- **Words**: `validDate >= viz.timeInterval.start.date`, where `validDate` is the JSON string `"2016-12-02"`.
- **Readings**:
  - (a) The type mismatch makes the comparison NULL, so the selector doesn't select anything. Cases 01, 02 and 03 would then be empty white maps.
  - (b) A string in ISO date form, compared with a Date, is read as that Date.
- **Chosen**: (b). Timestamp strings compared with a DateTime are read the same way.
- **Relied on**: the README's "dates are ISO dates", and "A Renderer SHALL support resolving the visualization time System Identifiers to the time instant or interval of the map being rendered". The text never says how a data property becomes a Date.

### C-08 Names and paths of System Identifiers
- **Where**: clause 7 tables, the JSON schema's `systemIdentifier` enum.
- **Words**:
  - clause 7 has `dataLayer.identifier` and `visualization.scaleDenominator`;
  - the schema and all the case styles use `dataLayer.id` and `viz.sd`;
  - the schema also has `viz.timeInterval.start.date`, which clause 7 doesn't list. Clause 7 only gives the UML `TimeInterval.start: TimeInstant` and `TimeInstant.date`.
- **Chosen**:
  - `viz` is an alias of `visualization`, `sd` of `scaleDenominator`, and `id` of `identifier`;
  - member paths follow the UML;
  - `viz.timeInterval.start.date` is the start date of the view's interval (1980-01-01). The view gives only dates, so the time is taken as 00:00.

### C-09 Enumeration values in JSON
- **Where**: "Enumeration values" (clause 16), `/req/right-hand/operands` NOTE.
- **Words**: `[dataLayer.type = vector]` in CSS. In JSON this is `"vector"`, a string literal.
- **Chosen**: enumeration values are compared as their names, as strings. This gives the same result for `vector` and `'vector'` (case 03 uses the quoted form).
- **Relied on**: "the same identifier enclosed within single quotes is considered equivalent".

### C-10 Sampling coverage cells to pixels
- **Where**:
  - `/req/coverage/single-channel` parts 3 and 4;
  - `/per/coverage/interpolation`;
  - the NOTE "Where nothing indicates whether a variable is continuous, this Standard does not require a behavior".
- **Words**: "portraying each coverage cell over the area of that cell"; "MAY interpolate between the values of neighbouring cells of a continuous variable".
- **Readings**:
  - nearest cell (each cell over its area);
  - bilinear interpolation of the elevation, or of the colours.
- **Chosen**: each pixel takes the cell that contains its centre (nearest). The grid (28 m cells, origin 225 496 / 6 872 568) is offset from the map pixels by 64 m and 57 m, so the centre of each pixel falls inside exactly one cell. An interpolating renderer would differ by up to a fraction of a cell everywhere.

### C-11 Hill shading
- **Where**: `/req/hill-shading/hill-shading`, `/factor`, `/sun`, and the NOTE about differences.
- **Words**:
  - "computing the terrain surface normal of each cell from the differences in elevation between neighbouring samples";
  - "multiplying the red, green and blue components of each cell by its shade value";
  - "an elevation coverage".
- **Readings and choices**:
  - **Which values are the elevations?** Choice: the cell's `singleChannel` value. Here that is the only band, `elevation`.
  - **Differences**: as the NOTE suggests, central differences over 2 × 28 m, repeating the edge sample at the edges.
  - **Normal**: (−f·∂z/∂x, −f·∂z/∂y, 1), normalized, with x east and y north (grid north). The sun vector is (sin az·cos el, cos az·cos el, sin el), so azimuth 315 lights from the north-west.
  - **Order**: shade = clamp(n·s, 0, 1), multiplied with the RGB that the `colorMap` already gave.
- **Consequence**: flat terrain gets shade sin 45° = 0.707. The text doesn't normalize the shade, so the whole coverage gets darker even where the ground is flat. A renderer that divides by the shade of flat ground, or applies the shade as an overlay, would give much lighter maps in cases 04 to 14.

### C-12 Numbers where text is expected: `concatenate('Road ', number)` and `text: number`
- **Where**: `/req/functions/call-expressions` part 5, `/per/functions/type-casts`, `/req/core/parameters`, the Text table.
- **Words**:
  - "A Renderer SHALL evaluate a FunctionCallExpression whose arguments do not match the parameters of the Function, in number or type, after these conversions, to NULL". The only conversions listed are integer→number and string→enumeration.
  - "A Renderer MAY convert arguments of other types … How such arguments are converted is not specified."
- **Readings**:
  - (a) Strictly, `number` is an integer and `concatenate` takes strings, so the result is NULL. NULL text is the empty string, so cases 17 and 18 would show no road names; case 18 would show only the Dots.
  - (b) Use the permission and convert the integer to decimal text.
- **Chosen**: (b). Integers become e.g. "2614" and "6", other numbers their shortest decimal form, booleans "true"/"false". The same conversion applies when a Text's `text` resolves to a number (cases 22 to 24), under "resolving Parameter Values to the data type expected by the Symbolizer property".
- **Note**: this is the clearest case where two conforming renderers can draw different maps. One of them uses a MAY and the other doesn't.

### C-13 Interpolating a `colorMap`
- **Where**: `/req/coverage/color-map`, `/rec/coverage/map-interpolation`, `/per/coverage/linear-light`.
- **Chosen**: piecewise linear interpolation in sRGB. Outside the range of the map, the first or last entry applies. The interpolation method and the colour space are both left open.

### C-14 Image graphics (cases 29 to 32)
- **Where**: `/req/vector/image`, `/per/vector/image-linear-light`, `/per/vector/image-alpha-test`.
- **Chosen**:
  - **Size**: without `size`, one image pixel per map pixel: hut.png is 24 × 24 px. `size: 10 mm` sets both sides to 35.71 px.
  - **Resampling**: bilinear (cairo `FILTER_BILINEAR`). The text gives no resampling method; another filter changes the edge pixels.
  - **Hotspot**: `50 pc 100 pc` is the bottom centre of the image as drawn, and `0 0` is its top-left corner. A number without a unit is in pixels of the image file, scaled with the image.
  - **Recolouring**: in sRGB (I didn't use the linear-light permission), on unpremultiplied colours, keeping the alpha. hut.png is black, so the drawn colour is `blackTint`.
  - **alphaThreshold**: no alpha test (default 0).
- **Relied on**: the hotspot words are "a number without a unit is in pixels of the image file (scaled with the image when it is drawn at another size), a value in `pc` is a percentage of the image's width or height".

### C-15 Font outlines (cases 04 to 14, 17, 18, 22 to 24)
- **Where**: `/req/font-outlines/outline`, `/size`, `/opacity`.
- **Words**:
  - "drawing the outline extending outward from the glyph contours by the thickness specified by the `size` property, in pixels";
  - "drawing the outline with the opacity specified by the `opacity` property".
- **Open points**:
  - The join shape at glyph corners: round or mitred.
  - Whether a translucent outline is drawn as one shape, or overlapping parts (glyph to glyph) add up.
  - Whether the outline also covers the inside of the glyph, which can show at anti-aliased edges.
  - Whether `font.opacity` also applies to the outline.
- **Chosen**: the outline is the glyph shape dilated by `size` px with round joins (glyph path filled, and stroked with width 2 × size). It is drawn once per label as a group with opacity `outline.opacity`, beneath the glyphs. Glyphs are filled with `font.color` × `font.opacity`, and the outline ignores `font.opacity`.
- **Resulting widths**: 1 px (case 12), 2 px (most cases) and 3.5 px (case 14) outward from the contours.

### C-16 A new casing or centre line that doesn't give a width
- **Where**: the "Stroke class default values" table.
- **Words**: "casing | `width` 0 (no casing), `color` black".
- **Chosen**: a new StrokeStyling for `casing` or `center` that doesn't set `width` has width 0. No case uses casings.

### C-17 Setting an object property without `"alter": true`
- **Where**: `/req/core/instances`, `/req/json/partial-update`.
- **Words**:
  - "A Symbolizer may either set an object property with a complete new instance, or specifically override a particular member";
  - "using default values for members which are not specified".
- **Chosen**:
  - An object without `alter` is a new instance: the members it doesn't set take the class defaults, not the inherited values. For example, `stroke: {color, width}` in case 02 resets `opacity` to 1.
  - The exception is Font: an unset font member stays unset, so that font inheritance applies. "Taking each property of the font … from the nearest place that sets it" would mean nothing if every Font instance had its own defaults.

### C-18 Updating an array element at an index past the end
- **Where**: `/req/json/array-element-update`.
- **Words**: "updating only the array element identified by `index`, preserving the other elements".
- **Problem**: case 03 sets `marker.elements` index 2 on a 2-element array, and case 01 sets index 1 on a 1-element array. Neither element exists yet.
- **Chosen**: an index equal to the length appends. Larger indices also append; nothing is padded. This doesn't affect the images: at 1:50 000 neither nested rule (`viz.sd < 10000` and `viz.sd < 5000`) is selected.

### C-19 Aligning text: which ascent, and which width
- **Where**: `/req/vector/text` part 3.
- **Words**: "`left` puts the start of the text there, `right` its end, `top` the top of the font's ascent, `bottom` the bottom of its descent, and `middle` the point halfway between them".
- **Readings**:
  - Ascent and descent: the font's typographic metrics (OS/2 `sTypoAscender` / `sTypoDescender`, about 0.73 em / 0.21 em for Arial), or the hhea/Windows metrics (0.905 em / 0.212 em for Arial). The text also doesn't say whether these are the font's metrics or the ink of the actual string.
  - Start and end: the advance width, or the ink bounds.
- **Chosen**: the ascent and descent that cairo's Windows backend reports: 0.905 em and 0.212 em for Arial, unhinted. The box runs from the pen origin to the advance width.
- **Effect**:
  - `top` (case 33): for 9 pt text (11.34 px), the baseline is 10.26 px below the point. With the typographic ascender it would be about 8.3 px.
  - `middle` (cases 04 to 24, 34): depends on both metrics.
  - `bottom` (cases 25 to 28, 35, 36): depends on the descent only.
  - With ink bounds instead of font metrics, the vertical position would change per word, by up to about 3 px.

### C-20 Dots
- **Where**: `/req/vector/dot`, `/per/vector/dot-outline`.
- **Chosen**: a filled anti-aliased circle of diameter `size`, centred exactly on the point, with no hairline outline (the permission is not used). No case draws the default white Dot.

### C-21 What counts as overlap between labels
- **Where**: `/rec/labels/overlap`.
- **Words**: "omit labels which cannot be placed without overlapping other labels". What a label's extent is isn't defined: ink, the text box, or the box including the outline.
- **Chosen**:
  - A Text's footprint is its box: advance width × (ascent + descent), grown by the outline size on every side.
  - A Dot's footprint is its bounding square, and an Image's is its drawn rectangle.
  - Along lines, each glyph's box is rotated with the glyph.
  - Footprints are rasterized to whole pixels and must not share a pixel with an earlier label.
  - Labels don't avoid markers or features. The text only asks for labels to avoid other labels.

### C-22 Sign of `y` in a label's `position`
- **Where**: `/req/vector/graphics` part 3, `/req/labels/line` part 4.
- **Words**:
  - "a positive `y` as an offset downwards on the map";
  - for labels along lines, "its `y` perpendicular to the line, positive towards the top of the label".
- **Chosen**: for markers and labels on points, positive y is down, so `0 -8` in cases 19 to 21 is 8 px up. For labels along lines, positive y is towards the top of the label. The two conventions are opposite, which is easy to get wrong.

### C-23 Default label `priority` and ties
- **Where**: `/req/labels/placement`, the NOTE after `/rec/labels/overlap`.
- **Words**:
  - "a label with a higher `priority` is placed in preference to a conflicting label with a lower `priority`";
  - "Which of two conflicting labels of the same `priority` is left out may differ between Renderers";
  - the TODO "confirm that a higher `priority` value means a higher priority (see #148)".
- **Chosen**:
  - The default priority is 0.
  - A NULL priority is 0, per the NULL table for numbers. In case 20 the mountains without `elevation` therefore get 0. In case 21, `0 - elevation` is NULL for them, so they get 0, which is the highest priority there.
  - Higher values are placed first.
  - Ties go in data order: layer order, then feature order in the file.
- **Effect**: case 19 has no priority at all, so which peak names survive is decided only by file order. Another renderer may legitimately keep others.

### C-24 Point labels at the edges of the map
- **Where**: the NOTE "Whether labels that would extend beyond the edges of the map are placed is left to the Renderer".
- **Chosen**: a point label is considered only if its point lies inside the map. It is placed even when the text extends past the edge, and the text is then cut off: Vassberget, Sagtindan and Nørdre Geitsida in cases 19 to 21.

### C-25 Line labels at the edges of the map
- **Chosen**: a label along a line is placed only where its whole footprint lies inside the map. Along a line there are other positions to choose, so cut-off text is avoided.

### C-26 Repeating labels along lines (`minSpacing`)
- **Where**: `/req/labels/placement` parts 3 and 4.
- **Words**:
  - "repeating a label so that the distance between repetitions of that label is at least `minSpacing` and, where space allows, at most `maxSpacing`";
  - "measuring the distance between repetitions on the map between their positions".
- **Open points**:
  - Without `maxSpacing`, nothing requires more than one label.
  - Where the first label goes is not said.
  - The "position" of a label along a line is not defined.
- **Readings**:
  - (a) Start from the middle of the line and add repetitions outward.
  - (b) Pack repetitions greedily from one end.
  - (c) Place one label only.
- **Chosen**:
  - The label's position is its anchor on the line: the point where x = 0 of its elements lies.
  - Candidate anchors are tried every 2 px from the start of the line, in the direction the label reads.
  - A candidate is accepted when its footprint is free and its straight-line distance to every earlier repetition with the same content in the same layer is at least `minSpacing`.
  - All candidates of one road come before those of lower priority. Both roads in the cases have priority 0, so data order decides.
- **Result**: road 2614 is labelled 4 times in case 22 (80 px), 2 times in case 23 (150 px) and once in case 24 (300 px). Reading (a) gives 3, 1 and 1. I chose (b) so that the three panels differ, as the example's caption ("Road numbers repeated along the roads") suggests. It is a guess at intent.

### C-27 A label on a line without `minSpacing`
- **Chosen**: one label per joined line. Read literally, a minimum spacing of 0 would allow unlimited repetitions. No case has this.

### C-28 Labels following lines: tangents, bends, reading direction
- **Where**: `/req/labels/line` parts 1 and 2, `/rec/labels/line`, and the NOTE "How sharp a bend a label along a line may follow is left to the Renderer".
- **Chosen**:
  - Each glyph is centred at its advance position along the line, rotated to the direction of the chord over the glyph's own advance.
  - A candidate is rejected if two neighbouring glyphs turn more than 40°.
  - The label reads left to right: the chord from the label's start to its end must have dx ≥ 0, and otherwise the other direction of the line is used.
  - The label is omitted where the line is shorter than the label.
  - Text with `middle` alignment is centred on the line, half way between ascent and descent.
  - The Dot of case 18 sits on the line at the anchor, and the text starts 7 px further along.

### C-29 Joining lines, and "the same content"
- **Where**: `/req/labels/line` part 3, `/req/labels/placement` part 4.
- **Words**: "joining … the line geometries of a data layer that have the same label and meet at their end points"; "all labels with the same content".
- **Chosen**:
  - "Same label/content" means the same sequence of element kinds and the same resolved texts.
  - Lines are joined where their end points are equal to 1e-6 m, greedily in data order. At a junction where three or more lines meet, which pair is joined is undefined, so I take the first match.
  - Road 2614 (three features in the data) is joined into one 732 px line, of which about 290 px can hold a label inside the map.

### C-30 Opacity of labels
- **Where**: the NOTE after `/req/core/opacity`: "The Symbolizer `opacity` does not apply to labels."
- **Chosen**: labels ignore the Symbolizer opacity. Text in markers multiplies it in.
- **Gap**: `font.opacity` is used in the cases (`opacity: 1.0`) but is missing from the Font table. I multiply it with the glyph colour.

### C-31 Polygon fill rule, and strokes on holes
- **Where**: clause 8 "Strokes": "drawing an outline (e.g., for linear geometries or the exterior of a polygon geometry)".
- **Chosen**: polygons are filled with the even-odd rule, which doesn't depend on ring orientation. Strokes are drawn on every ring, holes included. The text names only the exterior, and only as an example ("e.g.").

### C-32 Anti-aliasing and glyph rasterization
- **Where**: nowhere. The text says nothing about how geometry is rasterized.
- **Chosen**: cairo's grey-level anti-aliasing for everything. Glyphs come from unhinted Arial outlines placed at sub-pixel positions. A renderer with aliased drawing, hinted text or another text engine differs at every edge.

### C-33 A coverage and vector features with the same `zOrder`
- **Chosen**: coverage cells of a `zOrder` are drawn before the vector features of the same `zOrder`. The text gives no order between them. In the cases the coverage is the only layer that draws anything below the labels.

### C-34 Rendering passes
- **Where**: clause 7 "Visualization Rendering Passes", the `feature.pass` table.
- **Chosen**: a single pass. `viz.pass` and `feature.pass` resolve to 0, because their numbering (starting value, order) isn't defined. No case uses them.

### C-35 Marker positions on lines and polygons
- **Where**: `/req/vector/marker`; the NOTE "at the centroid of each polygon".
- **Chosen**: lines get a marker at every vertex. Polygons get one at the area-weighted centroid of the exterior minus its holes. "Centroid" is not defined further: whether holes count, and what happens when the centroid falls outside the polygon. Every case sets `marker: null` for lines and polygons, so this doesn't show.

---

## Contradictions, and things used but not defined

1. **Property names of TextAlignment** differ in three places:
   - `horzAlignment` / `vertAlignment` in the TextAlignment table and `/req/vector/text`;
   - `horizontal` / `vertical` in the UML and the CSS example `TextAlignment(horizontal: left; vertical: top)`;
   - `hAlignment` / `vAlignment` in the JSON schema.

   I accept all three.
2. **System Identifier names** in clause 7 (`dataLayer.identifier`, `visualization.scaleDenominator`) are not those in the JSON schema and the styles (`dataLayer.id`, `viz.sd`). The schema has `capabilities.dotpatterns`, which the capabilities table of clause 7 lacks.
3. **Font class table** omits `color`, `opacity`, `underline` and `outline`, which the UML and schema have. The cases set `font.color` and `font.opacity`. The text gives no default font colour or face.
4. **MultiGraphic `elements`** has multiplicity `1..*`, but the NOTE in clause 7 allows `marker: { elements: [] }`.
5. **ValueColor** is called `label: text` in the UML and `name` in the table.
6. **Unitless numbers** are pixels for screen objects, but "100 times less than if pc is specified" for relative values. The `hotSpot` treats a unitless number as pixels of the image file, a third meaning.
7. **`minSpacing` / `maxSpacing`** are "in pixels unless qualified with another unit", but the JSON schema types them as plain `numericExpression`, so JSON can't give them a unit. Clause 16 has the same problem with FontOutline `size` (plain number, "in pixels").
8. **Clause numbering**: clause 6 says the JSON encoding is Section 16 and CSS Section 17. The files and the README have CSS as 16 and JSON as 17.
9. **Units of a point**: "1/72 inch (0.3528 mm)". The exact value is 0.35278 mm.
10. **Colour component ranges**: the schema gives colour components as integers 0 to 255, while the Color class says only "number" in sRGB, and `colorChannels` uses 0 to 1. The text never says that 0 to 255 is the scale of Color.
11. **Default `colorChannels`**: the default uses `fields[0..2]` unscaled, while `colorChannels` must be 0 to 1. The text flags this itself as `TODO(review)`. It isn't used here.
12. **Metadata `abstract`**: the case styles set `abstract` / `.abstract`, which is neither in the Metadata table nor in the schema. It is ignored.
13. **`/req/core/z-order`** speaks of "a single rendering pass", but neither the numbering of passes nor how `zOrder` combines with layer order is defined (C-02, C-34).
14. **Coverage selectors**: `/req/core/selector` applies "to a feature or coverage cell", so selectors may depend on cell values. I evaluate coverage selectors once per layer and stop with an error if one depends on cell values. That is not implemented, and no case needs it.

## Not implemented

- **SVG images.** Case 01 refers to `icons/*.svg`, but only in rules for `viz.sd < 10000`, and case 01 renders at 1:50 000. No SVG is needed for any of the 36 images.
- **Selectors that depend on coverage cell values** (see item 14 above). Not needed.
- **Fill `pattern` and Stroke `pattern`** (in the schema but not in Part 1's text) and vendor extensions.
- **Overriding variables at run time** (`/req/variables/definition` part 2): `$variables` are resolved, but there is no user interface. `capabilities.variables` reports false.

Everything else that the 36 cases use is implemented.

## The cases

The table gives sizes in map pixels (0.28 mm). Text sizes are the font size (em). "Outline" is how far the font outline extends outward from the glyph contours.

| Case | What my renderer draws |
|---|---|
| 01 | 58 land cover polygons at 1:50 000 (all `validDate` 2016 fall in the interval). Fills #d6cfbd, or bog #cbb867, forest #4f8a45, lake #6fa3cc, at fill opacity 0.5. Strokes 0.75 px in the matching darker colour. Each `zOrder` group is composited at Symbolizer opacity 0.8. No markers or text (the `< 10000` rules are not selected). |
| 02 | 466 roads at 1:100 000 (paths excluded), round caps and joins. Grey #8c8172 1 px (private, tractor, cycleway; zOrder 2). Municipal #f2b84b 2.5 px (z 3), county #f2b84b 3.5 px (z 4), national #e8833a 4.5 px (z 5), European #d0483a 5.5 px (z 6). Higher zOrders are drawn on top. No markers. |
| 03 | 3 huts at 1:50 000: Dot 7 px #b8322a at Symbolizer opacity 0.9. No text (the `< 5000` rule is not selected). |
| 04 | Elevation coverage, 28 m cells sampled nearest at 28 m pixels. `colorMap` 300/1200/2200 m, multiplied by the hill shade (factor 2, sun 315°/45°; flat ground 0.707). Labels on the 3 peaks ≥ 2000 m (Rondslottet, Vinjeronden, Storronden): Arial 10 pt = 12.60 px, #2b2b2b, centre middle. White outline 2 px. |
| 05 | As 04, outline 2 px #f3e7b8. |
| 06 | As 04, outline 2 px #e8a090. |
| 07 | As 04, white outline 2 px at opacity 0.3. |
| 08 | As 04, white outline 2 px at opacity 0.6. |
| 09 | As 04, white outline 2 px at opacity 1. |
| 10 | As 04, no outline. |
| 11 | Same as 04 (identical input; pixel-identical output). |
| 12 | As 04, white outline 1 px. |
| 13 | Same as 04 (identical input; pixel-identical output). |
| 14 | As 04, white outline 3.5 px. |
| 15 | Lakes: fill #a9cbe3, no stroke, zOrder 2. Pond names as marker Text: Arial italic 9 pt = 11.34 px, #1f4e79, centre middle, zOrder 1. The lakes (zOrder 2) are drawn over the names (C-02). |
| 16 | As 15, but the names are labels, drawn on top of everything. No two labels overlap, so all 8 names appear. |
| 17 | Roads E6 and 2614 (county road joined from 3 features): stroke #d0483a 2 px. Labels along the lines "Road 6" and "Road 2614", Arial bold 8 px (no unit), #b8322a, white outline 2 px, starting 7 px along the line, centred vertically on it. `minSpacing` 150: 2 × "Road 2614" and 1 × "Road 6". |
| 18 | As 17, plus a Dot of 7 px #b8322a on the line at each label's anchor. 2 × "Road 2614" and 1 × "Road 6". |
| 19 | 36 mountains (5 without `elevation`) at 1:250 000: Dot 3 px #b8322a. Labels Arial 9 pt = 11.34 px #2b2b2b, centre middle, 8 px above the point. No priority, so overlaps are resolved in file order (C-23). Names at the edge are cut off (C-24). |
| 20 | As 19, priority = elevation (higher first; no elevation → 0). |
| 21 | As 19, priority = 0 − elevation (lower first; no elevation → 0, so those come first). |
| 22 | Roads as 17. Labels along the lines: the number only, Arial bold 8 pt = 10.08 px, #b8322a, white outline 2 px, centred on the anchor. `minSpacing` 80: "2614" 4 ×, "6" 2 ×. |
| 23 | As 22, `minSpacing` 150: "2614" 2 ×, "6" 2 ×. |
| 24 | As 22, `minSpacing` 300: "2614" 1 ×, "6" 1 ×. |
| 25 | 5 mountains at 1:38 000: Dot 4 px #b8322a. Marker Text Arial 9 pt = 11.34 px #2b2b2b, centre bottom, 4 px above the point. |
| 26 | As 25 with Arial 12 pt = 15.12 px. |
| 27 | As 25 with Arial bold 9 pt. |
| 28 | As 25 with Arial italic 9 pt. |
| 29 | 2 huts at 1:10 000: hut.png at its own size 24 × 24 px, black recoloured to #b8322a, bottom centre on the point. A Dot of 5 px #1f4e79 on top of it at the point. |
| 30 | As 29 with the image at 10 mm = 35.71 × 35.71 px (bilinear). |
| 31 | As 30 with hotSpot `0 0`: the top-left corner of the image on the point. |
| 32 | As 30 with blackTint #3a7d44. |
| 33 | 5 mountains at 1:52 000: Dot 4 px #b8322a. Text Arial 9 pt = 11.34 px with the default alignment left top: the text starts at the point, and its ascent top (10.26 px above the baseline) is at the point. |
| 34 | As 33, alignment centre middle. |
| 35 | As 33, alignment right bottom. |
| 36 | As 33, alignment centre bottom. |

## Files read outside this folder

At run time the renderer uses the system font Arial through cairo's Windows font backend (allowed by the README), and Python packages from the uv cache (numpy, Pillow, pycairo). Nothing about Cartographic Symbology, SLD/SE or CQL2 was read or imported.

There is one technicality. One of my commands printed `spec/1-core/examples/requirements/*.adoc` and `*.cscss` from this folder. Its output was too long for the terminal, so the Claude Code harness saved it to a temporary `tool-results/….txt` file in its own session folder, and I read that file. Its content is only a copy of files in this folder.

- the harness's temporary copy of my own command output, described above (content from this folder only)

Apart from that copy: none.
