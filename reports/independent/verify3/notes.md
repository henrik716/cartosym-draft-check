# Notes on the draft text (OGC CartoSym 2.0 Part 1, spec/1-core)

Each entry gives the identifier (requirement, clause or table), the words that leave the choice open, the readings considered, and the reading implemented in `renderer/render.py`. Section 4 lists contradictions and undefined items. Requirement identifiers are written as in the text.

## 1. Frame, units and colours

**N1. Pixel size and units** (clause 8 "Graphical Units of Measure", clause 17 units table, `/req/vector/units`).
Words: "The portrayal unit pixel is the default unit of measure. ... otherwise it is equal to 0.28mm x 0.28mm"; clause 17: "points | pt | One point is equal to 1/72 inch".
Considered: a client-dependent pixel (not available here), or the fixed 0.28 mm the view files give.
Implemented: 1 px = 0.28 mm (the view's `pixelSize_mm`); 1 pt = 1/72 in = 1.2599 px; metres and feet are converted with the scale denominator (metres per pixel = scaleDenominator x 0.28 mm, checked against the bbox); `em` = font size.

**N2. Font size unit** (clause 8 Font class "Size of the font (pt)", `/req/vector/fonts` "a `size` specified in _points_").
Words: Font `size` is "float" with no unit in the JSON schema.
Implemented: unitless font size = points (1/72 in). Alternative (pixels) rejected: the text says points in two places.
Undefined: the default face, size and colour of a Font. Implemented Arial, 10 pt, black. Not used by the cases except in Text graphics that give their own font.

**N3. Bare numbers** (clause 8 "The portrayal unit pixel is the default unit of measure" vs `/req/vector/image` "a number without a unit is a fraction of the image's width or height").
Implemented: a bare number is pixels for lengths and a fraction only for an Image `hotSpot` (see N24).

**N4. Colour range** (clause 7 and 8 Color class "r, g, b ... float"; `/req/coverage/color-channels` "each in the range 0 to 1"; JSON schema `colorComponent0to255` for `color`, `color0to1` for `colorChannels`; case files use `[224, 160, 48]`).
Considered: 0 to 1 floats for all Colors (the model text), or 0 to 255 integers for the encoding (schema, cases).
Implemented: 0 to 255 for `color` (arrays and r/g/b objects), 0 to 1 for `colorChannels`. No case uses `colorChannels`, so it is not implemented beyond parsing.

**N5. Colour names and hex** (clause 17 "Named web color enumeration"; "Colors can also be expressed as a hexadecimal value prefixed by a `#`").
Words: the JSON schema has no hex form, but the coverage cases use `"#8a7a5a"` in `colorMap`.
Implemented: named colours use the table in clause 17 (147 names, matched case-insensitively, so `lightGoldenRodYellow` and `fuschia` as spelled in the schema enum still match); hex is accepted as an extension.

**N6. Null values** (`/req/parameter-values/null` table).
Implemented as the table says: numeric null is 0, boolean null is false, Color null is black, enumeration null is the default, Marker or Label null is no graphics. A Color null inside an object also gives black.

## 2. Rules, defaults and merging

**N7. Object replacement or partial update** (`/req/core/instances`: "overriding a single member of an object Symbolizer property without replacing the other members"; `/req/json/partial-update`).
Words: a Symbolizer "may either set an object property with a complete new instance, or specifically override a particular member".
Implemented: `alter: true` merges members; an object without `alter` replaces the earlier object and its missing members take defaults (not the earlier member values). Thus in `core-instances` the nested `stroke` without `alter` would drop the width; the case uses `alter: true` for that reason.

**N8. Array element update** (`/req/json/array-element-update`).
Implemented: `{index, value}` replaces that element; the value is a complete new element. An index equal to the length appends (not in the text).

**N9. Features that no rule selects** (`/req/core/symbolizer`: "portraying, with the default values, the features and coverage cells that no StylingRule selects, so that a style hides data only by setting `visibility` to false").
Implemented literally. Effect in `core-opacity`: the polygons that are not lakes get the default Fill (white), the default Stroke (black 1 px) and the default Marker (white 10 px Dot at the centroid, invisible on the white background but present). A coverage layer with no `singleChannel` draws nothing (no default is given for coverage).

**N10. Default Marker** (clause 7 NOTE: "A style that sets no marker therefore draws a Dot at each point, at each vertex of a line and at the centroid of each polygon").
Implemented: absent `marker` gives one 10 px white Dot per anchor; `marker: null` or `elements: []` gives none; `marker: {}` gives the default Dot (per the NOTE).

**N11. Visibility** (`/req/core/visibility`; table: null boolean is false). Implemented: absent means true; any value other than true means not portrayed.

**N12. Selector results** (`/req/core/selector` NOTE: "A `selector` evaluating to null does not evaluate to true"). Implemented: selector selects only when its value is exactly true.

**N13. Expression semantics** (clause 7 operations: "A Renderer SHALL support evaluating operation expressions with a null operand as specified by CQL2").
Implemented: three-valued `and`/`or`/`not`; comparisons with null give null; comparisons between different types (for example a string and a number) give null; ISO date strings compare as strings (see N40); an unknown operator gives null (not in the text).

**N14. Identifier names** (clause 7 "Visualization System Identifiers", "Layer System Identifiers"; clause 8 table; JSON schema `systemIdentifier` enum; cases).
Words: the spec text says `visualization.*`, `dataLayer.identifier`, `feature.identifier`, `feature.geometryDimension`, `dataLayer.featuresGeometryDimension`; the schema and cases say `viz.*`, `dataLayer.id`, `feature.id`, `feature.geometryDimensions`, `dataLayer.featuresGeometryDimensions`.
Implemented: the schema and case names (the cases must run); the spec names were not separately implemented.

**N15. Right-hand operands** (`/req/right-hand/operands` is a separate requirements class, but `core-time` compares `validDate` with `viz.timeInterval.start.date`). Implemented without a check; the core class alone does not say this is allowed.

**N16. Parameter values in the core class** (clause 7 "Without a requirements class specifying otherwise, only Literal Expressions ... are allowed").
Words: `core-parameters`, `labels-priority` (priority), `vector-text` and others use property expressions for sizes and text.
Implemented: all expressions are evaluated. Conformance class of these cases is therefore parameter-values (or more), not core only.

## 3. Vector geometry and symbolizers

**N17. Marker anchors** (`/req/vector/marker` "at the points of vector geometry (for points and line strings) and at the centroid of polygons"; clause 7 NOTE "at each vertex of a line").
Implemented: each vertex of a line (not only the ends); the area centroid of each polygon, or of the whole MultiPolygon.

**N18. Order of drawing within a feature.** Undefined. Implemented: fill (or hatch, dot pattern, stipple), then stroke, then markers, as one group when opacity is below 1.

**N19. Polygon holes.** Undefined. Implemented: even-odd fill rule over all rings.

**N20. Line ends and joins.** Clause 8: "By default the end of open subpaths are butt caped and at the corners of paths are miter joined". Implemented: butt caps and miter joins; the miter limit is not stated (the Cairo default of 10 is used).

**N21. Dot size and colour** (`/req/vector/dot` "a `size` property and a `color` property that are the same values as the `width` and the `color` of its stroke"; `/req/json/dot-size-color` NOTE "The members of a JSON object have no order (RFC 8259), so within one styling rule there is no last value").
Implemented: `size` wins when both `size` and `stroke.width` are given (the producer rule says not to set both). A Dot with an outline (two concentric Dots, per the NOTE in clause 8) is not implemented: no case uses a Dot stroke.

**N22. Image resource and size** (`/req/vector/image`; clause 8 Resource class "url", "path (preferably relative) path to local file"; schema `uri`).
Implemented: `path` only, relative to the folder of the style file (so `../icons/hut.png` resolves to `cases/icons/`). `uri` and `url` are not fetched. The Image has no size property, so the image is drawn at its own pixel size (1 image pixel = 1 device pixel). `alphaThreshold` is not used (it is a MAY permission).

**N23. Graphic position direction** (`/req/vector/graphics`: "a positive `x` ... an offset to the right and a positive `y` as an offset upwards on the map, as for `Displacement` in SE 1.1"). Implemented literally: a positive `y` moves the graphic up (device y decreases). This is the reverse of the Image `hotSpot`, which is measured downwards (N24).

**N24. Image hotSpot** (`/req/vector/image`: "its `hotSpot` ... in the coordinates of the image, from its top left corner with `x` to the right and `y` downwards, where a number without a unit is a fraction of the image's width or height, a value in `pc` is a percentage of it, and a value in another unit is a length from that corner").
Implemented: origin at the top left corner; x right, y down; a bare number is a fraction (0.5 is the centre); `pc` is a percentage; other units are lengths in pixels after conversion. The case `[{pc:50},{pc:100}]` puts the bottom centre on the point.

**N25. Text alignment** (`/req/vector/text`: "`top` the top of the font's ascent, `bottom` the bottom of its descent, and `middle` the point halfway between them").
Implemented with the font's ascent and descent from Cairo's font metrics at the given size. Halfway means the midpoint of the ascent top and the descent bottom. `left` puts the start of the advance width at the point; `right` the end; `center` the middle of it.

**N26. Text of numbers.** Undefined how a numeric property becomes text (`elevation` 2100.0 is printed "2100"; non-integer values use Python's str). Used in `vector-text`.

**N27. Text graphics and overlap.** Undefined whether Text graphics in a marker are subject to overlap avoidance. Implemented: no (only labels are placed with overlap avoidance, `/rec/labels/overlap`). Visible in `vector-text`, where names overlap.

**N28. Font outlines** (`/req/font-outlines/size` "drawing the outline extending outward from the glyph contours by the thickness specified by the `size` property, in pixels").
Implemented: size in pixels. A stroke of width 2 x size is drawn under the glyphs, so the visible outward extension is `size` px. The alternative (a stroke of width size centred on the contour, extension size/2) is rejected because the text says "extending outward ... by the thickness".

## 4. Opacity, casing, centre lines, dashes and z-order

**N29. Opacity together** (`/rec/core/opacity-together`: "apply the Symbolizer `opacity` to the fill, the stroke and the graphics of markers of each feature together"). Implemented: a feature group (fill, stroke and markers) composited once at the symbolizer opacity. Casing and centre lines are separate groups; the text does not say whether they belong to the feature group.

**N30. Casings and centre lines** (`/req/casing/casing`: "drawing, within a single visualization pass, the casings of all features with the same `zOrder` beneath the main strokes of all those features"; `/req/casing/center`: "the center lines of all features with the same `zOrder` on top of the main strokes of all those features").
Implemented (6): for each zOrder value in ascending order, first the casings of all its features, then the main symbolizers (fill, stroke, markers) feature by feature in layer and file order, then the centre lines of all its features. This satisfies both sentences; a per-feature order (casing, stroke, centre) is rejected because of "all those features".
Undefined: the order of features with equal zOrder across layers (I used layer order, then file order).
A zero-width main stroke still gets its casing (total width = 2 x casing width); the text does not say.

**N31. Casing and centre names** (`/req/casing/center`; TODO #120 notes the schema calls it `centerLine`). Implemented: both `center` and `centerLine` are read.

**N32. Dash offset** (`/req/dashes/dash-offset`: "as the distance into the dash pattern at which dashing starts at the beginning of each line (as `stroke-dashoffset` in SVG and SE 1.1), in the units of the dash pattern"). (2)
Implemented: the offset is the distance into the pattern at which the pattern starts at the first point of each line; the pattern continues across vertices and restarts at the start of each line part (Cairo `set_dash(list, offset)`, one path per line part). The JSON schema has no `dashOffset` property although the requirement says "SHALL support defining a dashOffset property"; the case uses it anyway, and it was read from the case.

**N33. Dash lengths** (`/req/dashes/dash-pattern`: "lengths are in pixels unless qualified with another unit"). Implemented: units converted as in N1. An all-zero pattern gives a solid line.

**N34. Z-order tie-break.** (`/req/core/z-order`: "features and coverage cells of a single rendering pass in increasing order of their resolved `zOrder`"). Undefined for equal zOrder. Implemented: view layer order, then feature order in the file. Coverage layers take part in the same ordering.

## 5. Coverage and hill shading

**N35. Coverage cell to pixel mapping (3)** (`/req/coverage/single-channel`: "portraying each coverage cell over the whole area of that cell, so that each pixel of the map whose center lies in a cell takes the color and opacity of that cell"; `/req/hill-shading/hill-shading`: "the coverage resampled to the map's resolution where the map's resolution is coarser").
Implemented: each pixel centre is mapped to the cell containing it (floor of the offset from the lower-left corner). When the map pixel is as large as or larger than a cell (`mpp > cellsize`), the coverage is first resampled to the map's pixels by nearest cell, and the resampled grid is then used. The interpolation method is not given, so nearest is used; bilinear was rejected because the text says the cell is painted over its whole area.

**N36. Hill-shading samples (3)** (`/req/hill-shading/hill-shading`: "using as samples the cells of the elevation coverage where the map's resolution is as fine as the coverage's or finer, and the coverage resampled to the map's resolution where the map's resolution is coarser, and taking for each direction the difference between the two samples on either side of the cell over twice the distance between samples (repeating the edge sample at the edge of the coverage)").
Implemented: where the map is as fine as or finer than the coverage (`mpp <= cellsize`), the samples are the cells and the distance is the cell size; where the map is coarser (`mpp > cellsize`), the samples are the resampled map pixels and the distance is the pixel size (in `hill-shading-sun` the map is 75 m per pixel and the cells are 150 m, so this is the coarse case; in `font-outlines` the map is 28 m per pixel and the samples are the cells). The slope is taken over the two neighbouring samples (distance 2 x sample spacing), with the edge sample repeated. Each pixel takes the shade of its sample.
Undefined: whether the slope should use the resampled grid or the cells in the coarse case; the text says the resampled grid.

**N37. Hill-shading surface normal and sun** (`/req/hill-shading/factor`: "multiplying the horizontal components of the terrain surface normal by the `factor` ... before normalizing"; `/req/hill-shading/sun`: "azimuth ... in degrees clockwise from North, as a compass bearing" and "elevation angle (relative to the ground)").
Implemented: normal = normalize(-factor x dz/dE, -factor x dz/dN, 1); sun vector = (cos(el) sin(az), cos(el) cos(az), sin(el)); shade = clamp(dot, 0, 1). The sun default (no value is given in the text) is azimuth 315, elevation 45; no case omits it.

**N38. Colour map interpolation** (`/rec/coverage/map-interpolation`, a NOTE: "The interpolation method is not specified"). Implemented: linear between the two closest entries; values outside the range take the first or last entry. An exact entry value gives that entry's colour.

**N39. Multiplying a colour map by a hill shade** (`/req/hill-shading/hill-shading`: "where the HillShading has no `colorMap`, multiplying the red, green and blue components of each cell by its shade value"). Implemented: the symbolizer `colorMap` gives the base colour and the shade multiplies it (as the case comment says). If `hillShading.colorMap` exists, the shade is mapped through it instead. `hillShading.opacityMap` is applied to the shade.

**N40. Coverage NODATA** (the ESRI header `NODATA_value -9999`; no requirement mentions NODATA). Implemented: NODATA cells are transparent. No cell in the cases has that value.

**N41. Coverage selectors.** `/req/core/selector` applies rules "to a feature or coverage cell". Implemented: coverage selectors are evaluated per layer only (no cell properties). A selector that names a band therefore evaluates to null and does not select. No case needs this. `colorChannels` and `alphaChannel` are not implemented.

**N42. Time comparisons** (`/req/core/time`: a Date value; the case compares a `validDate` string). Implemented: ISO date strings compare as strings, which orders them correctly for `YYYY-MM-DD`.

## 6. Hatch fills (9)

**N43. Hatch colour and opacity** (`/req/hatches/hatch`: "drawn in the `color` and `opacity` of the Fill, without painting the area between the lines"). Implemented: the Fill colour and opacity; no solid fill is drawn when a hatch, dot pattern or stipple is present.

**N44. Hatch angle reference and direction** (table in `rc-hatches`: "0 gives horizontal lines and angles turn counter-clockwise as seen on the map"; TODO #146 says the table was changed from clockwise to follow the figure). Implemented: 0 is horizontal, angles increase counter-clockwise on the map (45 rises to the right, 90 is vertical). This is the table's current wording.

**N45. Hatch phase** (`/req/hatches/hatch`: "placing the hatch lines of all features on one pattern aligned with the map, with a line through the top left corner of the map"). Implemented: the lines are at signed perpendicular distances k x distance from the top left corner; k = 0 is the line through the corner. Distance is measured across the lines (the table) between the centres; width is the line thickness in pixels, centred on each line.

**N46. Hatch defaults.** The text gives none; the figure caption "(width : 1 px, angle : 45 °, distance : 10 px)" does. Implemented as defaults if absent (no case omits them).

## 7. Stipples and dot patterns (5)

**N47. Stipple dots** (`/req/stipples/ratio`: "dots in the `color` and `opacity` of the Fill placed at random so that they cover the `ratio` fraction of the area"; NOTE: "The size of the dots and their placement are left to the Renderer"; TODO #84 "define the size of the stipple dots").
Implemented: 2 px diameter (radius 1, the size of the dot pattern requirement, which is the only size given), uniform random positions inside the polygon (seed = layer index and feature index, so the run is repeatable), placed until the number of polygon pixel centres they cover reaches `ratio` of the polygon's pixel count (overlaps counted once). The alternative (number of dots = ratio x area / dot area) is rejected because overlap would make the coverage less than the ratio.

**N48. Dot pattern grid** (`/req/dot-patterns/dotpattern`: "a regular grid of points ... each drawn as a filled circle with a diameter of 2 pixels in the `color` and `opacity` of the Fill ... with its first point half the horizontal and half the vertical distance from the top left corner of the map"). Implemented literally, for all features on one grid, clipped to the polygon.

## 8. Labels (4), (7), (8)

**N49. Labels partly outside the map (4)** (`/rec/labels/overlap`: "A Renderer SHOULD omit labels which would extend beyond the edges of the map, except where the map is drawn in tiles that are put together").
Implemented: a label whose whole box does not lie inside the map is omitted (for that candidate position; repetitions along a line may still be placed elsewhere). The alternative (clipping) is not in the text.

**N50. Label overlap** (`/rec/labels/overlap`: "A Renderer SHOULD omit labels which cannot be placed without overlapping other labels, unless a property of the Symbolizer allows the overlap"). No such Symbolizer property is defined.
Implemented: greedy placement; a label box (advance width by ascent plus descent, grown by the outline size) must not overlap any placed label box. Labels are not checked against markers or Text graphics.

**N51. Label priority** (`/req/labels/placement`: "a renderer SHALL support placing labels so that a label with a higher `priority` is placed in preference to a conflicting label with a lower `priority`"; TODO #148 asks whether higher means higher).
Implemented: higher is preferred, as the text says. Priority absent gives 0 (LabelPlacement defaults are not given). Ties are broken by layer order, then feature order.

**N52. Label repetition along lines (7)** (`/req/labels/placement`: "repeating a label so that the distance between repetitions of that label is at least `minSpacing` and, where space allows, at most `maxSpacing`, both in pixels unless qualified ... measuring the distance between repetitions on the map between their positions"; "treating as repetitions of a label all labels with the same content from the same data layer").
Implemented: repetitions are grouped by (data layer, text content). For each line, positions are tried every 1 px from its first vertex; a position is accepted if its straight-line distance to every accepted repetition in the group is at least `minSpacing`, the label box lies in the map and it does not overlap a placed label. `maxSpacing` has no default and is not applied (no upper limit). The label text is not rotated (no rotation property is defined).
Alternatives rejected: even spacing from the line midpoint (not in the text); each feature separately (the text says same content from the same layer counts as one).

**N53. Label anchors** (undefined for polygons and lines). Implemented: a point label at the point; a polygon label at the centroid; a line label without `minSpacing` at the midpoint of the line's length (not used by these cases).

**N54. Label pass and opacity.** `/req/labels/label` draws labels "as a separate pass on top of all styled vector features and coverages". Implemented: after all zOrder values. The NOTE says the symbolizer opacity does not apply to labels; implemented that way.

## 9. Visualization frame and other

**N55. Pixel frame.** The bbox, width, height and scale of each view agree with 0.28 mm per pixel (checked by assertion in the renderer). No requirement says what to do if they disagree.

**N56. Image defaults.** Image `tint` white and `blackTint` black are clause 7 defaults (the image is drawn unchanged), applied as in `/req/vector/image` ("tint x v + blackTint x (1 - v)").

**N57. Renderer outside the stated classes.** Not implemented, since no case uses them: `colorChannels`, `alphaChannel`, Dot outlines, `feature.pass`, `visualization.pass`, `alphaThreshold` picking, vendor extensions, `dataLayer.features`.

## 10. Contradictions and undefined items

**C1. Hatch angle direction.** The table says counter-clockwise (current), TODO #146 says the table was changed from clockwise to match the figure. Only the table's text was used.

**C2. Unit names.** Clause 8 lists pixel, millimeter, inch, percentage, meter and foot in the requirement, and pixels, meters, feet, percent, points, em, screenInches, screenCM, screenMM in the enumeration. Clause 17 abbreviates to px, m, ft, pc, pt, em, inch, cm, mm, and calls `pc` percent (though it also cites CSS, where `pc` is picas). The JSON schema uses px, mm, cm, in, pt, em, pc, m, ft. The cases use px, mm, m, pc (percent in `hotSpot`), and the schema names were used.

**C3. Color range.** Clause 7 and 8 say r, g, b are floats; the schema and cases use integers 0 to 255 for `color` and 0 to 1 for `colorChannels`; `/req/coverage/color-channels` says 0 to 1 for the cell colour. Both were used as N4 describes.

**C4. Default colour channels.** Clause 7 TODO(review): the default `colorChannels` "uses the first three fields unscaled, while `colorChannels` is 0 to 1 (see #150)". Not used.

**C5. System identifier names.** `dataLayer.identifier` (spec), `dataLayer.id` (schema, cases); `visualization.*` (spec), `viz.*` (schema, cases); `feature.identifier`/`feature.id`; `feature.geometryDimension`/`feature.geometryDimensions`; `dataLayer.featuresGeometryDimension`/`...Dimensions`. The clause 7 NOTE uses `dataLayer.featuresGeometryDimensions`, which is defined only in the vector class with the singular name.

**C6. `notLike` missing from the schema.** TODO #140. The text defines `notLike` in `/req/text-relation/not-like` and the schema has no `notLike`. Not used.

**C7. `center` versus `centerLine`.** TODO #120 (N31).

**C8. `dashOffset` missing from the schema.** The requirement `/req/dashes/dash-offset` says "SHALL support defining a dashOffset property", but the schema's `stroke` has `dashPattern` only (N32).

**C9. Image `uri` versus `url`.** The schema has `uri`, the spec `url` (N22).

**C10. Label priority direction.** TODO #148 (N51).

**C11. Stipple dot size.** TODO #84 (N47). The dot-pattern requirement's size and colour are defined; the stipple's are not.

**C12. Hill-shading colour map.** The schema's `hillShading.colorMap` items have one prefix item (a zero-to-one value), not a `ValueColor` (value and colour). Not used; the spec's `ValueColor` was used.

**C13. Hill-shading sun defaults.** `sun`, `azimuth`, `elevation` have multiplicity 0..1 and no default. Implemented 315 and 45 (N37).

**C14. Hatch and pattern defaults.** The text gives none; the figure caption does (N46).

**C15. Dot size and stroke width.** Two members of the same Dot; the text says the last one set wins, but JSON members have no order (N21).

**C16. Parameter values in the core class.** Clause 7 says only literals are allowed without the parameter-values class, while the cases use expressions for Dot size, label priority and the Text content (N16). The core-only case `core-parameters` is therefore not core-only.

**C17. Right-hand operands in the core class.** `core-time` compares with an identifier on the right, which the core text does not allow without the right-hand class (N15).

**C18. Pass-based rendering.** Clause 7 says a visualization pass starts "only after all data layers and their features ... have been rendered with the symbolizers set for earlier visualization passes". No case uses passes; the renderer draws one pass.

**C19. Text font metrics.** `top` is "the top of the font's ascent" and `bottom` "the bottom of its descent", but the text gives no source for these metrics (N25).

**C20. Coverage NODATA.** Not defined in the text (N40).

**C21. Figures and example references.** The text refers to figures (for example `figures/hatches_default.png`, not included) and to "example 11" and `fig-example-*` items that are not in this folder. Used only where the caption gives a default (N46).

**C22. The default Marker is invisible on white.** The default Dot is white and the default background is white (N9, N10). It is drawn, but it cannot be seen in `core-opacity`; the text does not say whether defaults are meant to be visible.

**C23. Case count.** Twenty case folders, one of which (`vector-units`) has two views, so 21 images are rendered: `out/<case>-<N>.png` for each `view-N.json`.
