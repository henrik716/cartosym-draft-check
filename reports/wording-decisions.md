# How the wording of the rendered requirements was tightened

This log records, for each requirement whose wording was tightened, what the text said, how independent readers rendered it, the other evidence, the readings considered and the reading proposed. Each change is a proposal for the OGC CartoSym SWG; nothing here is an SWG decision unless it says so. The changes are in the PR that adds renders to the Part 1 document (branch `example-renders`).

## Method

The question was whether an implementation written only from the requirement text renders the same maps as another one written the same way.

1. **Test cases.** 20 small styles, one per requirement or small group of requirements, on real data for one area (Rondane, Norway: Kartverket N50 Kartdata, the national terrain model and a Sentinel-2 scene). Each case is a render kit: the style as CartoSym-JSON and CartoSym-CSS, the data as GeoJSON and ESRI ASCII grids in EPSG:25833, and one `view-N.json` per map (extent, size, scale, visualization date and time interval).
2. **Independent renderers.** Each run was a fresh Claude session given a sealed folder with the requirement text of `main` at c9808c0 (clauses, requirement files and schema; no figures) and the 20 kits, and asked to write a renderer in Python from that text alone, render every case, and list every place where the text left a choice open. The runs could not see this repository, pycartosym, libCartoSym, the web or each other. Six runs were made on the same text: runs 1, 2 and 4 with Claude Opus, runs 3 and 5 with Claude Sonnet, and run 6 with Claude Haiku. All rendered all 21 maps. Run 6 read the GeoJSON files with the Windows default encoding instead of UTF-8 (which GeoJSON requires), so its place names are garbled; that is a mistake of the run, not of the text.
3. **Comparison.** Each run's images were compared pixel by pixel with the others and with the draft renderer of this repository ("ours"), and their notes were merged point by point. A point where readers made different choices that change the picture is a place where the text has to say more. A point where all readers made the same unstated choice still gets a sentence, so that the next reader does not choose differently.
4. **Changes.** For each such point, one reading is proposed and written into the requirement, using, in this order: what the document itself shows (its figures and examples), consistency with the rest of the document, the mapping to SE 1.1 in Annex B, and what most readers chose. The draft renderer was then changed to follow the new wording, and the document's figures were rendered again.
5. **Check.** Fresh runs on the tightened text should then agree with each other; see "Check on the tightened text" at the end.

The six runs' notes, images and renderers, and the comparison, are in [`independent/`](independent/).

## Changes

Readers' columns: O = ours (the draft renderer before these changes), 1 to 6 = the independent runs. "—" means the run did not reach that point.

### W1. Direction of `y` in a Graphic `position` (/req/vector/graphics)

- **Before:** "a uom-qualified 2D real position offsetting the graphic from its original position". Nothing says which way `y` points.
- **Readers:** O up · 1 up · 2 up · 3 **down** · 4 up · 5 **down** · 6 up.
- **Evidence:** SE 1.1 `Displacement`, which Annex B maps a position to, displaces "above and to the right". The document's own examples were written assuming `y` up (a label offset `0 8` above a point, an elevation at `0 -6` below a name).
- **Proposed:** a positive `x` offsets to the right and a positive `y` upwards on the map, as for `Displacement` in SE 1.1.

### W2. Image `hotSpot` coordinates and units (/req/vector/image)

- **Before:** "an optional uom-qualified `hotSpot` position within the image"; the Image table says "0,0 position in the image"; the default is "its center, `{ 0.5, 0.5 }`"; clause 17 says a number without a unit is in pixels for screen-space objects.
- **Readers:** origin top left and `y` down: all. A bare number: O fraction · 1 **pixels** · 2 fraction · 3 fraction · 4 fraction · 5 fraction · 6 fraction.
- **Evidence:** the default `{ 0.5, 0.5 }` is a fraction. SE 1.1 `AnchorPoint`, which Annex B maps the `hotSpot` to, uses fractions too, but measures from the lower left.
- **Proposed:** image coordinates from the top left corner, `x` right and `y` down (as every reader assumed); a number without a unit is a fraction of the image's width or height, `pc` a percentage, other units a length. A NOTE says that `AnchorPointY` is 1 minus `y`.
- **Alternative not taken:** measure from the lower left as SE does, which would make the mapping to SE direct but would surprise readers who all assumed image coordinates.

### W3. Text alignment (/req/vector/text)

