# Notes: where the requirement text left me a choice

Renderer: `renderer/render.py` (numpy + Pillow only), driver `renderer/run_all.py`. Images: `out/case-NN-1.png`, all 36 rendered at exactly `width` x `height`. All 36 render without errors. Everything is drawn at 4x supersampling and box-filtered down.

Method: I read clauses 4-12, 16 (units, colours, tuples), 17, the requirement files for core, vector, labels, font outlines, coverage, hill shading, parameter values and JSON, and skimmed Annex C. I did not read clauses 13-15 or Annex B in detail, since no case needs them beyond `concatenate`, `-` and the relational operators. Choices are numbered C1.. in the order of the pipeline. "Text" quotes are exact words from the spec.

## Choices

**C1. Mapping the view to pixels; pixel size.** Clause 8, "Graphical Units of Measure": "it is equal to 0.28mm x 0.28mm"; `view-1.json` gives `bbox`, `width`, `height`, `scaleDenominator` and `pixelSize_mm`. Nothing says how bbox maps to pixels (corner or centre convention), or whether ground metres per pixel come from `bbox/width` or from `scaleDenominator x pixelSize_mm`. Readings: (a) continuous coordinates, pixel i covers [i, i+1), metres per pixel from bbox; (b) metres per pixel = scaleDenominator x 0.28 mm; (c) pixel centres at integer coordinates. Implemented (a) for geometry and (b) for `m`/`ft` lengths. In every case the two agree (e.g. case 01: 6160 m / 440 px = 14 m = 50000 x 0.00028 m), so it makes no difference here. Relied on: "one pixel ... 0.28mm", "scale denominator of the map being rendered".

**C2. Unit conversions.** Clause 16 "Units of measure": `pt` "1/72 inch (0.3528 mm)"; `mm` "Display unit ... defaults to 0.28 mm/pixel". I take `mm` and `pt` as physical lengths on the display, so px = mm / `pixelSize_mm`: 10 pt = 12.6 px, 14 pt = 17.64 px, 10 mm = 35.71 px. `m` = metres on the ground / (scaleDenominator x pixelSize). Open: whether `pt` follows `pixelSize_mm` (display) or is a fixed 96/72 conversion; I used `pixelSize_mm`. A value with no unit is in pixels ("For screen-space objects, defaults to pixels"; `/req/vector/fonts` "in pixels when no unit is given"). Text, e.g. `size: 8` in cases 17-18 is therefore 8 px, not 8 pt, while the neighbouring cases use `pt`.

**C3. Coverage sampling (`/req/coverage/single-channel`, `/per/coverage/interpolation`).** "A Renderer MAY interpolate between the values of neighbouring cells of a continuous variable" and "portraying each coverage cell over the area of that cell". Readings: nearest cell, bilinear interpolation, per-cell polygons. Implemented: each map pixel takes the cell that contains its centre (no interpolation). In cases 04-14 the pixel (28 m) equals the cell size (28 m), but the grid is offset by 64 m = 2.29 cells from the bbox, so a pixel never lines up with a cell exactly; interpolation would give a smoother, slightly different image. Nothing tells whether elevation is "continuous" (the data carries no `x-ogc-variableType`).

**C4. colorMap interpolation (`/req/coverage/color-map`, `/rec/coverage/map-interpolation`, `/per/coverage/linear-light`).** "interpolating between the colors of the two closest entries", method "not specified". Implemented: linear in the value, in sRGB components (the linear-light permission not taken). Result differs from linear-light interpolation by several levels in mid tones. Values outside the map take the first/last colour (stated).

