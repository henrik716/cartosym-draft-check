# Notes: places where the text leaves a choice open

Renderer: `renderer/render.py` (drawing) and `renderer/cartosym.py` (colours, units, expressions, rule cascading). Run with `uv run --no-project --with numpy --with pillow --with pycairo --with shapely python renderer/render.py`. Drawing uses pycairo (anti-aliased paths and text), shapely (geometry parsing, clipping, centroids), numpy and Pillow. All 20 cases render: 21 images, since `vector-units` has two views.

Each entry gives the requirement (or clause/table), the words that leave the choice open, the readings I considered, and **what I implemented**.

## A. Core: rules, defaults, ordering

1. **Features that no rule selects.** `/req/core/symbolizer`: "portraying data using the Symbolizer properties resulting from all selected StylingRules, using the default values for properties not set by any selected rule". The text does not say whether a feature that *no* rule selects is drawn at all. Readings: (a) draw it with the default symbolizer only (white fill, 1 px black stroke, the default white 10 px Dot); (b) do not draw it. **Implemented (a)**, because the NOTE under `/req/core/default-values` says "every feature is visible by default". Visible effect: in `core-opacity` the rule is `Landcover[class = 'lake']`, so all non-lake polygons are drawn with a white fill and a black 1 px outline.
2. **Default Marker is invisible.** Clause 7 default tables: Marker = "Single default Dot", Dot size "10 px", color "white". The NOTE says the default marker exists "so that every feature is visible by default", but a white dot with no outline on a white background (or a default white fill) is not visible. This contradicts the stated purpose. **Implemented as written** (white 10 px dot, no outline).
3. **Partial update of a property that no earlier rule set.** `/req/json/partial-update`: "preserving the values ... as set by earlier rules or by default values". **Implemented:** `alter: true` on an unset property starts from the class default (Stroke: black, 1 px, opacity 1; Fill: white, opacity 1).
4. **Selectors that evaluate to NULL** (for example a comparison with a missing property) do not select the rule, per the NOTE under `/req/core/selector`. Logical operators use the CQL2 three-valued logic.
5. **zOrder scope and ties.** `/req/core/z-order`: "portraying features and coverage cells of a single rendering pass in increasing order of their resolved `zOrder`". Not stated: (a) whether the sort is global across all layers or applies within each layer; (b) the order among equal `zOrder` values. **Implemented:** a global stable sort over all layers. Equal `zOrder` keeps the layer order of `view.layers`, then data order. The type is also inconsistent: `int` in the Symbolizer table, `float` in the "Visual Ordering Constructs" table.
6. **Opacity together.** `/rec/core/opacity-together`. **Implemented:** each feature's fill, stroke and marker are drawn into an offscreen group, which is then composited with the Symbolizer `opacity`. Casings and centre lines are drawn in their own passes (see F), each with the same Symbolizer opacity applied separately.
7. **Time comparisons with a text property.** `/req/core/time` and `/req/core/expressions-field-identifiers`: `validDate` is a text property (ISO date), and `viz.timeInterval.start.date` is a Date. The text does not define comparing text with a Date (CQL2 would need `DATE()`). Readings: (a) compare as text; (b) coerce the text to a date; (c) NULL or false. **Implemented (b)**, which gives the same order as (a) for ISO dates. The time zone and time of day of the visualization are not given; I used dates only.
8. **System identifier names.** The text uses `dataLayer.identifier` and `visualization.*`. The schema and the cases use `dataLayer.id`, `viz.*` and `viz.sd`. The text names `feature.geometryDimension`, the UML `feature.geometryDimensions`. **Implemented:** all of these are accepted as aliases.
9. **Capabilities.** I resolve `capabilities.<x>` to true for the classes I implemented. No case uses them.

## B. Basic vector styling

10. **Units of measure.** `/req/vector/units` and clause 8 "Graphical Units of Measure".
    - A bare number means pixels ("The portrayal unit 'pixel' is the default unit of measure").
    - mm, cm, in and pt use the 0.28 mm pixel, so 1 pt = (25.4/72)/0.28 = 1.26 px.
    - **m and ft:** ground distance at the map scale, so px = metres × 1000 / (scaleDenominator × 0.28). It could also be derived from bbox/width. The two agree for every view here.
    - `pc` for widths is not defined; I ignore it there.
    - The unit lists disagree with each other: "pixel, millimeter, inch, percentage, meter, foot" (requirement), the GraphicalUnit enumeration (adds points, em, screenCM), and `/req/dashes/dash-pattern` ("pixels, points, millimeters, centimeters and inches").
