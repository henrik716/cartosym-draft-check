# Notes: independent renderer for CartoSym 2.0 Part 1 (draft)

The renderer is in `renderer/` (`render.py`, `expr.py`, `raster.py`, `colors.py`). It reads `style.cs.json`, the GeoJSON layers and `view-1.json`. It writes `out/<case>-1.png` at `width` × `height`.

Run all cases:

    uv run --no-project --with numpy --with pillow --with matplotlib python renderer/render.py --all cases out

matplotlib is used only to locate the DejaVu font files that ship inside it (see N-FONT-FACE). It is not used for drawing. `colors.py` was transcribed by a script from the named-colour table in clause 16.

Each choice below has an identifier (N-…). The code refers to these identifiers in comments.

## The five choices that matter most

1. **N-PASS-SET / N-PASS-ALL**: which visualization passes and feature passes exist, and whether a rule that does not test the pass draws in every pass. This changes cases 3–6, 8, 9, 12–14, 16 and 17.
2. **N-RULE-ORDER (override, not accumulate)**: two selected rules that both set `stroke` give one stroke, not two. Cases 1 and 2 draw only the white 3 px line.
3. **N-UNKNOWN-MEMBERS**: what to do with `pattern`, `cap`, `join` and `vendor.*`, which Part 1 does not define. In case 17 a fill object with only a `pattern` becomes a solid white fill.
4. **N-CASING-ORDER**: how the casing sub-pass interacts with feature passes, zOrder and dashes. This affects cases 7, 11, 14 and 15.
5. **N-OPACITY-GROUP**: whether Symbolizer `opacity` is applied per primitive, per feature or per layer. This affects case 16.

## Choices, ambiguities and gaps

### N-PASS-SET: which pass values exist
- **Where:** clause 7, "Visualization Rendering Passes" and the table "Styles & Symbology Visual Ordering Constructs"; clause 8, "Feature Rendering Passes"; system identifiers `visualization.pass` and `feature.pass`.
- **Words:** "`visualization.pass` | Current visualization rendering pass | integer". "A later pass will only begin after all data layers and their features / coverage cells have been rendered with the symbolizers set for earlier visualization passes." "`feature.pass` | Current rendering pass for the same feature | integer".
- **Gap:** the text never says which pass numbers a Renderer runs, where they start, or whether negative numbers are allowed. Case 14 uses `feature.pass = -1`. Case 17 uses `viz.pass` 0, 1, 100 and 200.
- **Readings:**
  - (a) Run 0 plus every integer that a selector compares a pass identifier with.
  - (b) Run only the compared values.
  - (c) Run every integer from the minimum to the maximum.
  - (d) A pass expression that is not a literal (Annex C: `viz.pass = 4 * z_order + 0`) cannot be enumerated statically at all.
- **Implemented:** (a), in ascending order. The values come from `=` and `in` comparisons with literals, found anywhere in the selectors. Other comparisons (`<`, `between`, computed values) are not enumerated.
- **Relied on:** "integer" (so negative values are allowed and ordered). Annex C uses `feature.pass = -1` for bridges, which only makes sense if a normal pass 0 follows; that is why 0 is always included.

### N-PASS-ALL: does a rule that does not test the pass apply in every pass?
- **Where:** `/req/core/selector`; `/req/core/symbolizer` part 3; the Visual Ordering table; Annex B (informative).
- **Words:** "A Renderer SHALL support applying the Symbolizer of a StylingRule to a feature or coverage cell only if the rule has no `selector` or if its `selector` evaluates to true for that feature or coverage cell." "visualization.pass … Render all selected geometry features … more than once with different symbolization, or after whole map drawn in previous pass". Annex B: "visualization.pass | Order of `<FeatureTypeStyles>`", and "feature.pass | Order of symbolizers in the `<Rule>`".
- **Readings:**
  - (A) Pass values are just system identifiers. In every pass, every feature is resolved against all rules. Whatever results, including defaults and rules that ignore the pass, is drawn again.
  - (B) As in SLD FeatureTypeStyles (Annex B): a feature is drawn in a pass only by the rules that select that pass, and pass-independent rules are drawn once, in pass 0.
- **Implemented:** (A). It is the only reading that the normative selector text supports. Reading (B) has no definition in the text, and Annex B is informative.
- **Consequences:**
  - Case 8: the Zones fill (and its default 1 px black outline) is drawn again in viz pass 1. Inside the zone it covers the black road strokes of pass 0, so there the roads show only the white 3 px line.
  - Case 16: same effect.
  - Case 9: the red 1 px line is drawn twice, in feature passes 0 and 1.
  - Case 14: roads and plain rails are drawn twice, in feature passes −1 and 0.
  - Case 17: the Kerngebiet fill and `BP_TextAbschnittFlaeche` strokes are drawn four times, once per feature pass.
  - Repeated opaque drawing only darkens anti-aliased edges slightly. With `opacity < 1` it would accumulate.
