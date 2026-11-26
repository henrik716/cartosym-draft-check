# Second round of independent readings (2026-11-26)

After the first round ([`../README.md`](../README.md), for #192), this round read only text that no independent reader had seen yet:

- **Round A:** the rendering passes, with the text of `main` at fefe225 and the pass kits (passes-01 to passes-13, kit 14, label-pass), which only the draft renderer had run before.
- **Round B:** the text of our open pull requests #256–#262, #265 and #266, merged onto `main` as a local test merge (eaa8bd2, never pushed), with one case per panel of the requirement examples they change.
- **Round C:** the expressions, with the same merged text: the 161 cases of [`../../../cases/`](../../../cases/) without `expect`, `note` and `disputed`, plus 16 probes for unary minus (#199) and the minus in CartoSym-CSS values (#259).

Each round had three runs: Claude Opus (`a1`, `b1`, `c1`), Claude Sonnet (`a2`, `b2`, `c2`) and Claude Haiku (`a3`, `b3`, `c3`). Each run was a fresh session given a sealed folder with the requirement text (no figures) and the cases, under the instructions in `README-given-round-*.md`. A run could not see this repository, pycartosym, libCartoSym, the web or the other runs, and each run listed the files it read outside its folder: none (the Python packages and system fonts apart). The case folders used neutral names (`case-NN`), and comments that stated the expected result were removed from the styles. The `*-mapping.json` files map the cases back to the kits and examples. The scripts that built the folders and compared the results are in [`tools/`](tools/).

Every reader was a Claude model. A split between them is evidence that the text is open; agreement may also come from a bias the models share.

## Round A: rendering passes

[`compare-a/report.md`](compare-a/report.md) gives the share of pixels that differ clearly between each run and the draft renderer's readings of each kit; [`compare-a/strips/`](compare-a/strips/) shows them side by side.

- **Same picture:** in 14 of the 18 cases, the three runs and the draft renderer agree to 0.1 % of pixels or better (nested and top-level overrides, `feature.pass`, `viz.pass`, built-in casing, `zOrder` across layers, centre lines, feature pass −1, shared `zOrder`).
- **Split: a rule with no `viz.pass` condition, next to rules with one** (passes-06, passes-13). Opus and Sonnet apply the `Zones` rule in every pass, so the zone is drawn again in pass 1 and covers the roads' black pass-0 strokes inside it. Haiku and the draft renderer draw the zone once. Opus notes that Annex B, which maps passes to SLD FeatureTypeStyles, supports the other reading. This is the question of #207.
- **Kit 14** differs by 5–20 % between the runs, because it uses Part 2 members that Part 1 does not define (`pattern`, `cap`, `join`, `patternGap`, `vendor.*`), which each run ignored differently.
- Smaller differences: the anti-aliasing of a 1 px stroke (passes-07), and the fonts and the position of labels on lines (passes-10, label-pass).

## Round B: the text of our open pull requests

[`compare-b/report.md`](compare-b/report.md), [`compare-b/strips/`](compare-b/strips/). The draft renderer is drawn here on white, without the pale context layers of the document's figures.

- **Same picture:** Image size, `hotSpot` and tints (#262) agree exactly. Font sizes in `pt` and without a unit (#260) and font outlines agree; the 1–3 % differences come from font rasterizing and text metrics.
- **Contradiction in #265:** `/req/labels/line` says a position's `y` is "positive towards the top of the label", while `/req/vector/graphics` says a positive `y` is "an offset downwards on the map, as for screen coordinates". The draft renderer follows `/req/vector/graphics`. No image shows it, because the example's position is `7 0` (found by Sonnet).
- **A number where a string is expected:** #265's example writes `concatenate('Road ', number)`, and `number` is an integer. Read strictly, `/req/functions/call-expressions` makes the result NULL, and no road number is drawn. All three runs used the permission `/per/functions/type-casts` (found by Opus). The same gap is on `main`: `labels-placement-spacing` writes `text: number`, and the `text` of a Text is a string.
- **Open on purpose, and the runs differ there:** which labels survive a collision (cases 19–21; label footprint, ties, default `priority`), labels at the edge of the map ("left to the Renderer"), where repetitions along a line start without `maxSpacing`, and how bright hill shading is.

## Round C: expressions

[`compare-c.md`](compare-c.md) lists the cases where a run differs from the harness's expected value, and the probes. Most rows there are differences of form only (`3` against `3.0`, a point as `[x, y]` or `{x, y}`, which the harness treats as the same).

- **Same result:** all three runs give the expected value in 143 of the 161 cases, and the rest differ in form only, except for `accenti`.
- **Unary minus (#199):** all three runs read `-2 ^ 2` as 4, `-a ^ 2` (with `a` = 3) as 9 and `-2 ^ 0.5` as NULL, that is `(-a) ^ 2`. None found it in the prose: each took it from the order of the alternatives in the grammar, and each noted that the usual mathematical reading gives −4.
- **The minus in CartoSym-CSS values (#259):** in a `position`, `10 -4` is the point (10, −4) for all three, and `10 - 4` and `10-4` are subtractions. `10 -4` as a whole expression is the tuple `[10, -4]` for two runs and an error for one; none read it as 6.
- **Grouping:** in the grammar, `(1 + 2)` matches the array form before the parenthesized expression, so a strict reading makes `(1 + 2) * 3` an array times a number. All three treated it as grouping (found by Opus).
- **`accenti`** on Cyrillic and Tajik letters splits, because the text gives no folding table; it points to libCartoSym and UTR #30.
- Also noted by all three: comparisons and arithmetic with NULL are only "as specified by CQL2", which the folder did not include, and `a_equals` has an open TODO (#154).
