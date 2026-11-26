# Notes: independent renderer, CartoSym 2.0 Part 1 draft

Renderer: `renderer/render.py`. Outputs: `out/case-NN-1.png` (all 36 written, each at the view's width x height).
Libraries: numpy, Pillow, resvg-py (SVG rasterizer only; no CartoSym or SLD code).
Fonts: Arial from C:/Windows/Fonts. Supersampling x4, then box-filter downsampling.
Contact sheet used for my own check: `renderer/contact.png`. I did not compare against any reference image.

## Choices where the text leaves the drawing open

1. **Marker element index beyond the array (JSON `alter` with `index`, `/req/json`).** Text: "updating only the array element identified by index". Readings: (a) error, skip; (b) append. Chosen: append. Case 01 puts an Image at index 1 of a one-element marker, so it is appended. Case 03 is the same for index 2 with two elements.
2. **Default Marker and `marker: null`.** Table "Marker class default values" says a default Dot (10 px, white) applies to every feature. Chosen: absent marker means default Dot; `marker: null` means none; `{}` means default Dot; `elements: []` means none. Clause 7 note confirms this reading.
3. **Non-alter replacement of an object.** Text: "alter: true" preserves members. Chosen: an object without alter replaces the whole object, with defaults for missing members (for example `stroke: {width: 0}` in case 15 gives opacity 1, colour black).
4. **Markers on line strings.** Requirement says "points and line strings"; the note says a default Dot is drawn "at each vertex of a line". Chosen: vertices. No active rule places a marker on a line in these cases, so this is not exercised.
5. **Marker on polygons.** "centroid of polygons". Chosen: area-weighted centroid of the outer ring. Not exercised.
6. **Opacity of text and labels.** `/req/core/opacity` lists fill, stroke, graphics of markers and coverage cells, not text explicitly. Chosen: the symbolizer opacity multiplies text (a Text is a Graphic) and label text. Case 03 uses opacity 0.9 with Dots only, so it does not matter there.
7. **Priority of labels.** `/req/labels/placement` says a higher priority wins; the file has a TODO asking to confirm it (#148). Chosen: higher value wins. Cases 20 and 21 are the two readings with opposite inputs (elevation vs. negated elevation), so their outputs depend on this choice.
8. **Repetitions along lines (`minSpacing`).** Text: distance between repetitions "at least minSpacing", "where space allows, at most maxSpacing". No maxSpacing is given. Chosen: anchors at arc-length L/2 + k*minSpacing, each spacing measured between anchors; the label must lie wholly on the line (rec: omit if shorter). Overlap resolved greedily by priority, then by layer/creation order.
9. **Joining lines for labels.** Requirement says join lines "that have the same label and meet at their end points". Chosen: greedy chaining by exact endpoint match over features in the same layer with the same evaluated text; no true graph handling for branches.
10. **Label placement order and overlap.** Rec allows overlap omission "unless a property allows the overlap". Chosen: greedy by priority, box test by separating-axis test, boxes include outline width. Labels that would leave the map are omitted; the text leaves this to the renderer (NOTE under `/req/labels/placement`).
11. **Text along lines.** Chosen: each glyph is placed on the tangent at its arc position and rotated; reading direction is chosen so the text is never upside down (dx>0, or dx=0 with dy<0). The `y` offset is positive towards the top of the label.
12. **Text alignment vertical reference.** `top` = top of ascent, `bottom` = bottom of descent, `middle` = halfway between (Arial metrics from Pillow, ascent/descent from the font).
13. **Pixel size and ground units.** 1 px = 0.28 mm at the map scale, so 1 m = 1000 / (0.28 * scaleDenominator) px. `pt` = 1/72 in. A bare number in a font size is pixels (case 17).
14. **Font outlines.** Outline is a disk dilation of the glyph coverage by `size` px, drawn beneath the glyphs, in the outline colour and opacity. The text does not fix the shape; a disk is my reading.
15. **Dot.** Drawn as a filled disk of diameter `size`; the Dot's stroke is not separately drawn.
16. **Image hot spot.** `pc` is a percentage of the drawn size; a plain number is in image-file pixels scaled with the image (case 31: `[0, 0]`, top-left corner). Image size: an explicit `size` with one of x/y keeps the aspect ratio; a single value sets both. Default size: the file's own pixels, from the SVG width/height attributes for SVG.
17. **Tint and blackTint.** Each channel v of a pixel becomes tint*v + blackTint*(1-v), as in `/req/vector/image`. Alpha is kept.
18. **alphaThreshold.** Only a picking aid (`/per/vector/image-alpha-test` is a MAY). Not applied. Cases 01 use 0.1; no visible effect is intended.
19. **Coverage colour interpolation.** Linear in sRGB between colorMap entries (linear light is a MAY). Values outside the map take the first or last colour.
20. **Hill shading.** Gradients use the cell spacing (28 m); factor multiplies the horizontal normal components; sun azimuth is a compass bearing (clockwise from north), so azimuth 315 lights from the north-west. The map is north-up, so grid north equals map north. Shade multiplies the colour from colorMap (no colorMap in the hillShading object). Each map pixel takes the value of the cell containing its centre (nearest cell).
21. **Stroke width 0.** Nothing drawn. The stroke of a polygon is drawn after all fills of the same zOrder pass.
22. **Pass order.** Within one zOrder, in order: fills of all features, then strokes, then markers (`/req/vector/marker`). Labels are a separate pass after all features (`/req/labels/label`). Layers are not sorted by zOrder across the whole view; features with the same zOrder keep layer order.
23. **Mapping and scale.** The map is bbox to width x height; scaleDenominator is taken from view-1.json and used for `viz.sd` and for ground units.
24. **Date comparison.** ISO date strings compare lexicographically, which matches date order.
25. **Concatenate.** Number values are written without a trailing `.0`.
26. **Null semantics.** A selector that evaluates to NULL is not selected (CQL2 three-valued logic was implemented for and/or/not and comparisons).

## Contradictions, gaps and things I could not implement

- The clause 7 `/req/core/nested` example and the CSS examples are referenced but the example includes in `spec/1-core/examples/requirements/` were not all read; I worked from requirement text and the JSON encodings only.
- `/req/labels/placement` TODO on priority direction (see choice 7).
- `colorChannels` default TODO (#150) is not relevant here (no colorChannels in these cases).
- `/req/vector/image` gives no rule for `size` in a `mm` value when the image is also given `hotSpot` in plain pixels; I scaled the hotspot with the drawn size (choice 16).
- The `/req/vector/marker` text says markers are drawn "at points and line strings" while the default-Dot note says "at each vertex". Choice 4.
- Case 04 and case 13 have identical `style.cs.json` and identical `Places.geojson` (checked by diff). Both render the same.
- Nothing in the cases needed casing, center lines, dashes, hatches, dot patterns or stipples; those were not implemented.
- I did not implement the features that no case uses (Multi graphics, transforms, DGGS, time-dependent rules beyond date comparisons).

## Per-case table

Sizes in px: label fonts are the pt sizes converted at 1.2611 px per pt (9 pt = 11.35 px; 10 pt = 12.6 px; 12 pt = 15.1 px; 14 pt = 17.7 px); bare sizes are px (8 px in case 17/18). Outlines: size as given (px). Dots: diameter as given (px) or as converted from m. Images: size as given, or own file size (24 px) where none is given.

| case | what the renderer draws | text / outline / image sizes (px) |
|---|---|---|
| 01 | Landcover polygons at 1:50000: beige fill, 0.75 px outline; class fills bog/forest/lake; icon rule not active (scale above 10000) | outline 0.75 |
| 02 | Roads at 1:100000: grey path/default lines, coloured municipal, county, national, european strokes at 1, 2.5, 3.5, 4.5, 5.5 px; m-based rules not active | strokes 1 to 5.5 |
| 03 | Huts as red Dots (7 px) at 1:50000, opacity 0.9; detail rule not active | Dot 7 |
| 04 | Elevation: colorMap green-brown-grey, hill shading factor 2, sun 315/45; mountain labels (>= 2000 m) centred, dark grey, white 2 px outline | label 12.6, outline 2 |
| 05 | Same as 04, outline colour (243,231,184) | label 12.6, outline 2 |
| 06 | Same as 04, outline colour (232,160,144) | label 12.6, outline 2 |
| 07 | Same as 04, outline opacity 0.3 | label 12.6, outline 2 |
| 08 | Same as 04, outline opacity 0.6 | label 12.6, outline 2 |
| 09 | Same as 04, outline opacity 1.0 | label 12.6, outline 2 |
| 10 | Same as 04, no outline | label 12.6 |
| 11 | Same as 04 (outline white 2 px) | label 12.6, outline 2 |
| 12 | Same as 04, outline 1 px | label 12.6, outline 1 |
| 13 | Identical to 04 (style and data checked) | label 12.6, outline 2 |
| 14 | Same as 04, outline 3.5 px | label 12.6, outline 3.5 |
| 15 | Lake fill (169,203,227) at zOrder 2 covers ponds; pond names as marker text (italic, 9 pt) at zOrder 1, so the lake fill hides overlapping text | marker text 11.35 |
| 16 | Same lake fill; pond names as labels (drawn in the label pass, above the lakes) | label 11.35 |
| 17 | Roads 1:50000: red European/national/county lines 2 px; labels "Road N" bold 8 px, along the joined lines, minSpacing 150, white 2 px outline; Dot not drawn | label 8 (px), outline 2 |
| 18 | As 17, with a 7 px red Dot at each label anchor and text offset 7 px | Dot 7, label 8, outline 2 |
| 19 | Mountain Dots 3 px red; labels 9 pt above each Dot (y -8 px) with priority default (equal) | Dot 3, label 11.35 |
| 20 | As 19, label priority = elevation (higher elevation wins conflicts) | label 11.35 |
| 21 | As 19, label priority = -elevation (lower elevation wins conflicts) | label 11.35 |
| 22 | Road numbers as line labels, bold 8 pt, minSpacing 80 | label 10.1 (8 pt), outline 2 |
| 23 | As 22, minSpacing 150 | label 10.1, outline 2 |
| 24 | As 22, minSpacing 300 | label 10.1, outline 2 |
| 25 | Mountain marker: 4 px Dot plus marker Text 9 pt centred-bottom at (0,-4) | Dot 4, text 11.35 |
| 26 | As 25, text 12 pt | text 15.1 |
| 27 | As 25, text 9 pt bold | text 11.35 |
| 28 | As 25, text 9 pt italic | text 11.35 |
| 29 | Huts: hut.png (24 px, own size) in red, hotSpot bottom centre, plus 5 px blue Dot on the point | image 24, Dot 5 |
| 30 | As 29, image 10 mm (35.7 px), red tint (184,50,42) | image 35.7, Dot 5 |
| 31 | As 29, image 10 mm, hotSpot [0,0] (top-left at the point) | image 35.7, Dot 5 |
| 32 | As 30, blackTint green (58,125,68) | image 35.7, Dot 5 |
| 33 | Mountain 4 px Dot with marker Text 9 pt, no alignment (left top at point) | Dot 4, text 11.35 |
| 34 | As 33, centre middle | Dot 4, text 11.35 |
| 35 | As 33, right bottom | Dot 4, text 11.35 |
| 36 | As 33, centre bottom | Dot 4, text 11.35 |

Read outside the folder: none.