- **Note:** the style of case 17 starts with `{ fill: null; stroke: null; marker: null }`. This looks like an author working around reading (A).

### N-PASS-ORDER: nesting of passes, zOrder, casing and features
- **Where:** `/req/core/z-order`; `/req/casing/casing`; the painter's algorithm, which appears only in commented-out blocks (`////`) in clause 7 and Annex C, so it is not part of the published text.
- **Words:** "portraying features and coverage cells of a single rendering pass in increasing order of their resolved `zOrder`". "feature.pass … Render feature geometry … more than once … before rendering next data point."
- **Gap:** "single rendering pass" could mean a visualization pass or a feature pass. The order of layers within one zOrder is not stated.
- **Implemented:**
  - For each viz pass: for each distinct zOrder (ascending): all casings, then the main drawing of every (layer in `view-1.json` order, feature in file order, feature pass ascending), then all centre lines.
  - zOrder is resolved separately per feature and per pass.
  - Labels are drawn after all viz passes.

### N-RULE-ORDER: how rules combine
- **Where:** `/req/core/rules` part 3; `/req/core/nested`.
- **Words:** "The Symbolizer properties specified in a StylingRule appearing later … SHALL be interpreted as overriding all Symbolizer properties set by earlier rules." "the Symbolizer of a selected nested rule inheriting from, and overriding, the Symbolizer properties of its parent rule".
- **Readings:** (a) one resolved Symbolizer per feature (and pass), so later assignments replace earlier ones; (b) each selected rule draws its own Symbolizer, as in SLD.
- **Implemented:** (a). Rules are walked depth-first in document order: a parent's symbolizer, then its nested rules, then the next sibling.
- **Consequences:** cases 1 and 2 draw only `white 3 px`. The black 5 px stroke is overridden, so there are no black edges.

### N-REPLACE: is an object property replaced or merged?
- **Where:** clause 17, the `alter` paragraph and `/req/json/partial-update`; `/req/core/instances`.
- **Words:** "resolving instance expressions to an object of the specified class, using default values for members which are not specified".
- **Implemented:**
  - An object without `"alter": true` replaces the whole property, and its missing members take the defaults.
  - With `alter`, the object is merged into the earlier value. If the earlier value is `null` or unset, it is merged into the default.
  - `{index, value}` updates one array element.

### N-UNKNOWN-MEMBERS: members Part 1 does not define
- **Where:** clause 7, "Vendor Extensions"; clause 8 ("round caps … the Joins and Caps requirements class of Part 2 adds properties"); conformanceClasses.adoc lists "Pattern Strokes and Fills" without defining it. The JSON schema lists `fill.pattern` and `stroke.pattern`. The schema has no `cap`, `join`, `patternGap`, `patternInitialGap` or `transform`.
- **Words:** "Consumers should ignore any vendor extensions they do not understand." "If a custom property is used in the Parameter Value of a Symbolizer property, that property should be left set to the last Parameter Value that was understood." "The same principle applies for requirements clases that are not understood".
- **Readings:**
  - (a) Member level: ignore only the member that is not understood. The rest of the object still applies, and missing members take defaults.
  - (b) Property level: the whole `fill`/`stroke` assignment that contains a member not understood is skipped, and the property keeps its earlier value (`null` in case 17).
  - (c) Implement `cap`/`join` with common SVG meanings, and patterns by guessing tile size and origin.
- **Implemented:** (a).
  - `cap`, `join`, `pattern`, `patternGap`, `patternInitialGap`, `transform` and every `vendor.*` member (`vendor.xleitstelle.offset`, `placements`, `rotate`, `trim`) are ignored.
  - Strokes therefore keep round caps and joins, and vendor-offset strokes are drawn on the geometry.
- **Consequences in case 17:**
  - A fill that has only a `pattern` resolves to a new Fill whose colour defaults to **white**. `BP_SpezielleBauweise`, `BP_UeberbaubareGrundstuecksFlaeche` and the Verkehrsfläche besonderer Zweckbestimmung are painted solid white in viz pass 1.
  - A stroke that has only `pattern`/`patternGap` becomes the default 1 px black stroke (`BP_Wegerecht`, feature pass 1).
  - Under reading (b), none of these would be drawn, but nearly every stroke in case 17 would also vanish, because each one has a `join`.