11. **Stroke details.** Clause 8 gives butt caps and miter joins. The **miter limit is not given**; I used cairo's default of 10.
    - "outline (e.g., ... the exterior of a polygon geometry)" leaves open whether holes are stroked. **Implemented:** all rings are stroked.
    - Polygons with holes are filled even-odd, so holes stay empty.
    - Points get no fill or stroke, only the marker.
12. **Marker positions.** `/req/vector/marker`: "at the points of vector geometry (for points and line strings) and at the centroid of polygons". **Implemented:** every vertex of a line, including both ends.
    - A MultiPolygon gets one centroid for the whole geometry, not one per part.
    - The centroid can fall outside the polygon.
13. **Direction of +y in a Graphic `position`.** `/req/vector/graphics`, UnitPoint table: "y | Vertical position", with no direction. Readings: (a) +y down (screen and CSS convention); (b) +y up (map convention). **Implemented (b): +y points up on the map.** The text gives no tie-breaker. I used the case designs as one: `position: 0 -6` with `alignment: center top` for an elevation number, and a label at `0 8` over a dot, both only make sense with +y up.
    - The Image `hotSpot` uses the image convention: `100 pc` in y is the bottom edge, which the `vector-image` comment says too. The model therefore ends up with two y conventions, one for `position` and one for `hotSpot`.
14. **Order of drawing within a feature and of marker elements.** Not specified. **Implemented:** fill, then stroke, then marker, feature by feature. Marker elements are drawn in list order.
15. **Dot size that is zero or negative.** In `core-parameters`, `size: (elevation - 900) / 100` gives -0.22 for elevation 878. Not specified. **Implemented:** no dot is drawn. The unitless result is in pixels.
16. **Image.**
    - The drawn size is not defined (there is no size property). **Implemented:** native pixel size, 1 image pixel = 1 output pixel, with the top-left corner snapped to whole pixels.
    - A unitless `hotSpot` is read as a fraction of the image size. This matches the default `{0.5, 0.5}` and the CSS "(none) ... 100 times less than pc".
    - Tinting is applied to the un-premultiplied RGB; alpha is unchanged.
    - The Resource member is `url` in the text but `uri` in the schema and the case. I load `path`, relative to the style file.
    - `alphaThreshold` is not used (the permission was not taken).
17. **Text alignment.** `/req/vector/text`.
    - **No default alignment** is given. **Implemented:** center middle.
    - Meaning: the named side of the text is at the anchor. `left` means the text starts at the anchor; `top` means the text hangs below it.
    - "top", "middle" and "bottom" are not tied to font metrics. Readings: ascent/descent lines, ink bounding box, cap height, baseline. **Implemented:** top = ascent line, bottom = descent line, middle = halfway between them. Horizontal extent = advance width.
    - Member names disagree: `horzAlignment`/`vertAlignment` (text), `horizontal`/`vertical` (UML and CSS), `hAlignment`/`vAlignment` (schema). All are accepted, as well as the `[h, v]` array the cases use.
18. **Fonts.** `/req/vector/fonts`: size is "specified in points", converted to pixels with the 0.28 mm pixel (9 pt = 11.34 px).
    - No defaults are given for face, size or colour. **Implemented:** Arial, 10 pt, black.
    - Font `color` and `opacity` are in the UML and the schema but not in the Font table.
    - **Numbers shown as text** (`text: elevation`): the formatting is not defined. **Implemented:** integral values without decimals.
19. **Text graphics inside a Marker** are drawn in the feature pass, with no collision handling. Overlap avoidance is defined only for labels.

## C. Labels