**C5. Hill shading details (`/req/hill-shading/*`).** Open points: (a) how to compute slope ("How the differences in elevation are taken is not prescribed"): I use central differences over 2 x 28 m with the edge sample repeated (the note's example); (b) the sign/direction convention of the normal: x east, y north, z up, normal = (-factor dz/dx, -factor dz/dy, 1) normalised, "multiplying the horizontal components ... by the `factor` before normalizing"; (c) sun unit vector = (sin az cos el, cos az cos el, sin el) with azimuth clockwise from grid north ("compass bearing"); (d) shade = max(0, n.s), then RGB x shade: so flat ground has shade sin(45 deg) = 0.707 and the whole map is darker than the plain colour map. That follows from "no shade (the sun in the direction of the normal)" meaning shade 1 only for a normal pointing at the sun, but a reader could expect flat terrain to stay unchanged (i.e. normalise by the flat-terrain shade); I did not. (e) The colorMap is applied first, shade multiplied afterwards. (f) `factor` 2 with 28 m cells and ~1000 m relief gives steep shading; the note says this depends on resolution, so no adjustment.

**C6. Rule evaluation and merging (`/req/core/rules`, `/req/core/nested`, `/req/json/partial-update`).** The text says later rules override earlier ones and nested rules "inherit from, and override". Implemented: depth first, a rule's symbolizer is merged and then its nested rules are evaluated before the next sibling. A member object (`stroke`, `fill`, `marker`) is replaced as a whole unless it has `"alter": true` in which case only the listed members change. Consequence: in case 02, `stroke: {color, width}` in the class rules resets `opacity` to the default (1). Open: does a non-`alter` `stroke` object reset un-mentioned members to defaults (my reading) or keep earlier values? The CSS clause says `stroke: {gray}` "completely replace[s] stroke property".

**C7. Default marker (`Core` note "The default Marker applies to features of every geometry type").** When a layer's style never sets `marker`, I draw the default Dot (10 px, white) at each point, vertex and polygon centroid. All 36 cases set `marker` explicitly or null, so this is not exercised. The permission to draw a hairline outline round a Dot (`/per/vector/dot-outline`) was not used: Dots are plain discs.

**C8. Index base of element updates (`/req/json/array-element-update`).** The text says "zero-based array index" but its CSS equivalent writes `marker.elements[1]` for `"index": 1`. In cases 01 and 03 the CSS `marker.elements[1]` (one existing element) and `marker.elements[2]` (two existing elements) only make sense as zero-based appends when the marker has 1 or 2 elements, so I append when `index` equals the length. Not triggered at the given scales (sd 50000 and 100000 are not < 10000 or < 5000), so no image depends on it. Also unspecified: `index` greater than the length.

**C9. Drawing order (`/req/core/z-order`, `/req/vector/stroke`, `/req/vector/marker`, note after `/req/vector/marker`).** "all features with the same `zOrder`" does not say whether that means per layer or across layers. Implemented: for each distinct `zOrder` ascending, across all layers: all fills (and coverage) first, then all strokes, then all markers; inside each phase by layer order in `view-1.json`, then feature order in the file. Labels last of all. Default `zOrder` is 1 ("Symbolizer ... zOrder | 1"). Consequence in case 15: text drawn as a marker (zOrder 1) lies under lakes (zOrder 2); in case 16 the same text is a label and lies on top. Equal-`zOrder` features of one layer follow file order, which the text does not specify.

**C10. Opacity (`/req/core/opacity`, `/rec/core/opacity-together`).** The requirement says multiply the symbolizer opacity with the fill, stroke and marker graphics opacities; the recommendation says to apply the opacity to fill, stroke and marker together so they do not show through each other. They give different pixels where a stroke overlaps its own fill (case 01: opacity 0.8, fill 0.5, stroke 1.0). I implemented the requirement literally: fill alpha 0.5 x 0.8 = 0.4, stroke alpha 0.8, each composited separately (stroke centred on the boundary, half over the fill). The recommendation ("SHOULD") was not followed. For Text elements of a Marker I apply the symbolizer opacity too (Text is a Graphic); for Labels I do not (note: "does not apply to labels").

**C11. Stroke geometry.** `/req/vector/stroke` gives round caps and joins but not where the stroke sits relative to a polygon edge. Implemented: centred on the boundary. A `width` 0 or less draws nothing (stated). A polygon's holes are stroked too. Lines are not clipped specially. Dot: "filled circle whose diameter is its size".

**C12. Joining lines for labels (`/req/labels/line`).** "joining ... the line geometries of a data layer that have the same label and meet at their end points". Open: how to decide "meet" (tolerance), what happens where three lines meet, what "same label" means with several elements. Implemented: the label text of the first Text element; end points equal within 0.5 px (about 7 m at 1:50000 for case 17; I did not check whether the data's shared end points coincide exactly); at a junction the first unused line in file order is taken; chains are built greedily.

**C13. Direction of line labels (`/req/labels/line`).** "reads from left to right and is never upside down": I flip the reading direction when the chord from the first to the last element of the label points left (dx < 0). For a near-vertical line (dx = 0) both directions satisfy the text; I do not flip.

**C14. Bend limit and edge treatment (`/req/labels/line` note "How sharp a bend ... is left to the Renderer"; `/rec/labels/overlap` notes).** Implemented: a line label is omitted if the angle between the chords of two neighbouring glyphs exceeds 30 degrees or any glyph is turned more than 100 degrees; a line label must lie wholly inside the map. A point label is placed even where it is cut by the map edge (cases 19-21 show this), since the text leaves it to the Renderer. A glyph is positioned on the line at the centre of its advance, rotated to the chord over its width (min 3 px); kerning between glyphs is not applied on curved text.

**C15. Where on the line the label goes; repeating (`/req/labels/placement`, `/req/labels/line`).** Texts: "so that the distance between repetitions of that label is at least `minSpacing` and, where space allows, at most `maxSpacing`", "measuring the distance between repetitions on the map between their positions". Open: (a) whether `minSpacing` alone causes repetition (a single label also satisfies "at least"); (b) which positions are tried first; (c) "on the map" = straight line or along the line; (d) what the label's "position" is when elements have offsets. Implemented: with `minSpacing` set, as many labels as fit are placed, greedily, starting at the candidate nearest the median of valid positions and then in order of increasing distance from it, 3 px apart; without `minSpacing` one label per joined line. Distance = straight-line pixel distance between anchors (the Graphic origin, i.e. `position` 0 0; for case 18 the anchor is the Dot, for cases 17 and 22-24 the text starts 7 px after it or is centred on it). With the visible part of the roads only about 300 px across, `minSpacing` 150 and 300 (cases 17, 18, 23, 24) give one label per road and 80 (case 22) gives several. Different placement rules for (b) would move every road label along its road.

**C16. Collision test (`/rec/labels/overlap`).** "omit labels which cannot be placed without overlapping other labels". Readings: text boxes (advance x ascent+descent), rotated boxes, or the drawn ink. Implemented: the drawn pixels (glyphs plus font outline plus Dot), alpha above 0.02, no extra margin. Boxes would reject more labels.

**C17. Priority (`/req/labels/placement`).** "a label with a higher `priority` is placed in preference". The source also carries `// TODO(review): confirm that a higher priority value means a higher priority (see #148)`. I took higher number = placed first (case 20: `priority: elevation`; case 21: `0 - elevation` places the low mountains first). Default priority 0 (not stated). Ties: layer order then file order ("Which of two conflicting labels of the same priority is left out may differ").

**C18. Label element positions (`/req/vector/graphics` vs `/req/labels/line`) - contradiction.** `/req/vector/graphics`: "a positive `y` as an offset downwards on the map". `/req/labels/line`: "its `y` perpendicular to the line, positive towards the top of the label". I applied the first for markers and for labels on points (`position: 0 -8` in cases 19-21 moves the text up 8 px) and the second for labels along lines (no case uses a nonzero `y` there).

**C19. Text alignment and metrics (`/req/vector/text`).** "`top` the top of the font's ascent, `bottom` the bottom of its descent, and `middle` the point halfway between them", "`left` puts the start of the text there". Open: which ascent/descent (typographic font metrics vs ink of this string), and what the start means (advance origin vs ink). Implemented: the font file's ascent and descent as reported by FreeType at the render size, the start of the advance box. For Arial that is 0.905 em above and 0.212 em below the baseline, so `middle` sits 0.35 em above the baseline, a little higher than the centre of lowercase letters. Another renderer using cap-height or the string's ink box would put the text a couple of pixels differently. The default alignment `left top` applies where none is set (case 33).

**C20. Font size meaning (`/req/vector/fonts`).** "a uom-qualified `size`". I treat it as the em size (the Pillow/FreeType nominal size), so Arial 12.6 px has an ascent of 11.4 px. Another reading is the line height or the cap height. I also use the real bold / italic Arial files (arialbd, ariali) for `bold` / `italic`. Hinting and anti-aliasing are my own (supersampled, unhinted).

**C21. Font table vs use (contradiction / undefined).** The Font class table lists only `face`, `size`, `bold`, `italic`, but the UML and the cases use `font.color` and `font.opacity` (and `outline`); `underline` is in the UML but nowhere defined. I used `color` (default black, not stated anywhere) and `opacity` (default 1). Font inheritance (`/req/vector/font-inheritance`) is implemented per property from the Text, the MultiGraphic, the symbolizer, then default 16 px. Also the text alignment is named `horizontal`/`vertical` in the UML, `horzAlignment`/`vertAlignment` in the table and `["left","top"]` in the JSON; I accept the JSON form.

**C22. Font outline (`/req/font-outlines/*`).** "outline extending outward from the glyph contours by the thickness specified by the `size` property, in pixels", "beneath the glyphs themselves", "opacity specified by the `opacity` property". Open: the join style of the grown contour (round, mitre), whether `size` is the offset or the stroke width (centred stroke would reach `size`/2), and what happens in the overlap with the glyph if the glyph is translucent. Implemented: FreeType's round-join stroker, grown outward by `size` px from the contour (size 2 = 2 px on each side; 3.5 = 3.5 px, measured at 4x so 14 supersamples), the outline drawn first at its own opacity (0.3, 0.6, 1 in cases 07-09), the glyph on top at its own opacity. The outline mask includes the glyph interior, so with opaque glyphs the interior is invisible. Default outline colour (not given anywhere) black, default opacity 1. In cases 04-06, 11 and 13 the only difference is `color` (white, #f3e7b8, #e8a090); 11 and 13 are identical styles (size 2, white) and the images are identical.

**C23. Image drawing (`/req/vector/image`).** (a) `size: 10 mm` as a single value: "a single value sets both" so a 35.7 x 35.7 px square (the source is 24 x 24, so the aspect ratio is not an issue here). (b) No `size`: "its own size, one pixel of the image to one pixel of the map": 24 x 24 px. (c) `hotSpot: 50 pc 100 pc` is the bottom-centre of the image on the point; `0 0` is the top-left corner at the point (case 31, image hangs down-right). (d) Resampling method not stated: I upscale premultiplied RGBA with bicubic filtering at 4x, then box-downsample. (e) Recolouring `tint x v + blackTint x (1 - v)` in sRGB (the linear-light permission not taken), with `tint` white (default); the icon is black, so the result is `blackTint` where the alpha says "ink". Alpha is untouched. (f) `alphaThreshold` is ignored (stated: "no Renderer requirement applies to it"; I did not use the permission). (g) The `uri`/`path` choice: I read `path` relative to the case folder, and never `uri`. (h) The SVG icons are not drawn (no SVG rasteriser was written); they are only used when `viz.sd < 10000` in case 01, whose scale is 50000, so no image is affected.

**C24. Placement of graphics on lines and polygons (`/req/vector/marker`).** "at the points of vector geometry (for points and line strings) and at the centroid of polygons". I take "points" of a line string as its vertices (as the Core note says) and the polygon centroid as the area centroid of the exterior ring (which can fall outside a concave polygon). Not exercised by any case at the given scales.

**C25. Expression evaluation (core, parameter values).** (a) System identifiers: the JSON uses `dataLayer.id`, `viz.sd`, `viz.timeInterval.start.date`; the spec text defines `dataLayer.identifier`, `visualization.scaleDenominator`, `visualization.timeInterval` (a `TimeInterval` of `TimeInstant`s whose `date` is a `Date` class with year/month/day). I treated `id`, `viz` and `sd` as aliases, which the text only hints at ("viz.sd" appears in examples, never defined). (b) `validDate >= viz.timeInterval.start.date`: the property is an ISO string and the identifier a `Date`; no text defines comparing a string with a Date. I compared ISO strings (same order as dates). (c) `dataLayer.featuresGeometryDimension`: "(if same for all features)", computed from the file's geometry types. For coverage layers I give it `null`. (d) `concatenate('Road ', number)`: `concatenate` takes `(string a, string b)` but `number` is an integer; no conversion is defined. I convert numbers to text without a decimal point ("Road 2614"). (e) Comparison of two values of different types (e.g. string vs number) returns NULL (unknown, so not selected). (f) A rule's selector that evaluates to NULL does not select ("A `selector` evaluating to null does not evaluate to true"). (g) `visualization.pass` is 1: the text never says what the pass is when only one pass is drawn. (h) Coverage cells: selectors that depend on cell values are not evaluated per cell; the rule selector is evaluated once per layer with empty properties (none of the cases needs per-cell selection).

**C26. Layers in the view not drawn by a rule.** `/req/core/symbolizer`: data no rule selects is drawn "with the default values". So a layer with no matching rule would be drawn with a white fill, a black 1 px stroke, and the default Dot. Layers here are all matched by their `dataLayer.id` rule; features hidden by `visibility: false`.

**C27. Label elements that are not Text (cases 18).** A Dot in a label on a line: drawn at its `x` along the line (here 0) with no turning needed.

**C28. Label for point features with `minSpacing`.** Implemented the same repetition rule (same layer and same text, straight-line distance), though no case uses it on points.

## Contradictory or used-but-undefined items (summary)

- C18: `y` positive down in `/req/vector/graphics`, positive towards the top in `/req/labels/line`.
- C21: Font properties used in the data (`color`, `opacity`, `outline`) are missing from the Font table; default colour undefined; alignment property names differ between UML, table and JSON.
- C25: `id`, `viz`, `sd` aliases in the JSON are not defined in the system identifier table; `dataLayer.featuresGeometryDimension` is defined for vector only; `Date` vs ISO string comparison.
- Colours: Color r, g, b are 0..255 in the examples (`Color(255, 100, 50)`), but `colorChannels` "each in the range 0 to 1" (the source has a TODO about it, #150) and the default `colorChannels` takes the raw first three fields. Not exercised (only `colorMap` and `singleChannel` are used).
- ValueColor has `label` in the UML and `name` in the table.
- `Text` in the core table: "alignment ... default `left` `top`" vs the TextAlignment table with `horzAlignment`/`vertAlignment`.
- The recommendation `/rec/core/opacity-together` and the requirement `/req/core/opacity` give different pixels (C10).
- `/req/vector/stroke` last part, "strokes of all features with the same `zOrder` on top of the fills of all those features", combined with a per-feature opacity: with opacities below 1 the visible result depends on whether strokes of neighbouring polygons draw over each other (shared borders are drawn twice, so a shared border looks darker than an outer border).
- `/req/labels/placement`: "all labels with the same content from the same data layer" are repetitions even if they are different features with no road in common (then two roads with the same number count as repetitions of one label for the spacing rule).
- Annex C and the CSS examples use `marker.elements[1]` where the JSON clause says zero-based (C8).
- The hill-shading text says shade 1 is "no shade", but flat terrain then renders at 0.707 (C5).

## Not implemented

SVG images (C23h); `colorChannels`, `alphaChannel`, `opacityMap`; hill shading `colorMap`/`opacityMap`; dashes, casing, hatches, stipples (no case uses them; clauses 11 and 12 not implemented); coverage rasters coarser than the map pixel (would need overviews; not needed since 28 m = 28 m); per-cell selectors; variables, functions other than `concatenate`; `$include`; CQL2 functions other than the operators listed in `apply_op`.

## Table of cases

Pixel sizes: 1 pt = 0.3528 mm = 1.26 px; 1 mm = 3.571 px. Label/marker text is Arial. Scale given as the denominator. "Outline" is the font outline. Rendering is at 4x supersampling.

| Case | What the renderer draws |
|---|---|
| 01 | 1:50000, 440x300. 58 polygons of Landcover by class (bog #cbb867, forest #4f8a45, lake #6fa3cc, other #d6cfbd) with fill opacity 0.5 x 0.8 = 0.4, stroke 0.75 px at 0.8 opacity. No markers or text (needs sd < 10000). |
| 02 | 1:100000. Roads except class `path`: 1 px #8c8172 for others, municipal 2.5 px, county 3.5 px, national 4.5 px, european 5.5 px, by zOrder 2-6; round caps. No dots (needs sd < 10000). |
| 03 | 1:50000. Three huts as 7 px dots #b8322a at opacity 0.9. No text (sd >= 5000). |
| 04 | 1:100000, 300x200. Elevation: 28 m cells coloured by the 3-stop map, hill shaded (factor 2, sun 315/45). Labels of the 3 mountains >= 2000 m (Rondslottet, Storronden, Vinjeronden), Arial 10 pt = 12.6 px, centred, #2b2b2b, outline 2 px white. |
| 05 | As 04, outline 2 px #f3e7b8. |
| 06 | As 04, outline 2 px #e8a090. |
| 07 | As 04, outline 2 px white at opacity 0.3. |
| 08 | As 04, outline 2 px white at opacity 0.6. |
| 09 | As 04, outline 2 px white at opacity 1. |
| 10 | As 04, no outline. |
| 11 | As 04, outline 2 px white (same as 13). |
| 12 | As 04, outline 1 px white. |
| 13 | As 04, outline 2 px white (same as 11). |
| 14 | As 04, outline 3.5 px white. |
| 15 | 1:25000, 300x200. Lake polygons #a9cbe3 (zOrder 2, no stroke). Names of ponds/lakes as Text markers, Arial italic 9 pt = 11.34 px, #1f4e79, centred, drawn at zOrder 1 so lakes cover parts of them. |
| 16 | As 15 but the names are labels (drawn on top, collision tested): 8 of 8 placed. |
| 17 | 1:50000. Roads of class european/national/county: 2 px #d0483a. Labels "Road N" along the line, Arial bold 8 px #b8322a, left middle at x = 7 px, outline 2 px white, minSpacing 150 px: 2 labels (one per road). |
| 18 | As 17 plus a 7 px dot #b8322a at the label anchor (the text then starts after the dot): 2 labels. |
| 19 | 1:250000. 36 mountains as 3 px dots #b8322a plus a label (Arial 9 pt = 11.34 px, centred, 8 px above the point, no priority): 21 placed, clipped at the map edge where cut. |
| 20 | As 19 with `priority: elevation` (highest mountain first): 20 placed. |
| 21 | As 19 with `priority: 0 - elevation` (lowest first): 21 placed. |
| 22 | 1:50000. Roads as in 17; label is the road number only, Arial bold 8 pt = 10.08 px #b8322a, centred, outline 2 px white, minSpacing 80 px: 6 labels (4 candidate features, joined into roads where they meet, repeated along them). |
| 23 | As 22 with minSpacing 150 px: 2 labels. |
| 24 | As 22 with minSpacing 300 px: 2 labels. |
| 25 | 1:38000. 5 mountains: 4 px dots #b8322a and Text markers (not labels): Arial 9 pt = 11.34 px, `center bottom`, 4 px above the point. |
| 26 | As 25 with Arial 12 pt = 15.12 px. |
| 27 | As 25 with Arial bold 9 pt. |
| 28 | As 25 with Arial italic 9 pt. |
| 29 | 1:10000, 300x200. Two huts: `hut.png` at its own size (24 x 24 px), hot spot bottom centre, black recoloured to #b8322a, plus a 5 px dot #1f4e79 on top. |
| 30 | As 29 with size 10 mm = 35.7 x 35.7 px. |
| 31 | As 30 with hot spot 0 0 (the icon hangs down and right of the point). |
| 32 | As 30 with blackTint #3a7d44. |
| 33 | 1:52000. 6 mountains: 4 px dots and Text markers with the default alignment `left top` (text starts at the point and hangs below it), Arial 9 pt = 11.34 px. |
| 34 | As 33 with `center middle` (text centred on the point, over the dot). |
| 35 | As 33 with `right bottom` (text ends at the point, above it). |
| 36 | As 33 with `center bottom` (text centred above the point, bottom of the descent on the point). |

## Files read outside this folder

none

(The renderer loads `arial.ttf`, `arialbd.ttf`, `ariali.ttf` and `arialbi.ttf` from the Windows font folder, which the task allowed: "The system fonts of this machine (Windows) are available".)