- **Not implemented:** pattern fills and pattern strokes (images tiled or repeated along lines). The SVGs in `cases/case-17/svg/` are not used.

### N-SCALING-UNITLESS: contradictory wording (noted, not used)
- **Where:** clause 16, table "Units of measure abbreviations".
- **Words:** "(none) | For relative values like scaling, 100 times less than if _pc_ is specified."
- **Problem:** this reads as if a unitless `10` is 100 times less than `10 pc`, which would be 0.001. The likely intent is that a unitless `1` equals `100 pc`. Case 17's `scaling: [10, 10]` would then make a 150 px SVG tile 1500 px wide, which seems unintended.

### N-PROPERTY-PATH: `{"property": "zweckbestimmung.0"}`
- **Where:** `/req/core/expressions-field-identifiers`; README ("Properties are as they appear in the file").
- **Words:** "resolving an Identifier Expression to the value of the named feature property".
- **Readings:** (a) a property literally named `zweckbestimmung.0`, which is missing and so null; (b) element 0 of the array property `zweckbestimmung`.
- **Implemented:** (a). The text defines no member or index access; a comment in clause 7 says "We should probably consider including operators for accessing instance members, and indexing array elements."
- **Consequence:** the `SchadstoffBelastBoden` rule is never selected, so `BP_KennzeichnungsFlaeche` draws nothing. Its base rule sets fill, stroke and marker to null.

### N-EXPR-NULL: null in comparisons and logic
- **Where:** `/req/core/operations` part 4 ("with a null operand as specified by CQL2"); the NOTE under `/req/core/selector`.
- **Gap:** the CQL2 behaviour is only referenced, not restated.
- **Implemented:** three-valued (Kleene) logic.
  - A comparison with null is null. `and(false, null)` is false, `or(true, null)` is true, and `not(null)` is null.
  - `?:` takes the else branch when the condition is not true.
  - `in`: a null value gives null.
  - There is no type coercion: the string `'0'` is not equal to the number `0`.
  - Integers and reals compare numerically (`2` = `2.0`, as needed for `dataLayer.featuresGeometryDimensions = 2.0`).

### N-SYSID-NAMES: names of System Identifiers
- **Contradiction:** the text says `dataLayer.identifier`, `visualization.pass`, `visualization.scaleDenominator`, `feature.geometryDimension` and `dataLayer.featuresGeometryDimension` (singular). The UML uses `feature.geometryDimensions`. The JSON schema enum has `dataLayer.id`, `viz.pass`, `viz.sd`, `feature.id` and `dataLayer.featuresGeometryDimensions` (plural), and the cases use these.
- **Implemented:** both spellings resolve to the same value. `dataLayer.featuresGeometryDimensions` is the common dimension of all features in the layer, or null when they are mixed.

### N-GROUND-UNITS: metres to pixels
- **Where:** `/req/vector/units`; clause 8 (0.28 mm pixel).
- **Gap:** ground units can be converted with `scaleDenominator × pixelSize`, or with the ground size of a pixel from bbox / width. In cases 1–16, 0.28 mm × 3571.4 = 0.99999 m per pixel, while bbox / width = 1 m per pixel.
- **Implemented:** bbox / width, so ground widths agree with the drawn geometry.
- **Other units:** `mm`, `cm`, `inch` and `pt` go through `pixelSize_mm` (pt = 1/72 inch). A unitless number is in pixels.

### N-STROKE-AA: anti-aliasing, hairlines and colour space
- **Gap:** the text does not say whether to anti-alias, how to draw strokes thinner than 1 px (case 17: 0.2 m = 0.36 px), or in which colour space to blend.
- **Implemented:**
  - Anti-aliasing uses box-filter coverage computed from the distance to the centre line, so thin lines get proportional coverage.
  - Polygon fills use 4 × 4 supersampling with the even-odd rule.
  - Blending is in sRGB. The permission `/per/vector/image-linear-light` is only about images.

### N-POLY-OUTLINE: which rings the stroke draws
- **Words:** clause 8: "drawing an outline (e.g., for linear geometries or the exterior of a polygon geometry)".
- **Readings:** only the exterior ring, or every ring.
- **Implemented:** every ring, holes included. "e.g." reads as an example, not a restriction. Case 17 has polygons with holes.

### N-POINT-STROKE: stroke and fill on point features
- **Gap:** the default Stroke and Fill apply to every Symbolizer, so a point feature also has a 1 px black stroke by default. The NOTE under `/req/vector/dot` says "A Dot is a stroke drawn on a single point".
- **Implemented:** fill and stroke are not drawn for points. Only the marker is drawn (case 18 Harbours).