- **Before:** the alignment values are listed, but not what they mean or what the default is.
- **Readers:** all: `left` puts the start of the text at the position, `top` the top of the font's ascent; default `center` `middle`.
- **Proposed:** the same, stated.

### W4. Dot with a size of 0 or less (/req/vector/dot)

- **Before:** not stated. The core-parameters case computes negative sizes.
- **Readers:** all six drew nothing.
- **Proposed:** nothing is drawn for a size of 0 or less.

### W5. `dashOffset` (/req/dashes/dash-offset)

- **Before:** "dashing vector geometry based on a dashOffset property"; the figure caption: "a dash pattern preceded by an offset".
- **Readers:** O into the pattern · 1 into · 2 **a leading gap** (from the caption) · 3 into · 4 into · 5 into · 6 into.
- **Evidence:** SE 1.1 `stroke-dashoffset` and SVG `stroke-dashoffset` mean the distance into the pattern. The figure starts with a gap, which both readings can draw.
- **Proposed:** the distance into the dash pattern at which dashing starts at the beginning of each line, as in SVG and SE 1.1, in the units of the dash pattern, with a worked example; the pattern starts again at the beginning of each line and continues across vertices. The caption no longer says "preceded by".

### W6. Centre lines (/req/casing/center)

- **Before:** "on top of the main stroke".
- **Readers:** O per feature · 1 per feature · 2 **after all main strokes of the zOrder** · 3 per feature · 4 **after all** · 5 **after all** · 6 **after all**.
- **Evidence:** drawn per feature, the main stroke of a later road cuts the centre line of an earlier one where they join. The casing requirement already draws all casings of a zOrder together for the same reason.
- **Proposed:** the centre lines of all features with the same `zOrder` are drawn on top of the main strokes of all those features.

### W7. Label repetitions, and labels at the edge of the map (/req/labels/placement, /rec/labels/overlap)

- **Before:** "the distance between repetitions of that label is at least `minSpacing`"; nothing about the edge of the map.
- **Readers, repetitions:** 1, 2, 3 and 4: all labels with the same text in the layer, straight-line distance · 5 and 6: per feature, along the line · O: per feature.
- **Readers, edge:** O dropped · 1 kept, clipped · 2 dropped · 3 kept, clipped · 4 kept, clipped · 5 kept if its anchor is inside · 6 kept if its anchor is inside.
- **Evidence:** a road is usually split into several features; per-feature spacing repeats its number at every split.
- **Proposed:** repetitions are labels with the same content from the same data layer, measured between their positions on the map. A recommendation adds that labels that would extend beyond the edges of the map are omitted, except for maps drawn in tiles.
- **Why not the majority on the edge:** five of six readers kept such labels and clipped them, but a cut-off name cannot be read, and omitting is what the overlap recommendation already does with a label that does not fit. It is a recommendation (SHOULD), so a Renderer that clips is still conforming, and tiled maps, where a label has to cross the tile edge, are excepted. This is a choice for the SWG to confirm.

### W8. Hatches (/req/hatches/*)

