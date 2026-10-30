# cartosym-draft-check

Checks the draft requirements for OGC Cartographic Symbology 2.0 Part 1 (and Part 2 gradient fills) proposed in [opengeospatial/cartographic-symbology#133](https://github.com/opengeospatial/cartographic-symbology/pull/133). The checks use an implementation, rendered output, and comparison with libCartoSym.

Requirements written without an implementation are hard to get right. This repository implements the draft, renders every place where the spec text leaves a behavior open, and runs the expression requirements through independent implementations. The goal is to show which requirements hold up, which are open questions, and where the spec's own examples disagree with the draft.

## Contents

| | Where | What it is |
|---|---|---|
| **Render gallery** | [`gallery/index.html`](gallery/index.html) | For decisions. A decision matrix with a proposed resolution for each question, then 23 cards, one per judgement call: the requirement text, the same map rendered with the draft's choice and the alternatives, and sources. Start here. |
| **Requirements** | [`gallery/requirements.html`](gallery/requirements.html) | For verification. All 135 requirements in the PR, plus its one recommendation and one permission, each with its text, how it is checked and a link to the evidence. Straightforward visual requirements get one of 16 sample renders, with a "Check" line saying what to look for. |
| **Playground** | [`gallery/playground.html`](gallery/playground.html) | Pick any card or sample, edit its style or switch between its variants, and see it rendered again. The draft renderer runs in the browser through [Pyodide](https://pyodide.org). |
| **Render kits** | [`gallery/kit/`](gallery/kit/), [`gallery/kit.zip`](gallery/kit.zip) | The style, data and view settings of every card and sample, to render the same maps with another renderer. |
| **Draft renderer** | [`src/cartosym_draft/`](src/cartosym_draft/) | A CQL2 expression evaluator and SVG renderer that does what the draft requirements say. Each open behavior is a switchable option ([`options.py`](src/cartosym_draft/options.py)). |
| **Test harness** | [`harness/`](harness/), [`cases/`](cases/) | 93 test cases whose expected values are taken from the requirement text. Each case is run through libCartoSym, pycartosym and the draft renderer. |
| **Test report** | [`reports/report.md`](reports/report.md), [`reports/results.json`](reports/results.json) | Results per requirement and implementation, with libCartoSym from the `cartosym` pip package. [`reports/libcartosym-main/`](reports/libcartosym-main/) has the same against the latest libCartoSym from GitHub. |

Three implementations are involved, and they do different things. The **draft renderer** (this repository) evaluates expressions, resolves the style for each feature and draws the map. **libCartoSym** (Ecere) reads and writes CartoSym-CSS, CartoSym-JSON, SLD/SE and Mapbox styles, and evaluates expressions and styles for a feature (`cs-canif eval`); the test harness compares its results with what the draft says. **pycartosym** (Maxime Collombin) converts between CartoSym-CSS, CartoSym-JSON, SLD/SE and MapLibre styles; the draft renderer uses it to read CartoSym-CSS and CQL2-Text, and the test harness checks its conversion to CQL2-JSON.

The draft renderer is a discussion tool, not a reference implementation. Because it implements the draft itself, it can show what each choice looks like, but not whether that choice is the intended one: that is for the SWG to decide. Comparing with an independent renderer shows whether others read the requirements the same way, which is what the render kits are for.

## How it fits together

```text
[ 1. INPUTS ]
PR #133 branch ──────────────> tools/extract_requirements.py ──┬──> requirements.json
(../cartographic-symbology)                                    └──> CartoSym-JSON.schema.json
Kartverket DTM, Sentinel-2 ──> tools/fetch_*.py ──────────────────> rondane_data.py, sentinel2_data.py

[ 2. TEST HARNESS ]  harness/run.py
cases/*.yaml ──┬──> libCartoSym     (cs-canif eval)          ──┐
               ├──> pycartosym      (CQL2-Text → CQL2-JSON)  ──┼──> reports/report.md
               └──> draft renderer  (evaluate)               ──┘    reports/results.json

[ 3. GALLERY ]  python -m cartosym_draft.gallery
draft renderer      ──┬──> gallery/index.html          decision matrix, 23 cards
+ examples 5–9        ├──> gallery/requirements.html   135 requirements, 16 samples
+ sample data         ├──> gallery/kit/, kit.zip       style, data and view per card and sample
+ requirements.json   └──> gallery/playground.html     the draft renderer in the browser (Pyodide)
+ results.json

[ 4. CI ]  .github/workflows/libcartosym-main.yml (weekly, and when the harness or cases change)
latest eC + libCartoSym (Ubuntu) ──> harness/run.py ──> reports/libcartosym-main/
```

The requirement text and schema are snapshots of the PR branch, so run `extract_requirements.py` again after the requirements change. The harness and the gallery run separately, except that the requirements page shows the harness results from `results.json`, so run the harness first. The gallery build validates every style against the schema snapshot.

```text
cartosym-draft-check/
├── src/cartosym_draft/   # the draft renderer and the gallery build
│   ├── evaluate.py       #   CQL2-JSON expressions
│   ├── cascade.py        #   styling rules → the symbolizer for each feature
│   ├── render.py         #   vector features → SVG
│   ├── coverage.py       #   coverages and hill shading → PNG
│   ├── options.py        #   the switchable judgement calls
│   ├── gallery.py        #   cards; also samples.py, requirements_page.py, playground.py, kit.py
│   └── examples/         #   the spec's coverage examples 5 to 9
├── harness/              # run.py, and adapters.py for the three implementations
├── cases/                # test cases, with expected values from the requirement text
├── reports/              # test reports; libcartosym-main/ is written by CI
├── gallery/              # the generated pages and render kits, served by GitHub Pages
└── tools/                # requirement snapshot, Rondane and Sentinel-2 fetchers
```

## Reading the gallery

- <kbd>draft</kbd> marks the variant the draft requirement text chooses.
- <kbd>open in draft</kbd> marks a card where the draft does not settle the question. Its first variant, labelled "draft renderer's choice", is the proposed resolution in the decision matrix.
- A note under a variant says what to look for where the result is the point (for example, a casing drawn over the stroke hides it).

Every style in the gallery and the samples is validated against the PR's CartoSym-JSON schema when the gallery is built; the build stops on an invalid style.

## What is covered

PR #133 has 135 requirements: 109 in Part 1's requirements files, 20 in the core class (clause 7) and 6 for Part 2 gradient fills. It also has one recommendation (colorMap interpolation) and one permission (the Image alpha test). Every requirement is checked in at least one way; [`requirements.html`](gallery/requirements.html) lists how. Not implemented: the alpha-test permission, the visualization time and `capabilities` system identifiers, and label `maxSpacing`. CSCSS `.include` and variables are checked through pycartosym's conversion, which since 0.5.0 gives the draft's `$include`, `$variables` and `$ref` form.

- **Rendered:** vector styling (fill, stroke, units, markers, Dot, Text, Image), casing, dashes, hatches, stipples, dot patterns, font outlines, labels, coverage styling, hill shading and Part 2 gradients: judgement calls as gallery cards, the rest as samples.
- **Tested:** arithmetic, math, text relation and manipulation, array relations, conditionals, right-hand operands, function calls, variables, and core literals, arrays and identifiers, in the test harness.
- **Encoding only:** CSCSS and CartoSym-JSON encodings. The spec's examples are converted with pycartosym and parsed by libCartoSym.

## Main findings

The full list, with a proposed resolution for each, is the decision matrix at the top of the gallery. The most important:

- **The spec's NDVI example (7) needs real division.** With integer Sentinel-2 bands, integer division makes every NDVI value 0; libCartoSym does this today. Jérôme confirmed that `/` is real-valued and `div` is integer division, as in CQL2.
- **`hillShading.factor` was undefined in practice.** Examples 8 and 9 (`factor: 56`) gave no usable result under the draft's reading. Jérôme explained it: `factor` multiplies the horizontal components of the terrain normal, and the shade is the dot product with the sun direction (0 to 1). The normal is computed between the DEM samples being rendered, so the `factor` that suits a style depends on the resolution. The PR and the renderer now do this.
- **Example 6 (`colorChannels: B04 B03 B02`) rendered all white**: nothing defined how band values become 0..1 color components. Following Jérôme, the PR now scales the bands in the style (`B04 / 2500`).
- **The default Marker** (clause 7) puts a white dot on every point, line vertex and polygon centroid of a style that sets no marker. Jérôme confirmed this is intended, so every feature is visible, and a typical base style unsets it for lines and polygons (`marker: null`); the PR now says so. Still open: the JSON schema rejects `marker: null` and `marker: { elements: [] }` (a tested fix is proposed in #143). The Dot defaults gave a size and color the Dot class did not have; as agreed with Jérôme, Dot now has `size` and `color`, the same values as its stroke's width and color (#144).
- **The JSON schema (on main) rejects colors given as expressions, and empty arrays**, because its `oneOf` branches overlap.

The open points are recorded as TODO(review) notes in PR #133 (the schema issue is outside the PR). In the test harness the draft renderer passes all 93 cases and libCartoSym 36 of the 85 it can run. pycartosym converts all 55 expressions that have an expected CQL2-JSON to exactly that JSON.

## Data

The gallery uses small datasets ([`sample_data.py`](src/cartosym_draft/sample_data.py)):

- **Rondane:** real elevation of Rondane, Norway, 45 × 30 km with 150 m cells, from about 290 to 2160 m (the Rondane massif and the valleys around it), used by all the elevation cards (examples 5, 8 and 9, and gamma), so they can be compared with renders of real terrain. These cards are drawn 900 px wide, which keeps the scale at 1:178 571, inside the examples' `viz.sd < 200000`, and stretch the examples' color map (0–2500 m) to 500–2000 m, keeping its colors, so the whole ramp shows and the valley floors and summits fall outside it. From Kartverket's national terrain model (NHM DTM, via the Geonorge WCS), averaged from 30 m to 150 m cells by [`tools/fetch_rondane.py`](tools/fetch_rondane.py) and stored in [`rondane_data.py`](src/cartosym_draft/rondane_data.py). Elevation data © Kartverket, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Sentinel-2 L2A:** a real scene over the same 45 × 30 km of Rondane, from 2 August 2024 (`S2B_T32VNP_20240802T104620_L2A`), used by examples 6 and 7, with a few clouds that example 6's SCL rules hide. From Element84's Earth Search (`sentinel-2-c1-l2a`, cloud-optimised GeoTIFFs on AWS), reprojected to EPSG:25833 and averaged to 150 m cells (the scene classification takes each cell's most common class) by [`tools/fetch_sentinel2.py`](tools/fetch_sentinel2.py), and stored in [`sentinel2_data.py`](src/cartosym_draft/sentinel2_data.py). Since 2022, L2A digital numbers carry a +1000 offset; the tool removes it, so the bands are reflectance × 10 000, as the examples assume. Contains modified Copernicus Sentinel data 2024.
- **Pyramids** (synthetic, 15 × 10 km with 100 m cells): three square pyramids, used where the direction of the light must be easy to see.

In the render kits, the data is placed in ETRS89 / UTM zone 33N (EPSG:25833): the Rondane data at its real position, the pyramids near Oslo. Vector layers are GeoJSON, coverage bands ESRI ASCII grids with `.prj` files. Each file is named after its layer, which the styles' `dataLayer.id` selectors match. `view.json` gives the extent, size and scale denominator, and the attribution where a kit contains Kartverket or Copernicus data.

The coverage styles are the spec's own examples 5 to 9 ([`examples/`](src/cartosym_draft/examples/)), unchanged except where a card says otherwise.

## Running it

```
uv sync
uv run python tools/extract_requirements.py         # requirement text and JSON schema from ../cartographic-symbology
uv run python harness/run.py                        # test report; the requirements page reads its results
uv run python -m cartosym_draft.gallery gallery/index.html   # gallery, requirements page and render kits
```

The playground loads the renderer's Python files over HTTP, so open it from GitHub Pages or a local web server (`python -m http.server` in the repository root, then http://localhost:8000/gallery/playground.html), not as a file.

To fetch the Rondane data again: `uv run --with tifffile --with numpy python tools/fetch_rondane.py` and `uv run --with rasterio --with numpy python tools/fetch_sentinel2.py`.

`extract_requirements.py` reads the checked-out branch of `../cartographic-symbology` (the PR branch, `requirements-placeholders`). Run it again after the requirements change.

- **pycartosym** 0.6.1 is installed from PyPI. It converts the CSCSS examples and converts the CQL2-Text test inputs to CQL2-JSON.
- **libCartoSym** comes from the `cartosym` 0.0.1 and `ecrt` 0.0.6 packages (built in November 2025) by default. To test a build from source instead, set `CS_CANIF` to the `cs-canif` executable and `CS_CANIF_LIBDIRS` to the folders with its libraries; `REPORT_DIR` and `LIBCARTOSYM_LABEL` set where the report goes and how libCartoSym is described in it.
- **Latest libCartoSym:** the [`libcartosym-main`](.github/workflows/libcartosym-main.yml) workflow builds the latest eC and libCartoSym from GitHub on Ubuntu (as their `fetchAndBuild.sh` does), runs the harness against that `cs-canif`, and commits the report to [`reports/libcartosym-main/`](reports/libcartosym-main/). It runs weekly, when the harness or cases change, and on demand.
- **pycartosym's test suite** runs the expression cases too: `tools/export_pycartosym_cases.py` writes them to `tests/data/cartosym_draft_cases.json` in a pycartosym checkout next to this one, with the CQL2-Text, the expected CQL2-JSON and the `disputed` note of each case, but not the `expect` values. Export them again after the cases change, and open a pull request to pycartosym.
- **Cases with their own CQL2-JSON** give it to the draft renderer directly, so its results do not depend on pycartosym's parser. pycartosym 0.4.1 converted 30 of these expressions wrongly (string literals, negative numbers, arrays, conditionals, `^`); 0.5.0 fixed all but a string literal on its own (`'abc'`, read as a property), and 0.6.0 fixed that one.

## Limitations

- **Text** is laid out without font metrics, and labels along lines are straight, rotated text.
- **Conic gradients** are approximated with wedges.
- **Part 2 has no JSON schema**, so gradient fills are not validated beyond what the Part 1 schema allows.
- **The visualization time and `capabilities` system identifiers, and label `maxSpacing`,** are not implemented.

## About

Made by Henrik Gulliksen Schüller to support the review of PR #133. Developed with Claude (Anthropic) as a coding assistant; the approach, the choices and the review of the results are the author's. The findings are proposals for the Cartographic Symbology SWG, not decisions.

## Credits

- The coverage examples in [`src/cartosym_draft/examples/`](src/cartosym_draft/examples/) are the spec's own examples 5 to 9 from [opengeospatial/cartographic-symbology](https://github.com/opengeospatial/cartographic-symbology), converted to CS-JSON where needed.
- The requirement text and JSON schema snapshots (`requirements.json`, `CartoSym-JSON.schema.json`) come from the same repository, branch `requirements-placeholders`.
- The named-color table in [`colors.py`](src/cartosym_draft/colors.py) was generated from [pycartosym](https://github.com/maxcollombin/pycartosym)'s web color table (MIT License, © Maxime Collombin). The values are the CSS named colors.
- The Rondane elevation data ([`rondane_data.py`](src/cartosym_draft/rondane_data.py)) is from Kartverket's national terrain model: elevation data © Kartverket, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The Sentinel-2 scene ([`sentinel2_data.py`](src/cartosym_draft/sentinel2_data.py)) contains modified Copernicus Sentinel data 2024, obtained through Element84's [Earth Search](https://element84.com/earth-search/).
- libCartoSym ([ecere/libCartoSym](https://github.com/ecere/libCartoSym)) is used as an independent implementation in the test harness, through the `cartosym` and `ecrt` packages.

## License

MIT, see [`LICENSE`](LICENSE). This covers the code; the Rondane elevation and Sentinel-2 data keep their own terms (see Credits).