### N-DEFAULT-MARKER: markers no rule sets
- **Where:** NOTE under `/req/core/default-values`; `/req/vector/marker`.
- **Implemented:** as written. Case 18's `Piers` sets no marker, so it gets a white Dot of 10 px at the polygon's area centroid. The permitted hairline outline (`/per/vector/dot-outline`) is not used.

### N-CASING-ORDER: casing with feature passes, zOrder and dashes
- **Where:** `/req/casing/casing`; `/req/casing/center`.
- **Words:** "drawing, within a single visualization pass, the casings of all features with the same `zOrder` beneath the main strokes of all those features". "using the StrokeStyling specified by the `casing` property".
- **Gaps:**
  - It is not said whether casings drawn in different feature passes still go beneath all main strokes.
  - It is not said whether casings of different layers with the same zOrder merge.
  - It is not said whether the casing follows the `dashPattern`. StrokeStyling has no dashes.
  - The default `width` of a casing object that has no `width` could be the Stroke default (1 px) or the casing-row default (0).
- **Implemented:**
  - All casings of a zOrder group, from every layer and every feature pass, are drawn first.
  - The casing is a continuous stroke of `width + 2 × casing.width`, so it is not dashed.
  - The centre line is continuous and drawn on top.
  - A casing without `width` defaults to 0.
- **Consequence in case 15:** the rail's dash gaps show the dark casing beneath, except where the rail crosses a road. There the road's main stroke covers the rail casing, which was drawn earlier in the same zOrder group.

### N-DASH-CAPS: caps of each dash
- **Where:** `/req/vector/stroke` part 3 ("round caps at the ends of open lines"); `/req/dashes/dash-pattern`.
- **Gap:** the text does not say whether each dash gets the line's caps, and it defines no behaviour for an odd-length pattern or a zero-length dash.
- **Implemented:**
  - Each dash is drawn as an open line with round caps, so a 6 px dash at width 3 px appears 9 px long.
  - A zero-length dash is a round dot: case 17's `dashPattern [0, 5]` gives dots.
  - An odd-length pattern is repeated once (SVG convention).
  - The pattern restarts on each line or ring, as the requirement says.

### N-OPACITY-GROUP: how Symbolizer opacity is applied
- **Where:** `/req/core/opacity`; `/rec/core/opacity-together` and the NOTE after it.
- **Words:** "applying the resolved `opacity` property by multiplying it with the opacity of the fill, the stroke…". "either for each feature or for all features of a data layer with the same `zOrder` drawn at once". "Which of these to recommend is still under consideration."
- **Implemented:** per feature and per feature pass. Fill, main stroke and marker are drawn into a scratch layer, which is then composited with `opacity`. Casing and centre lines (separate sub-passes) are multiplied directly.
- **Consequence in case 16:** where two roads cross, the half-transparent strokes overlap and look darker. Per-layer grouping would give a uniform 0.5.

### N-LINE-LABEL: where a label goes on a line
- **Where:** `/req/labels/label`, `/req/labels/placement`.
- **Gap:** the text never says where a label is anchored on a line or polygon, nor whether it follows the line.
- **Implemented:**
  - Lines: one horizontal label at the point halfway along the line (the longest part of a multi-line).
  - Polygons: the area centroid.
  - Points: the point.
  - Labels are placed in order of collection. A label whose box overlaps a placed one is skipped (`/rec/labels/overlap`).
- **Consequence in case 13:** the label is resolved in both viz passes. The second copy is suppressed as an overlap, and "Road 2" is also suppressed because it overlaps "Road 1".
- **Not implemented:** priority, minSpacing and maxSpacing (not used in these cases). Labels that extend past the map edge are drawn clipped (the NOTE leaves this to the Renderer).

### N-TEXT-ALIGN: alignment names and metrics
- **Contradiction:** `/req/vector/text` and the TextAlignment table say `horzAlignment`/`vertAlignment`. The UML and clause 16 say `horizontal`/`vertical`. The schema says `hAlignment`/`vAlignment`.
- **Implemented:** all three spellings, plus the two-element array used in the cases.
- **Metrics:** "top of the font's ascent" and "bottom of its descent" use the font's own ascent and descent metrics. Horizontal extent is the advance width.

### N-FONT-DEFAULTS: font members without defaults
- **Gap:** the Font class has no default `size`, `face` or `color`, and `color` and `opacity` are missing from the Font table (only the UML and the schema have them).
- **Implemented:** size 10 pt, colour black, opacity 1. pt is converted to px with the 0.28 mm pixel (11 pt ≈ 13.9 px).

