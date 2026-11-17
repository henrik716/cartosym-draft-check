# cartosym-draft-check

Tools and evidence for the requirements of OGC Cartographic Symbology 2.0 Part 1 (and the Part 2 gradient fills) in [opengeospatial/cartographic-symbology](https://github.com/opengeospatial/cartographic-symbology): a renderer and expression evaluator that follow the requirement text, a test harness that runs the same expressions through libCartoSym and pycartosym, tests for the grammar and the JSON schemas, and the figures of the Part 1 document.

Requirements written without an implementation are hard to get right. This repository implements them, renders every place where the text leaves a behavior open, and checks whether readers who only have the text would draw the same maps. The goal is to show which requirements hold up, which are open questions, and where the document disagrees with itself.

It started on 15 October 2026 as a check of the draft requirements in [#133](https://github.com/opengeospatial/cartographic-symbology/pull/133), which Jérôme St-Louis merged on 13 November 2026. It is now used to prepare and check the pull requests that follow it.

## Pull requests it supports

| Pull request | What this repository adds |
|---|---|
| [#133](https://github.com/opengeospatial/cartographic-symbology/pull/133) Part 1 requirements (merged) | The draft renderer, the gallery with its decision matrix, the requirements page, the test harness, and the [walkthrough](gallery/pr133-requirements-walkthrough.html) for the SWG meeting of 13 November. |
| [#188](https://github.com/opengeospatial/cartographic-symbology/pull/188) CartoSym-JSON schema fixes | The [schema tests](schema-tests/): 663 documents with expected outcomes, run with three validators. |
| [#190](https://github.com/opengeospatial/cartographic-symbology/pull/190) data types | Harness cases that check that `ceil`, `floor` and `round` return an integer. |
| [#192](https://github.com/opengeospatial/cartographic-symbology/pull/192) renders in the Part 1 document | The figures, CartoSym-JSON and AsciiDoc of the document's 11 examples, 21 requirement vignettes and 20 gallery maps kept outside the document; the independent renders and the [log of wording decisions](reports/wording-decisions.md); the [renders walkthrough](gallery/pr192-renders-walkthrough.html). |
| [#196](https://github.com/opengeospatial/cartographic-symbology/pull/196) `random()` in the CartoSym-CSS grammar | Grammar cases for empty function calls in [`cases/grammar/`](cases/grammar/). |

## Pages

The generated pages are published with GitHub Pages; the links in the tables below go to their source.

- [Gallery](https://henrik716.github.io/cartosym-draft-check/gallery/index.html), [Requirements](https://henrik716.github.io/cartosym-draft-check/gallery/requirements.html) and [Playground](https://henrik716.github.io/cartosym-draft-check/gallery/playground.html)
- [Walkthrough of #133](https://henrik716.github.io/cartosym-draft-check/gallery/pr133-requirements-walkthrough.html): the Part 1 requirements, as prepared for the SWG meeting of 13 November 2026
- [Walkthrough of #192](https://henrik716.github.io/cartosym-draft-check/gallery/pr192-renders-walkthrough.html): the examples and figures in the Part 1 document, and the wording checked with independent renderers

The walkthroughs used to be `walkthrough.html` and `renders-walkthrough.html`; those addresses redirect to the new ones.

## Contents

**For the Part 1 document**

| | Where | What it is |
|---|---|---|
| **Document figures** | [`doc_examples.py`](src/cartosym_draft/doc_examples.py) | Renders the document's examples on Rondane data and writes, into a spec checkout, each example's render, its CartoSym-JSON (converted from the CartoSym-CSS with pycartosym, renaming `centerLine` to `center` until #188) and an AsciiDoc block with the render above the CSS and JSON. The requirement figures are vignettes: rows of small panels that each change one value of the style. Every JSON is validated against the spec's schema. |
| **Independent renders** | [`reports/independent/`](reports/independent/) | Six renderers and three expression evaluators, each written by a fresh Claude session from the requirement text alone, and three more renderers on the tightened text. Their notes, code, images and the pixel comparisons. |
| **Wording decisions** | [`reports/wording-decisions.md`](reports/wording-decisions.md) | For each requirement whose wording #192 tightens: the text before, how each reader rendered it, the evidence, and the reading proposed. |
| **#192 walkthrough** | [`gallery/pr192-renders-walkthrough.html`](gallery/pr192-renders-walkthrough.html) | The same record as a page for the SWG: the examples, how the wording was checked, and each change with the readers' choices. |

**For checking the requirements**

| | Where | What it is |
|---|---|---|
| **Draft renderer** | [`src/cartosym_draft/`](src/cartosym_draft/) | A CQL2 expression evaluator and SVG renderer that does what the requirements say. Each behavior that was open in the draft is a switchable option ([`options.py`](src/cartosym_draft/options.py)). |
| **Test harness** | [`harness/`](harness/), [`cases/`](cases/) | 124 test cases whose expected values come from the requirement text, run through libCartoSym, pycartosym and the draft renderer. |
| **Test report** | [`reports/report.md`](reports/report.md), [`reports/results.json`](reports/results.json) | Results per requirement and implementation, with libCartoSym from the `cartosym` pip package. [`reports/libcartosym-main/`](reports/libcartosym-main/) has the same against the latest libCartoSym from GitHub, written by CI. |
| **Grammar check** | [`tools/check_grammar.py`](tools/check_grammar.py), [`cases/grammar/`](cases/grammar/) | Generates a parser from the spec's CartoSym-CSS grammar with ANTLR and runs 38 cases and every `.cscss` example through it. |
| **Schema tests** | [`schema-tests/`](schema-tests/) | 663 CartoSym-JSON documents with expected outcomes, validated against the Part 1 and Part 3 schemas with python-jsonschema, Hyperjump and Ajv. They run against the #188 branch; the Part 2 to 4 schemas on `main` break them. |

**For discussion**

| | Where | What it is |
|---|---|---|
| **Render gallery** | [`gallery/index.html`](gallery/index.html) | A decision matrix with a proposed resolution for each question, then 23 cards, one per judgement call: the requirement text, the same map rendered with the draft's choice and the alternatives, and sources. Written for the review of #133, with the matrix kept up to date; see [Reading the gallery](#reading-the-gallery). |
| **Requirements** | [`gallery/requirements.html`](gallery/requirements.html) | All 131 requirements, 4 recommendations and 3 permissions of Part 1 and the Part 2 gradient fills, each with its text, how it is checked and a link to the evidence. Straightforward visual requirements get one of 18 sample renders, with a "Check" line saying what to look for. |
| **Playground** | [`gallery/playground.html`](gallery/playground.html) | Pick any card or sample, edit its style or switch between its variants, and see it rendered again. The draft renderer runs in the browser through [Pyodide](https://pyodide.org). |
| **Render kits** | [`gallery/kit/`](gallery/kit/), [`gallery/kit.zip`](gallery/kit.zip) | The style, data and view settings of every card and sample, to render the same maps with another renderer. |
| **#133 walkthrough** | [`gallery/pr133-requirements-walkthrough.html`](gallery/pr133-requirements-walkthrough.html) | #133 class by class, as prepared for the SWG meeting of 13 November 2026, where it was merged. A record; not updated since. |

## The implementations

Three implementations are compared, and they do different things. The **draft renderer** (this repository) evaluates expressions, resolves the style for each feature and draws the map. **libCartoSym** (Ecere) reads and writes CartoSym-CSS, CartoSym-JSON, SLD/SE and Mapbox styles, and evaluates expressions and styles for a feature (`cs-canif eval`); the test harness compares its results with what the requirements say. **pycartosym** (Maxime Collombin) converts between CartoSym-CSS, CartoSym-JSON, SLD/SE and MapLibre styles; the draft renderer uses it to read CartoSym-CSS and CQL2-Text, and the test harness checks its conversion to CQL2-JSON.

The draft renderer is a discussion tool, not a reference implementation. Because it implements the requirements itself, it can show what each choice looks like, but not whether that choice is the intended one: that is for the SWG to decide. Passing its own tests shows that it matches the text, not that the text is right. That is why the independent renderers exist: they show whether others reading the same text draw the same maps.

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

[ 3. GALLERY ]  python -m cartosym_draft.gallery
draft renderer      ──┬──> gallery/index.html          decision matrix, 23 cards
+ examples 5–9        ├──> gallery/requirements.html   138 requirements, 18 samples
+ sample data         ├──> gallery/kit/, kit.zip       style, data and view per card and sample
+ requirements.json   └──> gallery/playground.html     the draft renderer in the browser (Pyodide)
+ results.json

[ 4. DOCUMENT FIGURES ]  python -m cartosym_draft.doc_examples
spec's 1-core/examples/*.cscss ──> pycartosym + fix-ups ──> <name>.cs.json  ──┐
data/rondane/                  ──> draft renderer       ──> figures/*.jpg   ──┼──> into the spec checkout
                                                                              └──> <name>.adoc

[ 5. GRAMMAR AND SCHEMA ]
spec's .g4 files    ──> tools/check_grammar.py (ANTLR) ──> cases/grammar/css-grammar.yaml + examples
spec's JSON schemas ──> schema-tests/run.py, js/check.mjs  ──> schema-tests/out/

[ 6. CI ]  .github/workflows/libcartosym-main.yml (weekly, and when the harness or cases change)
latest eC + libCartoSym (Ubuntu) ──> harness/run.py ──> reports/libcartosym-main/
```

The independent renders and the wording log (`reports/independent/`, `reports/wording-decisions.md`) were made by hand, not by a script in this repository; `tools/build_renders_walkthrough.py` turns them into the renders walkthrough.

```text
cartosym-draft-check/
├── src/cartosym_draft/   # the draft renderer, the gallery and the document figures
│   ├── evaluate.py       #   CQL2-JSON expressions
│   ├── cascade.py        #   styling rules → the symbolizer for each feature
│   ├── render.py         #   vector features → SVG
│   ├── coverage.py       #   coverages and hill shading → PNG
│   ├── options.py        #   the switchable judgement calls
│   ├── gallery.py        #   cards; also review.py (the decision matrix), samples.py, requirements_page.py, playground.py, kit.py
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

## Reading the gallery

- <kbd>draft</kbd> marks the variant the draft requirement text chooses.
- <kbd>open in draft</kbd> marks a card where the draft does not settle the question. Its first variant, labelled "draft renderer's choice", is the proposed resolution in the decision matrix.
- A note under a variant says what to look for where the result is the point (for example, a casing drawn over the stroke hides it).

The decision matrix was written for the review of #133 and is kept up to date in [`review.py`](src/cartosym_draft/review.py): for each question, what the text says, the proposed resolution, and where it stands on GitHub on the date in its column heading, including the replies on #192. Update the rows and `MATRIX_AS_OF` together.

Every style in the gallery and the samples is validated against the snapshot's CartoSym-JSON schema when the gallery is built; the build stops on an invalid style.

## What is covered

The snapshot in [`requirements.json`](src/cartosym_draft/requirements.json) has 131 requirements (125 in Part 1, 6 for the Part 2 gradient fills), 4 recommendations and 3 permissions. Every one is checked in at least one way: 37 by a gallery card, 42 by a sample render or a document example, 62 by test cases and 12 as encodings (some in more than one way); [`requirements.html`](gallery/requirements.html) lists how.

- **Rendered:** vector styling (fill, stroke, units, markers, Dot, Text, Image), casing, dashes, hatches, stipples, dot patterns, font outlines, labels, coverage styling, hill shading and Part 2 gradients: judgement calls as gallery cards, the rest as samples and document examples.
- **Tested:** arithmetic, math, text relation and manipulation, array relations, conditionals, right-hand operands, function calls, variables, NULL, and core literals, arrays and identifiers, in the test harness.
- **Encoding only:** CartoSym-CSS and CartoSym-JSON. The document's examples are converted with pycartosym, validated against the schema, and parsed by libCartoSym and by a parser generated from the spec's grammar.

## Main findings

**From the review of #133.** The full list, with a proposed resolution for each, is the decision matrix at the top of the gallery. The most important:

- **The spec's NDVI example (7) needs real division.** With integer Sentinel-2 bands, integer division makes every NDVI value 0. Jérôme confirmed that `/` is real-valued and `div` is integer division, as in CQL2.
- **`hillShading.factor` was undefined in practice.** Examples 8 and 9 gave no usable result under the draft's first reading. Jérôme explained it: `factor` multiplies the horizontal components of the terrain normal, and the shade is the dot product with the sun direction (0 to 1). The requirements and the renderer now do this.
- **Example 6 (`colorChannels: B04 B03 B02`) rendered all white**: nothing defined how band values become 0..1 color components. The example now scales the bands in the style (`B04 / 2500`); #150 is about which data the examples should assume.
- **The default Marker** (clause 7) puts a white dot on every point, line vertex and polygon centroid of a style that sets no marker. Jérôme confirmed this is intended; a typical style unsets it for lines and polygons (`marker: null`), and the document now says so.
- **The JSON schema on `main` rejects colors given as expressions, and empty arrays**, because its `oneOf` branches overlap. #188 fixes this; the schema tests show 0 wrong outcomes on its branch with all three validators.

**From the renders work (#192).** Six independent renderers written from the requirement text of `main` split on several points that change the picture: which way `y` in a Graphic position points, what `dashOffset` measures, whether centre lines are drawn per feature or after all main strokes, how coverages are resampled, and more. #192 proposes a reading for each (W1 to W17 in [`wording-decisions.md`](reports/wording-decisions.md)), and three verification runs on the tightened text followed the new wording on every point. Jérôme replied on #192 on 16 and 17 November: he agrees with 8 of the changes, answered 6 differently (for example, `y` points down, and `min` and `max` take any number of arguments) and left 4 open. His replies are in the walkthrough and at the end of the wording log; the branch and the draft renderer do not follow them yet.

**Implementations.** In the test harness the draft renderer passes all 123 expression cases. pycartosym 0.6.5 converts every expression it is run on (117) as expected. libCartoSym passes 50 of 117 from the `cartosym` pip package (built in November 2025), and 103 of 115 from `main` at 29a5023 (CI, 16 November, before Jérôme's NULL fixes in 32d4590); Jérôme closed all the libCartoSym issues opened from the harness (ecere/libCartoSym#5 to #9, #11 and #12) on 16 November. The document figures also found pycartosym conversion gaps (`dashOffset`, dash units, identifiers in `placement`, hex Dot colors), reported to pycartosym and fixed in 0.6.5, which this repository pins.

## Data

The gallery and the figures use small datasets of one area, Rondane in Norway, 45 × 30 km ([`sample_data.py`](src/cartosym_draft/sample_data.py)):

- **Elevation:** real elevation from Kartverket's national terrain model (NHM DTM, via the Geonorge WCS), from about 290 to 2160 m, averaged to 150 m cells by [`tools/fetch_rondane.py`](tools/fetch_rondane.py) and stored in [`rondane_data.py`](src/cartosym_draft/rondane_data.py). Used by the elevation cards (examples 5, 8 and 9, and gamma), drawn 900 px wide at 1:178 571, inside the examples' `viz.sd < 200000`; they stretch the examples' color map (0–2500 m) to 500–2000 m, keeping its colors, so the whole ramp shows. Elevation data © Kartverket, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Sentinel-2 L2A:** a scene over the same area from 2 August 2024 (`S2B_T32VNP_20240802T104620_L2A`), used by examples 6 and 7 in the gallery, with a few clouds that example 6's SCL rules hide. From Element84's Earth Search (`sentinel-2-c1-l2a`), reprojected to EPSG:25833 and averaged to 150 m cells (the scene classification takes each cell's most common class) by [`tools/fetch_sentinel2.py`](tools/fetch_sentinel2.py), and stored in [`sentinel2_data.py`](src/cartosym_draft/sentinel2_data.py). Since 2022, L2A digital numbers carry a +1000 offset; the tool removes it, so the bands are reflectance × 10 000, as the examples assume. Contains modified Copernicus Sentinel data 2024.
- **For the document figures:** N50 Kartdata vector layers (land cover, rivers, roads, cabins, place names and more) clipped by [`tools/fetch_n50.py`](tools/fetch_n50.py) into [`data/rondane/`](src/cartosym_draft/data/rondane/), with coordinates to 0.1 m and road and river pieces that meet end to end with equal properties joined into one line. [`tools/fetch_hires.py`](tools/fetch_hires.py) adds the elevation and a cloud-free Sentinel-2 scene of 1 September 2024 (`S2B_T32VNP_20240901T104944_L2A`) at 50 m cells, and, for each panel at 1:100 000 or larger, the elevation at about one cell per screen pixel (2 to 28 m, from the 1 m terrain model). The playground keeps the 150 m grids. Map data © Kartverket, CC BY 4.0; contains modified Copernicus Sentinel data 2024.
- **Pyramids** (synthetic, 15 × 10 km with 100 m cells): three square pyramids, used where the direction of the light must be easy to see.

In the render kits, the data is placed in ETRS89 / UTM zone 33N (EPSG:25833): the Rondane data at its real position, the pyramids near Oslo. Vector layers are GeoJSON, coverage bands ESRI ASCII grids with `.prj` files. Each file is named after its layer, which the styles' `dataLayer.id` selectors match. `view.json` gives the extent, size and scale denominator, and the attribution where a kit contains Kartverket or Copernicus data.

The gallery's coverage styles are the spec's examples 5 to 9 ([`examples/`](src/cartosym_draft/examples/)), unchanged except where a card says otherwise.

## Running it

The tools read a checkout of the spec repository next to this one (`../cartographic-symbology`).

```
uv sync
uv run python tools/extract_requirements.py                  # requirement text and JSON schema from the spec checkout
uv run python harness/run.py                                 # test report; the requirements page reads its results
uv run python -m cartosym_draft.gallery gallery/index.html   # gallery, requirements page and render kits
uv run python -m cartosym_draft.doc_examples                 # document figures, JSON and AsciiDoc, written into the spec checkout (about 11 minutes)
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

`extract_requirements.py` reads the checked-out branch of the spec. The current snapshot is from branch `example-renders` (#192), whose requirement text has the changes in [`wording-decisions.md`](reports/wording-decisions.md); they are not merged yet. Run it again after the requirements change.

- **pycartosym** 0.6.5 is installed from PyPI. It converts the CartoSym-CSS examples and the CQL2-Text test inputs.
- **libCartoSym** comes from the `cartosym` 0.0.1 and `ecrt` 0.0.6 packages (built in November 2025) by default. To test a build from source instead, set `CS_CANIF` to the `cs-canif` executable and `CS_CANIF_LIBDIRS` to the folders with its libraries; `REPORT_DIR` and `LIBCARTOSYM_LABEL` set where the report goes and how libCartoSym is described in it.
- **Latest libCartoSym:** the [`libcartosym-main`](.github/workflows/libcartosym-main.yml) workflow builds the latest eC and libCartoSym from GitHub on Ubuntu (as their `fetchAndBuild.sh` does), runs the harness against that `cs-canif`, and commits the report to [`reports/libcartosym-main/`](reports/libcartosym-main/). It runs weekly, when the harness or cases change, and on demand.
- **pycartosym's test suite** can run the expression cases too: `tools/export_pycartosym_cases.py` writes them to `tests/data/cartosym_draft_cases.json` in a pycartosym checkout next to this one, with the CQL2-Text, the expected CQL2-JSON and the `disputed` note of each case, but not the `expect` values.
- **Cases with their own CQL2-JSON** give it to the draft renderer directly, so its results do not depend on pycartosym's parser.

## Limitations

- **Text** is measured with Pillow and the system's fonts where they are found (Arial on Windows), and otherwise estimated at 0.6 em per character; labels along lines are straight, rotated text.
- **Conic gradients** are approximated with wedges.
- **Part 2 has no working JSON schema**, so gradient fills are not validated beyond what the Part 1 schema allows.
- **The independent renderers are all Claude sessions** (Opus, Sonnet and Haiku). They were isolated from this repository and from each other, but they are not independent in the way two implementers from different organizations would be.
- **No render kit has been run through another existing renderer**, such as libCartoSym's.

## About

Made by Henrik Gulliksen Schüller, Part 1 editor, to support the review of #133 and the pull requests after it. Developed with Claude (Anthropic) as a coding assistant; the approach, the choices and the review of the results are the author's. The findings are proposals for the Cartographic Symbology SWG, not decisions.

## Credits

- The coverage examples in [`src/cartosym_draft/examples/`](src/cartosym_draft/examples/) are the spec's own examples 5 to 9 from [opengeospatial/cartographic-symbology](https://github.com/opengeospatial/cartographic-symbology), converted to CartoSym-JSON where needed.
- The requirement text and JSON schema snapshots (`requirements.json`, `CartoSym-JSON.schema.json`) come from the same repository, branch `example-renders` (see Running it).
- The named-color table in [`colors.py`](src/cartosym_draft/colors.py) was generated from [pycartosym](https://github.com/maxcollombin/pycartosym)'s web color table (MIT License, © Maxime Collombin). The values are the CSS named colors.
- The elevation data and the N50 map data are from Kartverket: © Kartverket, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The Sentinel-2 scenes contain modified Copernicus Sentinel data 2024, obtained through Element84's [Earth Search](https://element84.com/earth-search/).
- libCartoSym ([ecere/libCartoSym](https://github.com/ecere/libCartoSym)) is used as an independent implementation in the test harness, through the `cartosym` and `ecrt` packages.

## License

MIT, see [`LICENSE`](LICENSE). This covers the code; the Kartverket and Sentinel-2 data keep their own terms (see Credits).
