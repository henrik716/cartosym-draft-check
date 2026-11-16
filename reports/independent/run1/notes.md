# Notes: where the text left a choice open

Renderer: `renderer/render.py` (with `style.py`, `expr.py`, `colors.py`), run as
`uv run --no-project --with numpy --with pillow --with pycairo python renderer/render.py cases out`.
It reads only `style.cs.json`, the data and `view-N.json`. Drawing uses pycairo (general 2D library, anti-aliased); text uses cairo's system font lookup (Arial).
All 20 cases (21 views) render. Each entry below gives the requirement, the words that leave the choice open, the readings considered, and **the one implemented**. Cases affected are in brackets.

## A. Core: cascade, defaults, ordering

**A1. Features that no rule selects** (/req/core/symbolizer, /req/core/default-values) [core-opacity, all cases with an unselected feature]
Words: "portraying data using the Symbolizer properties resulting from all selected StylingRules, using the default values for properties not set by any selected rule".
Readings: (a) every feature of every layer in the view is portrayed; a feature that no rule selects gets all defaults: white fill, black 1 px stroke and a white 10 px Dot; (b) only features selected by at least one rule are portrayed.
**Implemented (a)**, because the NOTE under /req/core/default-values says "every feature is visible by default". Visible effect: in core-opacity the non-lake Landcover polygons are drawn with a white fill and a black 1 px outline. The outline of a neighbouring polygon shows as a black line inside the lake's half-transparent navy stroke. Under (b), only the lakes would be drawn.

**A2. Order of nested rules against later siblings** (/req/core/rules, /req/core/nested)
Words: "rules appearing later in a Style's list of rules ... overriding"; "inheriting from, and overriding, the Symbolizer properties of its parent rule".
The text does not say whether a nested rule of an earlier rule counts as "earlier" than a later top-level rule.
**Implemented depth-first document order**: parent, then its nested rules in order, then the next sibling. This makes no difference in these cases.

**A3. Whole-object replacement** (/req/core/rules vs /req/core/instances, /req/json/partial-update) [core-time, core-rules]
Words: "SHALL be interpreted as overriding all Symbolizer properties set by earlier rules".
Readings: an object property set without `alter` either replaces the whole object, with defaults for members not given, or overrides only the members it names.
**Implemented whole replacement**, which is the only reading under which `alter` is useful. In core-time, the nested `stroke: {crimson, 3 px}` replaces the parent stroke. When `alter: true` hits a property that no earlier rule set, the merge starts from the default object, following the words "as set by earlier rules or by default values".

**A4. zOrder scope and its type** (/req/core/z-order)
Words: "features and coverage cells of a single rendering pass in increasing order of their resolved `zOrder`".
Readings: zOrder sorts across all layers, or only within a layer, with layers in view order.
**Implemented a global sort**, with key (zOrder, layer position in the view, feature order). Equal zOrder keeps the view's layer order. The only painter's algorithm in the text (zOrder outside layers) is commented out.
Contradiction: the Symbolizer table gives zOrder as `int`, while the "Visual Ordering Constructs" table gives it as `float`. I accept floats.