### N-FONT-FACE: font faces
- **Gap:** the text does not say what to do when a requested face is unavailable, or how the generic name `sans-serif` is resolved.
- **Implemented:** `Arial` and `sans-serif` map to DejaVu Sans, using its Bold variant when `bold` is true. The font files come from inside the matplotlib package, so no system font file is read. Glyph shapes therefore differ from Arial.

### N-NULL-PARAM: null-valued Parameter Values
- **Implemented:** `/req/parameter-values/null` as written. A zOrder expression that is null gives 0 (not the default 1), a null visibility gives false, and a null colour gives black. Case 17's zOrder `isNull(ebene) ? 0 : abs(ebene)` never yields null.

### Other things noted
- The README says the CRS is EPSG:25833, but case 17 is in EPSG:25832. Only a linear bbox-to-pixel mapping is used, so the difference does not matter.
- `/req/vector/marker` defines `marker` as "an array of graphical elements", but the JSON schema and clause 8 make it an object with `elements`. The object form is implemented.
- The Symbolizer default `zOrder` is 1 (default table), while a null zOrder is 0 (null table). Both are used as written.
- The capability System Identifiers include `dotpatterns` in the schema but not in the text's table.
- Defaults are given for an Image `hotSpot` etc., but nothing in these cases uses Image graphics. Image markers are not drawn (no SVG rasterizer).

## What the renderer draws for each case

| Case | What is drawn |
|---|---|
| case-01 | Three roads as white 3 px lines only: the nested white stroke overrides the black one (N-RULE-ORDER). |
| case-02 | Same as case-01: the second top-level rule overrides the first. |
| case-03 | Per feature, black 5 px then white 3 px: each later road's black edges cut across earlier roads at crossings and joins. |
| case-04 | As case-03 with black 12 px / white 8 px. |
| case-05 | All roads black 5 px (viz pass 0), then all white 3 px (pass 1): merged crossings. |
| case-06 | As case-05 with 12 / 8 px. |
| case-07 | Built-in casing: white 3 px with 1 px black casing (5 px total), casings merged beneath. Looks the same as case-05. |
| case-08 | Light gray zone with default 1 px black outline, drawn again in pass 1 over the black road strokes. Roads are black/white outside the zone and white only inside it (N-PASS-ALL). |
| case-09 | Per-feature black 7 / white 5 (feature passes), then red 1 px centre lines in viz pass 1 (drawn in both feature passes). |
| case-10 | Gray 4 px roads under black 2 px rail (zOrder 0 vs 1), although the rail layer comes first. |
| case-11 | Yellow 10 px roads, 1.5 px brown casing merged beneath, 1 px brown centre line on top. |
| case-12 | Same look as case-11, built from three viz passes (13 / 10 / 1 px). |
| case-13 | Black 12 / white 8 merged roads. Bold DejaVu labels "Road 1" and "Road 3" centred at line midpoints; "Road 2" dropped as overlapping. |
| case-14 | Yellow roads with brown casing; dark 3 px rails on top (same zOrder 1, later layer). The bridge (zOrder 2) is drawn white 9 px with dark casing (feature pass −1) plus a dark 3 px line (pass 0) above the road. |
| case-15 | Yellow cased roads. The rail is white 3 px round-capped dashes [6, 6] on a continuous dark casing; at road crossings the road covers the rail casing. |
| case-16 | Green zone with 1 px black outline. Roads at opacity 0.5: black 12 px (pass 0); the zone is redrawn over it in pass 1; then white 8 px at 0.5. Darker where roads overlap (per-feature opacity). |
| case-17 | Kerngebiet ochre fills, rail areas lilac, road areas yellow with thin outlines (viz pass 0). White solid fills where only a `pattern` fill is given (pass 1). Blue 3 m water strokes, red dashed and dotted monument strokes, dashed and thin outlines (pass 100). Green / black / blue boundary lines and default 1 px black strokes for `BP_Wegerecht` (pass 200). Vendor offsets, caps/joins and patterns are ignored; `BP_KennzeichnungsFlaeche` draws nothing (N-PROPERTY-PATH). |
| case-18 | Gray pier polygon with 1.5 px outline and a default white 10 px Dot at its centroid. Harbour point drawn as an 8 px dark-blue Dot. Label "Harbour" in bold 16 pt dark blue, top-left aligned, 16 px below the point. |

## Files read outside this folder

none

(The Python packages numpy, Pillow and matplotlib were loaded as libraries. The DejaVu font files bundled inside matplotlib were loaded to draw text. None of these is about Cartographic Symbology.)
