# Independent renderers written from the requirement text

Six renderers were written from the Part 1 requirement text of `main` at c9808c0 alone, to find where the text lets two implementations draw different maps. How the runs were set up, and what was changed in the text because of them, is in [`../wording-decisions.md`](../wording-decisions.md).

| Run | Model | Notes | Renderer |
|---|---|---|---|
| 1 | Claude Opus | [run1/notes.md](run1/notes.md) | [run1/renderer/](run1/renderer/) |
| 2 | Claude Opus | [run2/notes.md](run2/notes.md) | [run2/renderer/](run2/renderer/) |
| 3 | Claude Sonnet | [run3/notes.md](run3/notes.md) | [run3/renderer/](run3/renderer/) |
| 4 | Claude Opus | [run4/notes.md](run4/notes.md) | [run4/renderer/](run4/renderer/) |
| 5 | Claude Sonnet | [run5/notes.md](run5/notes.md) | [run5/renderer/](run5/renderer/) |
| 6 | Claude Haiku | [run6/notes.md](run6/notes.md) | [run6/renderer/](run6/renderer/) |

Each run was a fresh session with a sealed folder holding the requirement text (no figures), the 20 render kits of the document's requirement examples, and [the instructions it was given](README-given-to-the-runs.md). It could not see this repository, pycartosym, libCartoSym, the web or the other runs. The kits are the same as the document's examples: the styles are in `1-core/examples/requirements/` of the spec, and the data comes from `src/cartosym_draft/data/rondane/` and the Rondane grids.

- [`strips/`](strips/): one image per map, the six runs on the old text side by side (the draft renderer after the changes is in `verify-strips/`).
- [`pixel-differences.md`](pixel-differences.md): the share of pixels that differ clearly between each pair. The draft renderer's maps have a 1-pixel grey frame, which accounts for about 0.8 % against every run.

Run 6 read the GeoJSON with the Windows default encoding instead of UTF-8, so the place names in its maps are garbled. That is a mistake of the run, not of the text.

## Check on the tightened text

| Run | Model | Notes | Renderer |
|---|---|---|---|
| verify 1 | Claude Opus | [verify1/notes.md](verify1/notes.md) | [verify1/renderer/](verify1/renderer/) |
| verify 2 | Claude Sonnet | [verify2/notes.md](verify2/notes.md) | [verify2/renderer/](verify2/renderer/) |
| verify 3 | Claude Haiku | [verify3/notes.md](verify3/notes.md) | [verify3/renderer/](verify3/renderer/) |

The same kits and instructions, with the requirement text after the changes in [`../wording-decisions.md`](../wording-decisions.md). [`verify-strips/`](verify-strips/) and [`verify-pixel-differences.md`](verify-pixel-differences.md) compare them with the draft renderer after the changes.

## Expression evaluators

| Run | Model | Notes | Evaluator | Results |
|---|---|---|---|---|
| expr 1 | Claude Opus | [expr-run1/notes.md](expr-run1/notes.md) | [expr-run1/evaluator/](expr-run1/evaluator/) | [results.json](expr-run1/results.json) |
| expr 2 | Claude Sonnet | [expr-run2/notes.md](expr-run2/notes.md) | [expr-run2/evaluator/](expr-run2/evaluator/) | [results.json](expr-run2/results.json) |
| expr 3 | Claude Haiku | [expr-run3/notes.md](expr-run3/notes.md) | [expr-run3/evaluator/](expr-run3/evaluator/) | [results.json](expr-run3/results.json) |

Each evaluator got the requirement text and the 123 cases of [`../../cases/`](../../cases/) as they were at the time (without `expect`, `note` and `disputed`), with [these instructions](README-given-to-the-expression-runs.md). [`expression-results.md`](expression-results.md) lists the cases where a result differs from the harness's expected value.