20. **Label anchor.** `/req/labels/label` defines when labels are drawn, not where. **Implemented:** point features at the point, polygons at the centroid (as for markers), lines at positions along the line (item 24). The text is always horizontal; no orientation along the line is defined.
21. **Collision geometry.** `/rec/labels/overlap`: "omit labels which cannot be placed without overlapping other labels". The shape used for the test is not defined. **Implemented:** the metric box of each Text element (advance width × ascent+descent), grown by the outline size, plus the boxes of any Dot or Image elements. No extra padding. Only label-to-label overlap is tested, not label-to-marker.
22. **Priority.** `/req/labels/placement`: "a label with a higher `priority` is placed in preference". The text itself has a TODO asking to confirm that a higher value means higher priority (#148). **Implemented:** higher value first. The default priority is not given; I used 0. A NULL priority (peaks without an elevation) becomes 0 per the NULL table. Ties keep data order (greedy placement).
23. **Labels partly outside the map.** Not addressed. Readings: (a) keep them, clipped at the map edge; (b) drop any label not entirely inside; (c) shift them inside. **Implemented (a).** Candidates entirely outside are dropped. Visible in `labels-priority`, where names are cut at the edges.
24. **Label repetition along lines.** `/req/labels/placement`: "the distance between repetitions of that label is at least `minSpacing` and, where space allows, at most `maxSpacing`". Not defined:
    - where the first label goes;
    - whether distance is measured along the line or straight;
    - what "that label" is when a road is split into many features with the same number;
    - what happens with no spacing at all.

    **Implemented:**
    - Each feature is clipped to the view. On each visible part of length L, n = floor(L/s)+1 positions are spaced s = `minSpacing` apart and centred on the part (`maxSpacing` is used only if `minSpacing` is absent).
    - A candidate is rejected if an already placed label with the same text in the same layer lies closer than s in a straight line. Features with the same road number are therefore treated as one label.
    - With no spacing at all: one label at the middle of the longest visible part.
25. Symbolizer `opacity` is not applied to labels (NOTE under `/req/core/opacity`). A feature with `visibility: false` gets no label.

## D. Font outlines

26. **Outline size unit and meaning.** `/req/font-outlines/size`: "extending outward from the glyph contours by the thickness specified by the `size` property". `size` is a plain float with no unit and no default.
    - Unit readings: pixels, points (as for the font size), or a fraction of the font size. **Implemented:** pixels.
    - Meaning readings: distance outward from the contour, or total stroke width. **Implemented:** distance outward. The glyph path is stroked with width 2 × size, round joins, in the outline colour and opacity, and the glyphs are then filled on top ("beneath the glyphs themselves").
    - No defaults are given for size, opacity or colour; I used 1 px, opacity 1 and white. `labels-spacing` sets no outline opacity, so it gets 1.
    - The clause 10 table calls this the "Extended Text Class", while the UML puts `outline` on Font, as the cases do.

## E. Dashes

27. **Meaning of `dashOffset`.** `/req/dashes/dash-offset`: "dashing vector geometry based on a dashOffset property". The only description is the figure caption: "a dash pattern preceded by an offset". Readings:
    - (a) SVG/PostScript/SE: the offset is the distance *into* the pattern at which the line starts, so `[8,4]` with offset 4 starts with a 4 px dash;
    - (b) the caption read literally: a leading gap of `dashOffset`, then the pattern;
    - (c) the pattern shifted forward by the offset.

    **Implemented (a).**
    - `dashOffset` is not in the schema's Stroke definition, though the case uses it.
    - An odd-length pattern is repeated (SVG rule; the text does not say).
    - The pattern restarts for each feature and each line part, and continues through vertices.
    - Casings and centre lines are not dashed.

## F. Casing and centre line

28. **Centre lines per feature or after all main strokes.** `/req/casing/casing` explicitly draws all casings of a `zOrder` beneath all main strokes. `/req/casing/center` only says "on top of the main stroke". Readings: (a) each centre line right after its own feature's main stroke; (b) all centre lines after all main strokes of the same `zOrder`. With (a), a later road's main stroke covers an earlier road's centre line at a junction. **Implemented (b)**, by symmetry with the casing requirement.
    - Order per `zOrder` group: all casings, then all features (fill/stroke/marker), then all centre lines.
29. Casing caps and joins follow the stroke (butt and miter), so a casing does not wrap round the end of a line. This is not stated either way.
    - With no casing `width`, the StrokeStyling default of 1 px applies.
    - The schema names the member `centerLine`, while the text and the case use `center` (TODO #120). Both are accepted.

## G. Hatches

30. **Hatch colour.** The Hatch class has width, angle and distance but **no colour**. Readings: (a) lines in the Fill `color` with no background; (b) Fill `color` as a solid background with lines in black or the stroke colour. **Implemented (a).** Fill `opacity` applies to the lines.
31. **Angle reference and direction.** Hatch table: "Hatches orientation clockwise degree", with no reference direction. The text's own TODO (#146) says it should probably be counter-clockwise from +x, like the gradient angle.
    - **Implemented:** 0° = horizontal lines; positive angles turn clockwise on screen. So 45° gives lines from top-left to bottom-right ("\") and 90° gives vertical lines.
    - Alternatives: counter-clockwise (45° = "/"), or 0° = north, as a compass bearing (45° = "/").
32. **Distance and phase.**
    - `distance` is read as centre-to-centre spacing, not the gap between lines.
    - The phase is not specified. **Implemented:** one line passes through the top-left corner of the image (pixel (0,0)), so the pattern is anchored to the image, not to the CRS origin, the polygon or its bounding box.
    - Defaults come from the figure caption "Default hatch properties (width: 1 px, angle: 45°, distance: 10 px)"; no default table exists. Bare numbers are pixels.

## H. Dot patterns and stipples

33. **Dot pattern dots.** `/req/dot-patterns/distance` gives only the spacing. The dot size and colour are explicitly undefined (TODO #84). **Implemented:**
    - round dots 2 px in diameter, in the Fill colour, with no background;
    - grid anchored to the image's top-left corner, first dot centred at (h/2, v/2), then every `horizontal` px across and every `vertical` px down;
    - a square grid (not staggered).
34. **Stipple dots.** `/req/stipples/ratio`: "Ratio of stippling dots according to area filled". The size, colour and arrangement of the dots are undefined (TODO #84).
    - **Implemented:** each output pixel inside the area is set to the Fill colour with probability `ratio`. The pixels come from a fixed pseudo-random field over the image (seed 12345), so dots are 1 px and about 30 % of the area is covered for 0.3. No background.
    - Alternatives: a regular ordered dither; larger dots whose total area is `ratio`; `ratio` as a count of dots per unit area.

## I. Coverages and hill shading

35. **How coverage cells map to output pixels.** `/req/coverage/*` speak of "each coverage cell" and do not define resampling. **Implemented:** each output pixel takes the cell that contains the pixel centre (nearest). In the 75 m views each 150 m cell becomes a 2×2 block. In `font-outlines` (28 m pixels) cells become about 5.4 px blocks of colour.
36. **colorMap and opacityMap interpolation.** `/rec/coverage/map-interpolation` explicitly allows any non-overshooting method. **Implemented:** linear per sRGB component, clamped to the first/last entry outside the range.
    - `opacityMap` and `alphaChannel` together: not specified. **Implemented:** multiplied.
    - NODATA cells (`-9999`) are not mentioned in the text. **Implemented:** transparent.
    - The ValueOpacity table lists a member `color` ("Color associated with this value") where it should be `opacity`.
37. **Which samples hill shading differentiates.** `/req/hill-shading/hill-shading`: "differences in elevation between neighbouring samples of the elevation coverage at the resolution being rendered, over the horizontal distance between those samples". At 75 m or 28 m pixels, the native 150 m cells are not samples "at the resolution being rendered". Readings:
    - (a) differences between native cells (150 m apart), then mapped like colour;
    - (b) nearest-resample to pixels, then differentiate, which gives zero slope inside a cell and spikes at cell edges;
    - (c) interpolate the elevation to pixel centres, then differentiate.

    **Implemented (c):** bilinear interpolation of the elevation at each output pixel centre, then central differences (one-sided at the image edges) over the ground size of one output pixel. The shade is therefore computed per output pixel, while the colour comes from the nearest cell (item 35).
    - The elevation is taken as the `singleChannel` value.
    - x is east and y is north. The normal is (−f·dz/dx, −f·dz/dy, 1), normalised. The sun vector is (sin az·cos el, cos az·cos el, sin el).
38. **Hill shading defaults.** No defaults are given for `factor` or `sun`. **Implemented:** factor 1, azimuth 315°, elevation 45°. Bare angles are degrees; the schema's Angle also allows `{deg}`/`{rad}`.
    - A consequence of the requirement as written: flat ground gets a shade of sin(sun elevation) (0.5 at 30°, 0.71 at 45°), so the whole map is darkened even with no relief.
    - With a HillShading `colorMap`, I replace the colour by the mapped shade; with a HillShading `opacityMap`, I multiply the alpha. Neither is exercised by the cases.
39. **Defaults for `colorChannels` and `singleChannel`.** "fields[0], fields[1], fields[2]" is unscaled, while `colorChannels` is in 0..1. The text flags this itself (TODO #150). Not exercised.
    - The schema types `singleChannel` as `zeroToOne`, while the cases (and the text's examples) feed it elevations in metres.

## J. Other inconsistencies and undefined terms found while reading

- Clause 7 TimeOfDay table: `minutes` typed `Month` and `seconds` typed `int`, while the UML says `double`. The `visualization.timeInterval` row is defined as "Current visualization time of day".
- MultiGraphic table: `elements` multiplicity `1..*`, yet the NOTE under `/req/core/default-values` uses `elements: []` to unset a marker. A marker `{}` yields the default Dot; `null` or `elements: []` yields none.
- The named-colour table spells `fuschia` (the web name is `fuchsia`). I accept both.
- Dot: `size`/`color` are "the same values as" `stroke.width`/`stroke.color`, "the value set last applies". In JSON there is no order within a rule (`/req/json/dot-size-color`). I read `size`/`color` first and fall back to `stroke.width`/`stroke.color`.
- `/req/core/operations`: "with a null operand as specified by CQL2". The CQL2 text is not in this folder; I used SQL-style three-valued logic and NULL-propagating comparisons and arithmetic.
- Some clause 7 CSS examples use `opacity = 0.5` (with `=`) where the grammar uses `:`. Not relevant to rendering from JSON.
- Visualization and feature passes (`viz.pass`, `feature.pass`) resolve to 0. No case uses them.