**A5. Order of fill, stroke and marker inside one feature** (clause 8, /req/vector/*)
No normative text gives this order. Annex F, which is informative, says the fill is drawn first, then the stroke.
**Implemented fill → stroke → centre line → marker graphics**, so markers are on top.

**A6. How opacity is applied** (/req/core/opacity, /rec/core/opacity-together) [core-opacity]
**Implemented the recommendation per feature.** Fill, stroke, centre line and markers are drawn into one group, and the group is painted with the symbolizer opacity. Different features still show through each other. The casing, drawn in its own phase (C3), gets `casing.opacity × opacity` separately.
The text does not say whether "together" also spans features or layers.

**A7. Names of system identifiers differ between text and schema** (/req/core/layers, /req/core/scale, /req/core/time, clause 8 table)
- The text uses `dataLayer.identifier`, `visualization.scaleDenominator`, `feature.identifier` and `feature.geometryDimension` (table) / `geometryDimensions` (UML). The schema and the cases use `dataLayer.id`, `viz.sd` and `viz.timeInterval.start.date`.
- `visualization.timeInterval` is defined as "Current visualization time of day", a copy error.
- `start.date` exists only in the UML (TimeInterval → TimeInstant → date).
**Implemented both spellings as aliases.**

**A8. Comparing a text property with a date** (/req/core/relational, /req/core/time) [core-time]
`validDate` is a JSON string. `viz.timeInterval.start.date` is a Date. The text defines no coercion: the Relational Operators table only says "The first operand is greater than ...".
Readings: (a) parse an ISO-date string as a date when the other operand is a date; (b) compare as text after formatting the date (same result for ISO dates); (c) the types are incomparable, giving null, so no road is red.
**Implemented (a)** (the README states `validDate` is an ISO date).

**A9. Null semantics** (/req/core/operations)
Words: "with a null operand as specified by CQL2". The definition is outside the spec.
**Implemented Kleene three-valued logic**: and/or/not; a comparison with null gives null; a selector that gives null does not select (NOTE under /req/core/selector). Places without `elevation` are therefore never selected by `elevation >= ...`.

**A10. Arithmetic in a core case; negative sizes** (/req/core/parameters, /req/parameter-values/expressions, /req/arithmetic/*) [core-parameters]
`size: (elevation - 900) / 100` needs both the Parameter Values class and the Arithmetic class. Core alone allows only literals, so a core-only renderer cannot draw this case. Both classes are implemented here.
For spot heights below 900 m the result is negative. A negative Dot size is undefined. **Implemented: not drawn.** Alternatives are drawing the absolute value or clamping to 0.
The bare number is taken as pixels.

**A11. Time identifiers when the view has only a date**
`viz.dateTime` and `viz.timeOfDay` are taken as midnight on `visualization.date`. This is not used by any case.

## B. Units

**B1. Ground units** (/req/vector/units, clause 8 "Graphical Units of Measure")
Words: "applying the appropriate unit transformation".
Metres can be converted with the view's ground resolution (bbox width / pixel width) or with `scaleDenominator × pixel size`.
**Implemented the bbox resolution.** Both give the same value in these views (for example 2.24 and 5.6 m/px in vector-units), but they differ if the declared scale does not match the bbox, or in a geographic CRS.

**B2. The list of units is inconsistent across the text**
- /req/vector/units lists "pixel, millimeter, inch, percentage, meter, foot".
- The units table in clause 17 adds `pt`, `em` and `cm`.
- /req/dashes/dash-pattern requires "pixels, points, millimeters, centimeters and inches".
- The table calls 1 pt "0.3528 mm". **Implemented 25.4/72 mm.**
- `em` with no font is taken as 12 pt (not used).
- The pixel is "0.28mm x 0.28mm" unless the viewer resolution is known. The view's `pixelSize_mm` (0.28) is used.

**B3. `pc` means percent, and what it is a percentage of** (clause 17 units table) [vector-image]
`pc` is percent here (in Web CSS it is the pica). It is "relative ... depends on context". For `hotSpot`, **implemented as a percentage of the image width and height**, measured from the top-left corner with y down, so `50 pc 100 pc` is the bottom centre.

**B4. Bare numbers** (clause 17 units table, Image defaults)
"(none) ... For screen-space objects, defaults to pixels", but the default hotSpot is written as bare fractions "`{ 0.5, 0.5 }`". These contradict each other.
**Implemented: bare numbers are pixels**, and the default hotSpot is the image centre.

## C. Vector features

**C1. Graphic `position` axis direction** (/req/vector/graphics) [vector-marker-dot, vector-text, labels-priority]
Words: "a uom-qualified 2D real position offsetting the graphic". The direction of +y is not defined.
**Implemented +x right, +y up (map north).** The evidence is vector-text, where `position: 0 -6` with `alignment: center top` only makes sense if −6 puts the elevation below the dot.
Under the y-down reading, the small dot in vector-marker-dot would be lower-right instead of upper-right, and the labels in labels-priority would be below their points instead of above.
The Image `hotSpot` is read in image coordinates (y down; B3), so the two UnitPoint uses have opposite y axes.

**C2. Where markers are drawn** (/req/vector/marker)
Words: "at the points of vector geometry (for points and line strings) and at the centroid of polygons".
**Implemented:**
- at every vertex of a line, including both ends;
- at the area centroid of a polygon, which can fall outside the polygon;
- for a multi-polygon, one area-weighted centroid (the alternative is one per part).

**C3. Casing geometry** (/req/casing/casing, /req/casing/center) [casing]
- The casing is one stroke of width `width + 2 × casing.width` under the main stroke, with the same butt caps and miter joins, so it does not extend past the ends of a line.
- Casings of all features with the same zOrder are drawn first; this is specified.
- The casing is drawn solid even when the main stroke is dashed, because StrokeStyling has no dash members. Alternative: dash it with the main stroke.
- The text does not say whether centre lines are drawn per feature, right after each main stroke, or all after all main strokes. **Implemented per feature.** A later feature's white main stroke can then cut an earlier feature's orange centre line at a junction.
- Schema vs text: the schema names the member `centerLine`, the text `center` (TODO #120). Both are accepted.

**C4. Stroke joins, caps and alignment** (clause 8 Strokes)
Words: "By default the end of open subpaths are butt caped and at the corners of paths are miter joined". No miter limit is given; **implemented 10** (the cairo default).
The stroke is centred on the geometry, half inside polygons. This is not stated.
A stroke `width: 0` draws nothing.

**C5. Polygon fill rule and line fills**
**Implemented even-odd for holes**, and fills apply to polygons only.
Annex F (informative, SymCore 1) says "If a line is used, then the line (string) is closed for filling". Because the default Fill is white, a renderer following Annex F would paint white areas under every line.

**C6. Dashes** (/req/dashes/dash-pattern, /req/dashes/dash-offset) [dashes]
- `dashOffset` has no definition beyond "dashing ... based on a dashOffset property". The figure caption says "a dash pattern preceded by an offset".
  Readings: (a) SVG `stroke-dashoffset`: start 4 px into the pattern, so the line begins with a 4 px dash and then a 4 px gap; (b) shift the pattern forward, so the line begins with a 4 px lead-in (gap or solid) and then the 8 px dash.
  **Implemented (a).**
- The pattern runs continuously over vertices and restarts at each feature and each line part.
- `dashOffset` is missing from the JSON schema's `stroke`; the case uses it.
- The JSON schema's `dashPattern` uses `unitValue`, and the dashPattern table uses the type "UnitValue", which is not defined anywhere.

**C7. Dot** (/req/vector/dot)
**Implemented as a filled circle with diameter `size`.** The default Dot is white, so the default marker cannot be seen on a white background or a white fill.

**C8. Image** (/req/vector/image) [vector-image]
- The Image has no size or scale property. **Implemented at native size** (one image pixel per map pixel, 24 px), with bilinear sampling at sub-pixel positions.
- Tint is applied to straight (non-premultiplied) RGB; alpha is unchanged.
- The text does not say what a relative `path` is relative to (the style file, the working directory or the data). `../icons/hut.png` relative to the case folder points to the empty `cases/icons/`. **Implemented a fallback** to `<case>/icons/<file name>`. This is a harness issue, but the text gives no rule either.
- The clause 8 Resource table names `url`; the schema and the case use `uri`.
- `alphaThreshold` is implemented as an alpha test (permission). It has no effect at 0.

**C9. Text and alignment** (/req/vector/text, /req/vector/fonts) [vector-text, labels-*]
- **Alignment meaning.** **Implemented:** `left` means the text starts at the anchor and runs right; `right` ends at the anchor; `top` puts the top of the text at the anchor; `bottom` puts the bottom there. Alternative: the alignment names the side of the anchor where the text goes.
- **Vertical box.** **Implemented the font's ascender and descender lines** rather than the ink of the string; `middle` is halfway between them.
- **Default alignment.** Not defined; **implemented `center middle`**.
- **Member names differ in four places:**
  - Text table: `horzAlignment`/`vertAlignment`
  - UML: `horizontal`/`vertical`
  - CSS example: `TextAlignment(horizontal: ...; vertical: ...)`
  - schema: `hAlignment`/`vAlignment`
  All of these are accepted.
- **Font.** `color` and `opacity` appear in the UML and the schema but not in the Font table. No defaults are given. **Implemented:** face Arial, size 10 pt, colour black, opacity 1.
  The size is in points and is converted with the 0.28 mm pixel (9 pt = 11.34 px). It is taken as the em size.
  `bold` and `italic` use the system's bold and italic faces.
- **Number to text.** Converting a number to text (`text: elevation`) is undefined. Integers print without a decimal point.
- **No collisions in markers.** Text in a *marker* takes no part in collision handling. In vector-text, "Søre Smedhamran" and "Nørdre Smedhamran" overlap.

## D. Fills

**D1. Hatch colour** (/req/hatches/hatch) [hatches]
The Hatch class has no colour, but the cases give `fill.color` next to `hatch`.
Readings: (a) hatch lines in `fill.color` (with `fill.opacity`) and no solid fill; (b) a solid fill in `fill.color` with hatch lines in another colour (the stroke colour? black?); (c) both.
**Implemented (a).**

**D2. Hatch angle** (/req/hatches/angle) [hatches]
Words: "Hatches orientation clockwise degree". The 0° reference is not given. The TODO(review) note says it should perhaps be counter-clockwise.
**Implemented: 0° = horizontal lines, positive clockwise on screen.** 45° gives "\" lines and 90° vertical. Other readings: 0° = vertical (a compass bearing), or counter-clockwise.

**D3. Hatch distance, phase and defaults**
- "Distance between two consecutive hatches" is **implemented centre to centre** (not the gap between lines).
- The pattern is anchored to the image origin (a line passes through pixel (0,0)). The text does not say whether it should be anchored per feature.
- Defaults come only from a figure caption ("width : 1 px, angle : 45 °, distance : 10 px"); these are used.

**D4. Stipple** (/req/stipples/ratio, TODO #84) [stipples-dot-patterns]
Words: "Ratio of stippling dots according to area filled". The dot size, colour and distribution are not given.
**Implemented** 1-pixel dots in `fill.color`, each pixel set independently at random with probability `ratio`. The random field has a fixed seed and is anchored to the image, so the covered fraction is about the ratio.
Other readings: larger dots, a blue-noise or regular distribution, or a ratio of dot count rather than area.

**D5. Dot pattern** (/req/dot-patterns/*, TODO #84) [stipples-dot-patterns]
The dot size and colour are not given. **Implemented** 2 px dots in `fill.color` on a rectangular grid at ((i+½)·h, (j+½)·v), anchored to the image origin.
Other readings: a staggered grid, or the default Dot (10 px white), which with 8×4 px spacing would merge into a solid area.
Schema defect: in `dotpattern`, `{"distance": ...}` sits directly inside `oneOf` with no `type`/`properties`, so the schema puts no constraint on the object.

## E. Coverage and hill shading

**E1. Cells vs rendered pixels** (/req/coverage/*, /req/hill-shading/hill-shading) [coverage-opacity-map, hill-shading-sun, font-outlines]
The text portrays "each coverage cell", but hill shading uses "neighbouring samples of the elevation coverage at the resolution being rendered". The resampling method is not given.
Readings: (a) nearest neighbour, so cells are drawn as squares; slopes measured at render resolution are then zero inside a cell and spike at cell edges; (b) bilinear, or smoother, resampling to pixel centres.
**Implemented (b) bilinear for all coverage values**, with cell values at cell centres and the colour and opacity maps evaluated per rendered pixel.
Visible effect: at 5.4 px per 150 m cell (font-outlines) the shading shows cell-sized facets, because bilinear slopes are constant within a cell. A smoother method would remove them. Results at this level depend on an unstated choice.

**E2. Slope computation** (/req/hill-shading/hill-shading)
**Implemented** central differences over two rendered pixels (one-sided at the image edges); the horizontal distance is the ground pixel size in metres.
Pixels outside the grid, and NODATA cells, are transparent.

**E3. Which field is the elevation; how hill shading combines with colours** (/req/hill-shading/*)
- The text does not say which field is the elevation. **Implemented the `singleChannel` value.**
- With no HillShading colorMap, the cell's colour from the Symbolizer `colorMap` is multiplied by the shade. This follows the text "multiplying the red, green and blue components of each cell by its shade value".
- With a HillShading colorMap, its colour replaces the cell colour. With a HillShading opacityMap, its value multiplies the other opacities. Both are inferred and not used by these cases.
- Defaults for `factor` and `sun` are not defined. **Implemented 1 and azimuth 315°, elevation 45°** (not used).
- Bare angles are taken as degrees.

**E4. Literal consequence of the shade formula**
Flat terrain gets shade = sin(sun elevation): 0.5 for hill-shading-sun (30°) and 0.71 for font-outlines (45°). The whole map is therefore darkened. The text allows no normalisation to keep flat ground at full brightness, so none is done.
"Azimuth ... clockwise from North" is taken as grid north (up in EPSG:25833). The meridian convergence (about 3–4° here) is ignored.

**E5. colorMap / opacityMap** (/req/coverage/color-map, /rec/coverage/map-interpolation)
- **Implemented linear interpolation in sRGB components.** The colour space is not stated.
- Entries are sorted by value. The text does not require ascending order.
- Values outside the range take the end entries; this is specified.
- The ValueOpacity table lists a `color` member instead of `opacity` (copy error).
- The ValueColor/ValueOpacity tables say `name`; the UML says `label`.

**E6. Schema vs cases**
- `singleChannel` is typed `zeroToOne` in the schema, but the cases (and clause 9) feed it elevations (300–2200).
- Colour strings like `"#8a7a5a"` (used in every colorMap) are not allowed by the schema's `color`, which accepts only web colour names as strings. They are accepted here anyway.
- JSON colour arrays and objects are 0–255 (schema), while the model's Color has float components and `colorChannels` is 0–1 (TODO #150).

**E7. Coverage selectors**
Selectors are evaluated with whole-grid values. Only selectors that are uniform over the grid (here `dataLayer.id`) are supported. A per-cell selector would raise "unsupported"; none occurs in the cases.

## F. Labels

**F1. Pass and opacity** (/req/labels/label)
Labels are drawn after everything else, and the symbolizer opacity is not applied to them (NOTE under /req/core/opacity).

**F2. Overlap** (/rec/labels/overlap)
- A label is omitted if its box overlaps an already placed label. The box is the advance width × (ascender + descender), padded by the outline size; Dots in a label use their circle.
- Labels do not avoid markers or lines.
- **Implemented:** a candidate whose anchor is outside the image is skipped; a label that is partly outside the image is kept and clipped. Neither is specified.

**F3. Priority** (/req/labels/placement, TODO #148) [labels-priority]
**Implemented: a higher number means higher priority.** The TODO says this is unconfirmed. The default priority is undefined; **implemented 0**. Ties are broken by data order.

**F4. Labels on lines** [labels-spacing]
Neither orientation nor placement along a line is defined. **Implemented horizontal, unrotated text centred on points of the line.**

**F5. minSpacing and maxSpacing** (/req/labels/placement) [labels-spacing]
Words: "the distance between repetitions of that label is at least `minSpacing` and, where space allows, at most `maxSpacing`".
Open points: whether "that label" means one feature's label or the same text across features (roads are split into many features); whether the distance is along the line or a straight line; where the first repetition goes; and what happens with no `maxSpacing`.
**Implemented:**
- candidates at arc length L/2 ± k·minSpacing along each line;
- a candidate is rejected if a label with the same text is already placed within `minSpacing` (straight-line distance), across features;
- `maxSpacing` is not enforced, apart from the regular candidate spacing.

**F6. Font outline** (/req/font-outlines/*) [font-outlines, labels-spacing]
- The text says only "extending outward from the glyph contours by the thickness specified by the `size` property". The unit is not given: pixels, or points like the font size. **Implemented pixels.**
- **Implemented** as a stroke of width 2·size on the glyph contours, with round joins, under the glyph fill.
- Defaults are not defined. **Implemented opacity 1 and colour white** (labels-spacing gives no opacity).

## G. Other

- **G1. Anti-aliasing.** The text does not mention it; anti-aliased drawing is used throughout.
- **G2. Capabilities.** `capabilities.*` resolves true for the classes implemented: vector, coverage, labels, hillshading, fontoutlines, hatches, stipples, dashes, casing, parametervalues, arithmetic, conditional, righthand. No case uses them.
- **G3. Visualization and feature passes.** Not implemented beyond resolving `viz.pass` and `feature.pass` to 0; no case uses them.
