# cartosym-draft-check

Tools and evidence for the requirements of OGC Cartographic Symbology 2.0 Part 1 (and the Part 2 gradient fills) in [opengeospatial/cartographic-symbology](https://github.com/opengeospatial/cartographic-symbology): a renderer and expression evaluator that follow the requirement text, a test harness that runs the same expressions through libCartoSym and pycartosym, tests for the grammar and the JSON schemas, and the figures of the Part 1 document.

Requirements written without an implementation are hard to get right. This repository implements them, renders every place where the text leaves a behavior open, and checks whether readers who only have the text would draw the same maps. The goal is to show which requirements hold up, which are open questions, and where the document disagrees with itself. What it shows are proposals for the Cartographic Symbology SWG, not decisions.

## Pages

The pages are published with GitHub Pages, starting from the [home page](https://henrik716.github.io/cartosym-draft-check/). They share one navigation bar:

| Page | What it is for |
|---|---|
| [Requirements](https://henrik716.github.io/cartosym-draft-check/gallery/requirements.html) | Every requirement, recommendation and permission of Part 1 and the Part 2 gradient fills, with its text and how it is checked. Under each tested requirement, its test cases with what the draft renderer, libCartoSym and pycartosym give. |
| [Judgement calls](https://henrik716.github.io/cartosym-draft-check/gallery/index.html) | Where the text leaves a renderer a choice (or left one before it was tightened): the same map drawn each way, and a decision matrix with a proposed resolution for each question and where it stands on GitHub. |
| [Rendering passes](https://henrik716.github.io/cartosym-draft-check/gallery/passes.html) | Test cases for how `viz.pass`, `feature.pass`, `zOrder`, casings and nested rules decide what is drawn on top ([#212](https://github.com/opengeospatial/cartographic-symbology/issues/212)), each with a render kit. |
| [Playground](https://henrik716.github.io/cartosym-draft-check/gallery/playground.html) | Edit the style of any card or sample and see the draft renderer draw it again, in the browser. |
| Records | The walkthroughs of [#133](https://henrik716.github.io/cartosym-draft-check/gallery/pr133-requirements-walkthrough.html) and [#192](https://henrik716.github.io/cartosym-draft-check/gallery/pr192-renders-walkthrough.html) as they were presented, the [wording decisions](reports/wording-decisions.md), the [independent renders](reports/independent/) and the [expression test report](reports/libcartosym-main/report.md). |

The [gallery maps](https://henrik716.github.io/cartosym-draft-check/gallery/maps/) are the 20 maps of #192 kept outside the document. The walkthroughs used to be `walkthrough.html` and `renders-walkthrough.html`; those addresses redirect to the new ones, and every other address and anchor linked from GitHub still works.

## Contents

**Checking the requirements**

| | Where | What it is |
|---|---|---|
| **Draft renderer** | [`src/cartosym_draft/`](src/cartosym_draft/) | A CQL2 expression evaluator and SVG renderer that does what the requirements say. Each behavior that was open in the draft is a switchable option ([`options.py`](src/cartosym_draft/options.py)). |
| **Test harness** | [`harness/`](harness/), [`cases/`](cases/) | 135 test cases whose expected values come from the requirement text, run through libCartoSym, pycartosym and the draft renderer. |
| **Test report** | [`reports/libcartosym-main/`](reports/libcartosym-main/) | Results per requirement and implementation against the latest libCartoSym from GitHub, written by CI; the requirements page shows them under each requirement. [`reports/report.md`](reports/report.md) has the same with libCartoSym from the `cartosym` pip package (November 2025). |
| **Round trips** | [`harness/roundtrip.py`](harness/roundtrip.py), [`reports/roundtrip.md`](reports/roundtrip.md) | Converts the expression cases CQL2-Text → CQL2-JSON → CQL2-Text → CQL2-JSON, and the spec's examples CartoSym-CSS → CartoSym-JSON → CartoSym-CSS → CartoSym-JSON, with libCartoSym and pycartosym; compares the JSON with the case's or the example's, and checks that the round trip gives it back. CI does the same with the latest libCartoSym. |
| **Grammar check** | [`tools/check_grammar.py`](tools/check_grammar.py), [`cases/grammar/`](cases/grammar/) | Generates a parser from the spec's CartoSym-CSS grammar with ANTLR and runs 38 cases and every `.cscss` example through it. |
| **Schema tests** | [`schema-tests/`](schema-tests/) | 744 CartoSym-JSON documents with expected outcomes, validated against the Part 1 and Part 3 schemas with python-jsonschema, Hyperjump and Ajv. The 624 built by code are also in [`schema-tests/cases.json`](schema-tests/cases.json), as plain JSON. |

**For the Part 1 document**

| | Where | What it is |
|---|---|---|
| **Document figures** | [`doc_examples.py`](src/cartosym_draft/doc_examples.py) | Renders the document's examples on Rondane data and writes, into a spec checkout, each example's render, its CartoSym-JSON (converted from the CartoSym-CSS with pycartosym, with the fix-ups in `PYCARTOSYM_GAPS`) and an AsciiDoc block with the render above the CartoSym-CSS. The requirement figures are vignettes: rows of small panels that each change one value of the style. Every JSON is validated against the spec's schema. |
| **Independent renders** | [`reports/independent/`](reports/independent/) | Six renderers and three expression evaluators, each written by a fresh Claude session from the requirement text alone, and three more renderers on the tightened text. Their notes, code, images and the pixel comparisons. |
| **Wording decisions** | [`reports/wording-decisions.md`](reports/wording-decisions.md) | For each requirement whose wording #192 tightened: the text before, how each reader rendered it, the evidence, and the reading proposed. |

**For discussion**

| | Where | What it is |
|---|---|---|
| **Judgement calls** | [`gallery/index.html`](gallery/index.html) | The decision matrix, then 23 cards, one per judgement call: the requirement text, the same map rendered with the text's choice and the alternatives, and sources. See [Reading the judgement calls](#reading-the-judgement-calls). |
| **Requirements** | [`gallery/requirements.html`](gallery/requirements.html) | All 142 requirements, recommendations and permissions, each with its text, how it is checked and the evidence. Straightforward visual requirements get one of 18 sample renders, with a "Check" line saying what to look for. |
| **Rendering passes** | [`gallery/passes.html`](gallery/passes.html), [`passes.py`](src/cartosym_draft/passes.py) | 13 cases: 01 to 08 are Maxime Collombin's from pycartosym `examples/passes`; 09 to 13 add the center line, labels, a bridge in `feature.pass = -1`, two layers sharing a `zOrder` and a translucent layer, and draw each reading where the text is open. Each has a render kit (`gallery/kit/passes-<case>/`) with both style encodings, the draft renderer's image and a README with what should be drawn; SLD/SE, MapLibre and QGIS versions are welcome as pull requests. |
| **Playground** | [`gallery/playground.html`](gallery/playground.html) | The draft renderer in the browser through [Pyodide](https://pyodide.org). |
| **Render kits** | [`gallery/kit/`](gallery/kit/), [`gallery/kit.zip`](gallery/kit.zip) | The style, data and view settings of every card, sample and pass case, to render the same maps with another renderer. |

## The implementations

Three implementations are compared, and they do different things. The **draft renderer** (this repository) evaluates expressions, resolves the style for each feature and draws the map. **libCartoSym** (Ecere) reads and writes CartoSym-CSS, CartoSym-JSON, SLD/SE and Mapbox styles, and evaluates expressions and styles for a feature (`cs-canif eval`); the test harness compares its results with what the requirements say. **pycartosym** (Maxime Collombin) converts between CartoSym-CSS, CartoSym-JSON, SLD/SE and MapLibre styles; the draft renderer uses it to read CartoSym-CSS and CQL2-Text, and the test harness checks its conversion to CQL2-JSON.

The draft renderer is a discussion tool, not a reference implementation. Because it implements the requirements itself, it can show what each choice looks like, but not whether that choice is the intended one: that is for the SWG to decide. Passing its own tests shows that it matches the text, not that the text is right. That is why the independent renderers exist: they show whether others reading the same text draw the same maps.

In the latest run (CI, 21 November 2026, libCartoSym `main` at e9342b6), all three give what the text says on every case they run: the draft renderer on 132 of the 135 cases, libCartoSym on 119, and pycartosym, which converts rather than evaluates, on 119.

## How it fits together

```text
[ 1. INPUTS ]
spec checkout ───────────────> tools/extract_requirements.py ──┬──> requirements.json
(../cartographic-symbology)                                    └──> CartoSym-JSON.schema.json
Kartverket DTM, Sentinel-2 ──> tools/fetch_rondane.py, fetch_sentinel2.py ──> rondane_data.py, sentinel2_data.py (150 m)
Kartverket N50, DTM, S-2 ────> tools/fetch_n50.py, fetch_hires.py ─────────> data/rondane/ (vector layers, 50 m grids)

[ 2. TEST HARNESS ]  harness/run.py
cases/*.yaml ──┬──> libCartoSym     (cs-canif eval)          ──┐
               ├──> pycartosym      (CQL2-Text → CQL2-JSON)  ──┼──> reports/report.md
               └──> draft renderer  (evaluate)               ──┘    reports/results.json

[ 3. PAGES ]  python -m cartosym_draft.gallery
draft renderer        ──┬──> index.html (root)          home page
+ examples 5–9          ├──> gallery/index.html          judgement calls: decision matrix, 23 cards
+ sample data           ├──> gallery/requirements.html   142 requirements, 18 samples, test cases per requirement
+ requirements.json     ├──> gallery/passes.html         13 pass cases
+ review.py             ├──> gallery/kit/, kit.zip       style, data and view per card, sample and pass case
+ reports/libcartosym-  ├──> gallery/playground.html     the draft renderer in the browser (Pyodide)
  main/results.json     └──> the navigation bar in the two walkthroughs

[ 4. DOCUMENT FIGURES ]  python -m cartosym_draft.doc_examples
spec's 1-core/examples/*.cscss ──> pycartosym + fix-ups ──> <name>.cs.json  ──┐
data/rondane/                  ──> draft renderer       ──> figures/*.jpg   ──┼──> into the spec checkout
                                                                              └──> <name>.adoc

[ 5. GRAMMAR AND SCHEMA ]
spec's .g4 files    ──> tools/check_grammar.py (ANTLR) ──> cases/grammar/css-grammar.yaml + examples
spec's JSON schemas ──> schema-tests/run.py, js/check.mjs  ──> schema-tests/out/

[ 6. CI ]  .github/workflows/libcartosym-main.yml (weekly, and when the harness or cases change)
latest eC + libCartoSym (Ubuntu) ──> harness/run.py, harness/roundtrip.py ──> reports/libcartosym-main/
```

The independent renders and the wording log (`reports/independent/`, `reports/wording-decisions.md`) were made by hand, not by a script in this repository; `tools/build_renders_walkthrough.py` turns them into the #192 walkthrough.

```text
cartosym-draft-check/
├── index.html            # the home page (generated)
├── src/cartosym_draft/   # the draft renderer, the pages and the document figures
│   ├── evaluate.py       #   CQL2-JSON expressions
│   ├── cascade.py        #   styling rules → the symbolizer for each feature
│   ├── render.py         #   vector features → SVG
│   ├── coverage.py       #   coverages and hill shading → PNG
│   ├── options.py        #   the switchable judgement calls
│   ├── nav.py            #   the navigation bar shared by every page
│   ├── home.py           #   the home page
│   ├── gallery.py        #   the judgement calls; also review.py (the decision matrix), samples.py, requirements_page.py, passes.py, playground.py, kit.py
│   ├── doc_examples.py   #   figures, CartoSym-JSON and AsciiDoc for the Part 1 document
│   ├── n50.py            #   loads the N50 layers in data/rondane/
│   ├── data/rondane/     #   N50 vector layers and 50 m grids
│   └── examples/         #   the spec's coverage examples 5 to 9
├── harness/              # run.py, and adapters.py for the three implementations
├── cases/                # expression cases; grammar/ has the grammar cases
├── schema-tests/         # CartoSym-JSON schema tests (see its README)
├── reports/              # test reports, independent renders, wording decisions
├── gallery/              # the generated pages and render kits, served by GitHub Pages
└── tools/                # requirement snapshot, grammar check, data fetchers, walkthrough builder, pycartosym export
```

## Reading the judgement calls

- <kbd>draft</kbd> marks the variant the requirement text chooses.
- <kbd>open in draft</kbd> marks a card where the text does not settle the question. Its first variant, labelled "draft renderer's choice", is the proposed resolution in the decision matrix.
- A note under a variant says what to look for where the result is the point (for example, a casing drawn over the stroke hides it).

The decision matrix is kept up to date in [`review.py`](src/cartosym_draft/review.py): for each question, what the text says, the proposed resolution, and where it stands on GitHub on the date in its column heading. A merged pull request counts as decided; "answered by Jérôme" is one member's answer, not an SWG decision. Update the rows and `MATRIX_AS_OF` together.

Every style in the judgement calls and the samples is validated against the snapshot's CartoSym-JSON schema when the pages are built; the build stops on an invalid style.

## What is covered

The snapshot in [`requirements.json`](src/cartosym_draft/requirements.json) has 142 identifiers: 131 requirements (125 in Part 1, 6 for the Part 2 gradient fills), 4 recommendations and 7 permissions. Every one is checked in at least one way: 37 by a judgement call, 42 by a sample render or a document example, 62 by test cases and 12 as encodings (some in more than one way); [`requirements.html`](gallery/requirements.html) lists how.

- **Rendered:** vector styling (fill, stroke, units, markers, Dot, Text, Image), casing, dashes, hatches, stipples, dot patterns, font outlines, labels, coverage styling, hill shading and Part 2 gradients: judgement calls as cards, the rest as samples and document examples.
- **Tested:** arithmetic, math, text relation and manipulation, array relations, conditionals, right-hand operands, function calls, variables, NULL, and core literals, arrays and identifiers, in the test harness.
- **Encoding only:** CartoSym-CSS and CartoSym-JSON. The document's examples are converted with pycartosym, validated against the schema, and parsed by libCartoSym and by a parser generated from the spec's grammar.

## Running it

The tools read a checkout of the spec repository next to this one (`../cartographic-symbology`).

```
uv sync
uv run python tools/extract_requirements.py [spec checkout]  # requirement text and JSON schema from the spec checkout
uv run python harness/run.py                                 # test report (reports/); REPORT_DIR=<absolute path> writes elsewhere
uv run python harness/roundtrip.py                           # round trips through CQL2-JSON and CartoSym-JSON (reports/roundtrip.md)
uv run python -m cartosym_draft.gallery gallery/index.html   # all pages, the home page and the render kits (about a minute)
uv run python -m cartosym_draft.doc_examples                 # document figures, JSON and AsciiDoc, written into the spec checkout (about 12 minutes)
uv run python tools/build_renders_walkthrough.py             # gallery/pr192-renders-walkthrough.html
uv run --with antlr4-tools python tools/check_grammar.py     # the spec's CartoSym-CSS grammar (needs Java)
```

The schema tests have their own instructions in [`schema-tests/README.md`](schema-tests/README.md).

The playground loads the renderer's Python files over HTTP, so open it from GitHub Pages or a local web server (`python -m http.server` in the repository root, then http://localhost:8000/gallery/playground.html), not as a file.

To fetch the data again:

```
uv run --with tifffile --with numpy python tools/fetch_rondane.py
uv run --with rasterio --with numpy python tools/fetch_sentinel2.py
uv run --no-project --with pyogrio --with geopandas python tools/fetch_n50.py
uv run --no-project --with rasterio --with tifffile --with numpy python tools/fetch_hires.py
```

`extract_requirements.py` reads whatever is checked out in the spec checkout it is given. The current snapshot is `main` at fefe225, taken from a detached worktree of `origin/main` (`git worktree add --detach ../cartographic-symbology-main origin/main`). Run it again after the requirements change.

- **pycartosym** 0.6.5 is installed from PyPI. It converts the CartoSym-CSS examples and the CQL2-Text test inputs.
- **libCartoSym** comes from the `cartosym` 0.0.1 and `ecrt` 0.0.6 packages (built in November 2025) by default. To test a build from source instead, set `CS_CANIF` to the `cs-canif` executable and `CS_CANIF_LIBDIRS` to the folders with its libraries; `REPORT_DIR` and `LIBCARTOSYM_LABEL` set where the report goes and how libCartoSym is described in it.
- **Latest libCartoSym:** the [`libcartosym-main`](.github/workflows/libcartosym-main.yml) workflow builds the latest eC and libCartoSym from GitHub on Ubuntu (as their `fetchAndBuild.sh` does), runs the harness against that `cs-canif`, and commits the report to [`reports/libcartosym-main/`](reports/libcartosym-main/). It runs weekly, when the harness or cases change, and on demand. The requirements page reads its results.
- **pycartosym's test suite** can run the expression cases too: `tools/export_pycartosym_cases.py` writes them to `tests/data/cartosym_draft_cases.json` in a pycartosym checkout next to this one, with the CQL2-Text, the expected CQL2-JSON and the `disputed` note of each case, but not the `expect` values.
- **Cases with their own CQL2-JSON** give it to the draft renderer directly, so its results do not depend on pycartosym's parser.

## Data

The judgement calls and the figures use small datasets of one area, Rondane in Norway, 45 × 30 km ([`sample_data.py`](src/cartosym_draft/sample_data.py)):

- **Elevation:** real elevation from Kartverket's national terrain model (NHM DTM, via the Geonorge WCS), from about 290 to 2160 m, averaged to 150 m cells by [`tools/fetch_rondane.py`](tools/fetch_rondane.py) and stored in [`rondane_data.py`](src/cartosym_draft/rondane_data.py). Used by the elevation cards (examples 5, 8 and 9, and gamma), drawn 900 px wide at 1:178 571, inside the examples' `viz.sd < 200000`; they stretch the examples' color map (0–2500 m) to 500–2000 m, keeping its colors, so the whole ramp shows. Elevation data © Kartverket, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Sentinel-2 L2A:** a scene over the same area from 2 August 2024 (`S2B_T32VNP_20240802T104620_L2A`), used by examples 6 and 7 in the cards, with a few clouds that example 6's SCL rules hide. From Element84's Earth Search (`sentinel-2-c1-l2a`), reprojected to EPSG:25833 and averaged to 150 m cells (the scene classification takes each cell's most common class) by [`tools/fetch_sentinel2.py`](tools/fetch_sentinel2.py), and stored in [`sentinel2_data.py`](src/cartosym_draft/sentinel2_data.py). Since 2022, L2A digital numbers carry a +1000 offset; the tool removes it, so the bands are reflectance × 10 000, as the examples assume. Contains modified Copernicus Sentinel data 2024.
- **For the document figures:** N50 Kartdata vector layers (land cover, rivers, roads, cabins, place names and more) clipped by [`tools/fetch_n50.py`](tools/fetch_n50.py) into [`data/rondane/`](src/cartosym_draft/data/rondane/), with coordinates to 0.1 m and road and river pieces that meet end to end with equal properties joined into one line. [`tools/fetch_hires.py`](tools/fetch_hires.py) adds the elevation and a cloud-free Sentinel-2 scene of 1 September 2024 (`S2B_T32VNP_20240901T104944_L2A`) at 50 m cells, and, for each panel at 1:100 000 or larger, the elevation at about one cell per screen pixel (2 to 28 m, from the 1 m terrain model). The playground keeps the 150 m grids. Map data © Kartverket, CC BY 4.0; contains modified Copernicus Sentinel data 2024.
- **Pyramids** (synthetic, 15 × 10 km with 100 m cells): three square pyramids, used where the direction of the light must be easy to see.

In the render kits, the data is placed in ETRS89 / UTM zone 33N (EPSG:25833): the Rondane data at its real position, the pyramids near Oslo. Vector layers are GeoJSON, coverage bands ESRI ASCII grids with `.prj` files. Each file is named after its layer, which the styles' `dataLayer.id` selectors match. `view.json` gives the extent, size and scale denominator, and the attribution where a kit contains Kartverket or Copernicus data.

The coverage styles of the cards are the spec's examples 5 to 9 ([`examples/`](src/cartosym_draft/examples/)), unchanged except where a card says otherwise.

## Limitations

- **Text** is measured with Pillow and the system's fonts where they are found (Arial on Windows), and otherwise estimated at 0.6 em per character; labels along lines are straight, rotated text.
- **Conic gradients** are approximated with wedges.
- **Part 2 has no working JSON schema**, so gradient fills are not validated beyond what the Part 1 schema allows.
- **The independent renderers are all Claude sessions** (Opus, Sonnet and Haiku). They were isolated from this repository and from each other, but they are not independent in the way two implementers from different organizations would be.
- **No render kit has been run through another existing renderer**, such as libCartoSym's.

## History

The repository started on 15 October 2026 as a check of the draft requirements in [#133](https://github.com/opengeospatial/cartographic-symbology/pull/133), which Jérôme St-Louis merged on 13 November 2026. It has since been used to prepare and check the pull requests that follow it.

| Pull request | What this repository added |
|---|---|
| [#133](https://github.com/opengeospatial/cartographic-symbology/pull/133) Part 1 requirements (merged 13 November) | The draft renderer, the judgement calls with their decision matrix, the requirements page, the test harness, and the walkthrough for the SWG meeting of 13 November. |
| [#188](https://github.com/opengeospatial/cartographic-symbology/pull/188) CartoSym-JSON schema fixes (merged 20 November) | The [schema tests](schema-tests/), run with three validators. |
| [#190](https://github.com/opengeospatial/cartographic-symbology/pull/190) data types (merged 20 November) | Harness cases that check that `ceil`, `floor` and `round` return an integer. |
| [#192](https://github.com/opengeospatial/cartographic-symbology/pull/192) renders in the Part 1 document (merged 20 November) | The figures, CartoSym-JSON and AsciiDoc of the document's 11 examples, and 20 gallery maps kept outside the document; the independent renders and the log of wording decisions; the #192 walkthrough. |
| [#196](https://github.com/opengeospatial/cartographic-symbology/pull/196) `random()` in the CartoSym-CSS grammar (merged 20 November) | Grammar cases for empty function calls in [`cases/grammar/`](cases/grammar/). |
| [#231](https://github.com/opengeospatial/cartographic-symbology/pull/231) requirement vignettes (merged 20 November) | A vignette under each requirement a map can show: 64 vignettes for 63 of the 125 Part 1 requirements. |
| [#234](https://github.com/opengeospatial/cartographic-symbology/pull/234) CartoSym-JSON links (merged 21 November) | The examples of the CartoSym-CSS clause link their CartoSym-JSON. |
| [#233](https://github.com/opengeospatial/cartographic-symbology/pull/233) Annex C rendering passes (open) | Examples 12 and 13 on Rondane data, and rendering passes in the draft renderer. |
| [#212](https://github.com/opengeospatial/cartographic-symbology/issues/212) figures and test cases for passes (issue) | The rendering-pass cases and their render kits. |

**Findings from the review of #133.** The full list, with a proposed resolution for each, is the decision matrix. The most important:

- **The spec's NDVI example (7) needs real division.** With integer Sentinel-2 bands, integer division makes every NDVI value 0. Jérôme confirmed that `/` is real-valued and `div` is integer division, as in CQL2.
- **`hillShading.factor` was undefined in practice.** Examples 8 and 9 gave no usable result under the draft's first reading. Jérôme explained it: `factor` multiplies the horizontal components of the terrain normal, and the shade is the dot product with the sun direction (0 to 1). The requirements and the renderer now do this.
- **Example 6 (`colorChannels: B04 B03 B02`) rendered all white**: nothing defined how band values become 0..1 color components. The example now scales the bands in the style (`B04 / 2500`); #150 is about which data the examples should assume.
- **The default Marker** (clause 7) puts a white dot on every point, line vertex and polygon centroid of a style that sets no marker. Jérôme confirmed this is intended; a typical style unsets it for lines and polygons (`marker: null`), and the document now says so. Drawing it at points only is proposed in #241.
- **The JSON schema rejected colors given as expressions, and empty arrays**, because its `oneOf` branches overlapped. #188 fixed this; the schema tests show 0 wrong outcomes on it with all three validators.

**Findings from the renders work (#192).** Six independent renderers written from the requirement text split on several points that change the picture: which way `y` in a Graphic position points, what `dashOffset` measures, whether centre lines are drawn per feature or after all main strokes, how coverages are resampled, and more. #192 proposed a reading for each (W1 to W17 in [`wording-decisions.md`](reports/wording-decisions.md)), and three verification runs on the tightened text followed the new wording on every point. Jérôme's replies on #192 changed several of them before it was merged; they are in the #192 walkthrough and at the end of the wording log.

**Implementations.** libCartoSym `main` went from 50 of 117 cases (the `cartosym` pip package of November 2025) to every case it runs, after Jérôme's fixes to the issues opened from the harness (ecere/libCartoSym#5 to #9, #11 and #12, and NULL handling). The document figures also found pycartosym conversion gaps (`dashOffset`, dash units, identifiers in `placement`, hex Dot colors), fixed in 0.6.5, which this repository pins; the ones still open are worked around in `PYCARTOSYM_GAPS` in `doc_examples.py`.

## About

Made by Henrik Gulliksen Schüller, Part 1 editor, to support the review of #133 and the pull requests after it. Developed with Claude (Anthropic) as a coding assistant; the approach, the choices and the review of the results are the author's. The findings are proposals for the Cartographic Symbology SWG, not decisions.

## Credits

- The coverage examples in [`src/cartosym_draft/examples/`](src/cartosym_draft/examples/) are the spec's own examples 5 to 9 from [opengeospatial/cartographic-symbology](https://github.com/opengeospatial/cartographic-symbology), converted to CartoSym-JSON where needed.
- The requirement text and JSON schema snapshots (`requirements.json`, `CartoSym-JSON.schema.json`) come from the same repository, `main` (see Running it).
- The named-color table in [`colors.py`](src/cartosym_draft/colors.py) was generated from [pycartosym](https://github.com/maxcollombin/pycartosym)'s web color table (MIT License, © Maxime Collombin). The values are the CSS named colors.
- The elevation data and the N50 map data are from Kartverket: © Kartverket, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The Sentinel-2 scenes contain modified Copernicus Sentinel data 2024, obtained through Element84's [Earth Search](https://element84.com/earth-search/).
- libCartoSym ([ecere/libCartoSym](https://github.com/ecere/libCartoSym)) is used as an independent implementation in the test harness, through the `cartosym` and `ecrt` packages.

## License

MIT, see [`LICENSE`](LICENSE). This covers the code; the Kartverket and Sentinel-2 data keep their own terms (see Credits).