- **Before:** the Hatch class has no colour; `angle` is "Hatches orientation clockwise degree", with a TODO saying it should probably be counter-clockwise (#146); `distance` is "Distance between two consecutive hatches"; nothing about the phase.
- **Readers:** lines in the fill colour with nothing between them: all. 0 = horizontal lines: all. Clockwise: all readers (O, 1 to 6) followed the table. Centre to centre, across the lines: all. Phase through the map's origin: 1 to 6.
- **Evidence:** the readers had no figures. The document's figure of the default hatch (45 degrees) shows lines rising to the right, which is counter-clockwise; the gradient `angle` also turns counter-clockwise.
- **Proposed:** the lines in the Fill's `color` and `opacity`, nothing painted between them; 0 gives horizontal lines and angles turn counter-clockwise (following the figure; the TODO now says so); `distance` between the centres of the lines, measured across them; one pattern for the whole map with a line through its top left corner, so neighbouring features line up.

### W9. Dot patterns (/req/dot-patterns/dotpattern)

- **Before:** the size and colour of the dots are not given (#84).
- **Readers:** dots of 2 pixels (1 to 6; ours 2.4) in the fill colour, nothing between them, on a grid aligned with the map; the first point half a step from the corner (O, 1, 2, 3, 4) or at the corner (5, 6).
- **Proposed:** the same, with the first point half a step from the top left corner. The 2 pixels are a proposal until #84 is decided.

### W10. Stipples (/req/stipples/ratio)

- **Before:** "Ratio of stippling dots according to area filled" (#84).
- **Readers:** random 1 pixel dots (O, 1, 2, 4) · a regular grid of dots sized to cover the ratio (3, 5, 6).
- **Evidence:** the document's figure shows dots at random, with the ratio as the share of the area covered.
- **Proposed:** dots in the Fill's colour and opacity, at random, covering the `ratio` fraction of the area. A NOTE says that dot size and placement are left to the Renderer, so two Renderers do not draw the same dots.

### W11. Font outline `size` (/req/font-outlines/size)

- **Before:** "by the thickness specified by the `size` property", no unit.
- **Readers:** pixels, extending outward by `size`: O, 1 to 5 · 6 **points** (the unit of the font size).
- **Proposed:** in pixels.

### W12. Coverage cells and map pixels (/req/coverage/single-channel)

- **Before:** "portraying each coverage cell"; nothing about map pixels finer than cells.
- **Readers:** O nearest cell · 1 bilinear · 2 bilinear · 3 nearest · 4 nearest · 5 nearest · 6 nearest.
- **Proposed:** each cell is portrayed over its whole area: a pixel takes the colour and opacity of the cell that contains its centre.
- **Open for the SWG:** whether a permission to interpolate between cells is wanted.

### W13. Hill-shading samples (/req/hill-shading/hill-shading)

- **Before:** "differences in elevation between neighbouring samples of the elevation coverage at the resolution being rendered".
- **Readers:** O cells, central differences · 1, 2, 4 and 5 bilinear at map pixels · 3 and 6 cells, central differences.
- **Evidence:** at map pixels finer than the cells, differencing bilinearly interpolated values gives faceted relief (runs 1, 2, 4 and 5 noted this themselves). We read "at the resolution being rendered" as being about maps coarser than the coverage (overviews); that is an assumption, to be confirmed by Jérôme, who proposed the wording.
- **Proposed:** the cells where the map is as fine as the coverage or finer, the coverage resampled to the map's resolution where it is coarser; central differences, repeating the edge sample at the edge.

### W14. Opacity applied together (/rec/core/opacity-together)

- **Before:** "to the fill, the stroke and the graphics of markers together".
- **Readers:** all: per feature, so that different features still show through each other.
- **Proposed:** the same, stated.

### W15. Features that no rule selects (/req/core/symbolizer)

- **Before:** "portraying data using the Symbolizer properties resulting from all selected StylingRules, using the default values for properties not set by any selected rule"; a NOTE under /req/core/default-values says "so that every feature is visible by default".
- **Readers:** drawn with all the defaults (white fill, black 1 px stroke, white 10 px Dot): O, 1 to 5 · 6 **not drawn** (it read the selector as deciding whether a feature is portrayed at all).
- **Evidence:** the NOTE; example 11 starts with `{ visibility: false; }` to hide everything no later rule shows, which is only needed if unselected features are drawn.
- **Proposed:** a requirement part: features and coverage cells that no rule selects are portrayed with the default values, so a style hides data only by setting `visibility` to false.

## Expression requirements

The same method was applied to the 57 expression requirements. Three evaluators (Claude Opus, Sonnet and Haiku) were written from the same text alone and run on the 123 cases of this repository's test harness, without the expected values or the harness's notes. Their notes, code and results are in [`independent/`](independent/) (`expr-run1` to `expr-run3`), and the comparison in [`independent/expression-results.md`](independent/expression-results.md).

- 121 of the 123 cases: all three evaluators gave the result the harness expects.
- 0 cases: the evaluators disagreed with each other.
- 2 cases: all three agreed with each other but not with the harness.

### X1. `max` with three arguments: the harness was wrong

- **Case:** `max(1, 5, 3)`, expected 5.
- **Text:** /req/math/max: "taking two numeric arguments"; /req/functions/call-expressions: a call whose arguments do not match the parameters "in number or type" evaluates to NULL.
- **Evaluators:** all three gave NULL.
- **Change:** none to the text. The harness case now tests `max(1, 5)` = 5, a new case tests `max(1, 5, 3)` = NULL, and the draft renderer's `max` and `min` take exactly two arguments (it accepted any number).

### X2. `like` and an escape character

- **Case:** `'50%' like '50\%'`, expected true (libCartoSym supports a backslash escape).
- **Text:** /req/text-relation/like defines `%` and `_`, and no escape character.
- **Evaluators:** all three gave false, reading the backslash as an ordinary character.
- **Proposed:** a requirement part: a backslash in the pattern makes the character after it match only itself (`'50\%'` matches `50%`, `'\\'` a single backslash). CQL2 defines the same escape: Requirement 5 (`/req/advanced-comparison-operators/like-predicate`), part K: "The escape character SHALL be the back slash (ASCII x5C, `\`)." This is issue #181, which also asks how the backslash is written in CartoSym-CSS; the proposal writes it once (`'50\%'`).

### Open points the cases do not reach

All three evaluators agree on the 123 cases partly because the cases stay away from places the text leaves open. Their notes list these, which need cases, and wording or issues:

- Operator precedence and associativity are given only by the order of the alternatives in the ANTLR grammar: unary minus binds tighter than `^` (`-2 ^ 2` = 4), `^` is left-associative (`2 ^ 3 ^ 2` = 64), all relational operators share one level, and `not` binds looser than them (issue drafted on 2026-11-13).
- The Logical Operators table is two-valued ("True if and only if ..."), while /req/core/operations defers NULL operands to CQL2, which is not in the text; all three used Kleene logic.
- `random()` is not a function call in the CartoSym-CSS grammar: `expCall` needs at least one argument, so the parser reads `random()` as an empty instance (`expInstance`, the rule for `Dot { ... }` and `INTERVAL(start: ...)`). (First written here as "cannot be written"; the grammar check showed it parses, as an instance.) [#196](https://github.com/opengeospatial/cartographic-symbology/pull/196) makes it a call.
- `viz.sd` and `visualization.scaleDenominator` (and the other `viz.*` names) are not said to be aliases; the schema allows only `viz.*`, the text names only `visualization.*`.
- `true`, `false` and `null` are not tokens of the lexer, so the grammar reads them as identifiers.
- Unary minus has no stated meaning; the unit words (`m`, `px`, `pt`, ...) cannot be property names unless quoted.
- Return types: whether `ceil(2.5)` and `abs(-2)` are integers or reals (the UML says real; the requirement says "integral value").
- `substitute`: all occurrences (the table) or one (the requirement's "replaces a substring"); all three chose all.
- The accent folding table beyond Ø and Ł; function names' case; `format` with mismatched specifiers.
- The JSON schema cannot encode `intDiv`, `mod`, `notLike`, `notBetween`, `notIn` or a null literal in arithmetic, comparison and `like` operands.

## Contradictions fixed

| Where | Before | After |
|---|---|---|
| Clause 7, system identifiers | `visualization.timeInterval`: "Current visualization time of day" | "Current visualization time interval" |
| Clause 7, TimeOfDay class | `minutes`: Month | int |
| Clause 7, Visual Ordering Constructs | `zOrder`: float | int, as in the Symbolizer table and /req/core/z-order |
| Clause 9, ValueOpacity class | `color` (a copy of ValueColor) | `opacity` |
| Hatch table | angle "clockwise" | counter-clockwise, as the figure shows (W8) |

## Contradictions not fixed here

These need the schema PR (#188) or an SWG decision, and are listed for the issues:

- `center` (rc-casing) and `centerLine` (schema on `main`); #188 uses `center`. `dashOffset` is missing from `main`'s schema; #188 adds it.
- The text names `dataLayer.identifier`, `visualization.scaleDenominator`, `feature.identifier`, `feature.geometryDimension` and `dataLayer.featuresGeometryDimension`; the schema and the examples use `dataLayer.id`, `viz.sd`, `feature.id` and `...Dimensions`.
- Colour components: Color is a float in the model and `colorChannels` 0 to 1, while JSON colours are 0 to 255 (#150). The schema types `singleChannel` as 0 to 1, but clause 9 and the examples use elevations.
- Resource `url` (clause 8 table) and `uri` (schema).
- Text alignment members: `horzAlignment`/`vertAlignment` (table), `horizontal`/`vertical` (UML and CSS), `hAlignment`/`vAlignment` (schema).
- The unit lists of /req/vector/units, clause 8, the GraphicalUnit enumeration, /req/dashes/dash-pattern, clause 17 and the schema differ; `inch` and `in` are both used.
- Schema: the second branch of `dotpattern` has no `type` or `properties`; `main`'s schema rejects hex colour strings as a `color` but accepts them in `colorMap`.

## Points every reader chose the same way, left for the SWG

Not written into the text here, because they are not about one requirement or need a decision on defaults:

- Markers go at every vertex of a line and at the area centroid of a polygon (which can lie outside it).
- Within a feature: fill, stroke, centre line, markers; Text in a marker has no collision handling.
- zOrder sorts across all layers; ties keep layer order, then feature order.
- A higher label `priority` wins; no priority is 0 (TODO #148).
- The default Marker is a white 10 px Dot without an outline, so it cannot be seen on a white background or on the default white fill, although the NOTE gives "every feature is visible by default" as its purpose (run 4).
- Defaults that are not defined anywhere: font face and size, casing and centre-line colour and width, font outline colour and opacity, hill-shading `factor` and `sun`; the size of an Image (all drew it at its native pixels).

## Found while making the figures, for the SWG

- Caps and joins: Part 1 fixes butt caps and miter joins (clause 8), and its Stroke has no `cap` or `join`; round caps and joins are in Part 2's "Joins and Caps" class. N50 starts a new feature wherever an attribute changes, so the figures show a notch where two pieces of a road meet at a bend. Joining pieces with the same properties (tools/fetch_n50.py) leaves 378 such joints in the Rondane roads, 219 of them differing only in `validDate`. Either move `cap` and `join` into Part 1's Stroke, or say in clause 8 what the defaults do where a line is split. Posted as #193; the other open rendering details are #194.
- Example 8's `factor: 56` draws the Rondane relief almost black with `factor` as vertical exaggeration: lower it, or say which data it was made for.
- The size of an Image: the draft renderer draws it 24 px wide, the readers at its native pixels (see above). The icons of example 2 are SVG files 24 px wide, so both readings give the same figure.

## Check on the tightened text

Three fresh runs were made on the tightened text (the working tree of `example-renders` after W1 to W15 and X2), with the same 20 kits and instructions as before: verify 1 with Claude Opus, verify 2 with Claude Sonnet and verify 3 with Claude Haiku. Each was also asked to quote the words it relied on for each point. Their notes and renderers are in [`independent/`](independent/) (`verify1` to `verify3`), the side-by-side maps in [`independent/verify-strips/`](independent/verify-strips/) and the pixel comparison in [`independent/verify-pixel-differences.md`](independent/verify-pixel-differences.md).

| Point | Before (six runs) | After (three runs) |
|---|---|---|
| W1 `y` of a position | 4 up, 2 down | 3 up |
| W2 bare `hotSpot` number | 5 fraction, 1 pixels | 3 fraction |
| W5 `dashOffset` | 5 into the pattern, 1 leading gap | 3 into the pattern |
| W6 centre lines | 2 per feature, 4 after all | 3 after all |
| W7 repetitions | 4 same text in the layer, 2 per feature | 3 same text in the layer |
| W7 labels at the edge | 1 dropped, 5 kept (clipped) | 3 dropped |
| W8 hatch angle | 6 clockwise | 3 counter-clockwise |
| W10 stipples | 3 random, 3 regular grid | 3 random (dot size and placement left to the Renderer, as intended) |
| W11 font outline unit | 5 pixels, 1 points | 3 pixels |
| W12 cells and pixels | 4 nearest, 2 bilinear | 3 nearest |
| W13 hill-shading samples | 2 cells, 4 bilinear at pixels | 2 cells, 1 misread (below) |
| W15 unselected features | 5 drawn, 1 not drawn | 3 drawn |

The images agree accordingly: verify 1 and verify 2 match each other to 0.0 % of pixels on every map except the stipples, whose dots the text now leaves to the Renderer on purpose. Verify 3 draws all text slightly larger and places the elevation numbers lower, a font-size conversion inside that renderer rather than a different reading; it differs on the three maps with text only.

What the check still found, and what was done:

- **W13, reworded again.** Verify 3 called the hill-shading case (75 m pixels over 150 m cells) the "coarser" case, misreading "where the map's resolution is coarser". The sentence now says "where a pixel of the map covers no more ground than a cell (for example 75 m pixels over 150 m cells)".
- **W16. North for the sun.** Verify 1 noted that "clockwise from North" can mean grid north or true north, about 4.5 degrees apart in UTM zone 33 at Rondane. Every reader used grid north (up on the map); /req/hill-shading/sun now says so.
- **W17. Annex B, Marker position.** Verify 1 noted that Annex B mapped a Marker `position` to SE `<AnchorPoint>`, which contradicts W1 and duplicates the `hotSpot` row. It now maps to `<Displacement>` (inside `<Graphic>` for SE 1.1, and inside `<PointPlacement>` for labels in SE 1.1 and SLD 1.0), as the annex's own SE example already does. Annex B is mostly Maxime's work, so this row should be checked by him.
- **Dot pattern TODO.** The TODO asked to define the size and colour of the points, which W9 now does; it now asks to confirm the proposed 2 pixels (#84).
- **Draft renderer.** The comparison showed our label placement differing from both verify 1 and verify 2 in two maps. The cause was our estimate of text width (0.6 em per character); the draft renderer now measures text with the font where it can, and then places the same labels as both runs.

Points the verification runs still list as open, for issues rather than this PR: the miter limit; a stroke of width 0; the default Dot colour (white) against the default Stroke colour (black) when a Dot's colour is its stroke's; the size at which an Image is drawn (it has no size property); how a number is written as text; the colour space for colour-map interpolation; the resampling for maps coarser than the coverage; a pixel centre on the edge between two cells; and defaults for fonts, casings, centre lines and font outlines.

## Replies on the pull request

Jérôme St-Louis replied to these changes on [#192](https://github.com/opengeospatial/cartographic-symbology/pull/192) on 16 and 17 November 2026, and on #100, #193, #194 and #195 where they bear on a change. These are one member's answers, not SWG decisions, and the branch does not follow them yet. "Differs" means his answer differs from the change proposed above.

| Change | Reply | What he answered |
|---|---|---|
| W1 | Differs | In screen space, a positive y was intended to point down. |
| W2 | Differs | Origin top left, as proposed, but a number without a unit is in pixels, as for everything else: 50 pc 50 pc is the centre and 0 0 the top left corner. The pixels are those of the image file (#100). |
| W3 | Differs | The meaning is right (top is the top of the font's ascent), but the default was meant to be top left; a baseline alignment may be added (#195). |
| W4 | Agrees | A Dot of size 0 draws nothing. |
| W5 | Agrees | Yes, restarting at each line; [5, 2] is a 5 pixel dash and a 2 pixel gap from the start of the line. |
| W6 | Agrees | Centre lines after all main strokes of the same zOrder: correct. |
| W7 | Differs | Whether labels that cross the edge of the map are placed should be a Renderer option, not required either way (static maps, dynamic maps, tiles), perhaps with a NOTE saying so. |
| W11 | Agrees | Pixels unless another unit is given. Still to decide: whether a font size without a unit is in points or pixels. |
| W8 | Agrees | Counter-clockwise sounds right. |
| W9 | Open | Not settled: he would expect dot patterns to be perhaps more random, and asks whether both stipples and dot patterns are needed (#84). |
| W10 | Open | Not settled: he would expect a stipple to be a regular bitmap pattern, for example 8 × 8 (#84). |
| W12 | Differs | Do not prescribe one mechanism (coverages may be draped on 3D terrain, or drawn from several levels of detail). Interpolation is allowed, but only for continuous variables, as the logical schema says; where nothing says, CartoSym need not require a behaviour. |
| W13 | Agrees | Essentially yes, but the wording should leave room. |
| W16 | Open | It needs room for global data and globes; "north as shown on the map at the shaded point" might work. Defaults suggested on #194: azimuth 315, elevation 45. |
| W14 | Open | Per-feature group opacity may be very costly for many features; the recommendation might be left open, or noted as still under consideration. |
| W15 | Agrees | Correct. He suggests a permission in Part 1 to draw a hairline outline, so that the white default Dot shows on white. |
| X1 | Differs | min and max should take any number of arguments (added to libCartoSym); even one may make sense. |
| X2 | Agrees | Yes, '50\%' matches the text 50% (also on #181). |

Also on #193 and #194: Part 1 should default to round caps and round joins, which removes the miter limit question; a stroke of width 0 draws nothing; casing and centre line widths default to 0 (off), with black if only a width is set; `hillShading.factor: 0` is the default and turns hill shading off; an Image is drawn at its size in pixels, and an Image `size` property may be needed (#100); colour maps may be interpolated in linear RGB.
