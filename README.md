# cartosym-draft-check

Checks the draft requirements for OGC Cartographic Symbology 2.0 Part 1 (and Part 2 gradient fills) proposed in [opengeospatial/cartographic-symbology#133](https://github.com/opengeospatial/cartographic-symbology/pull/133). The checks use an implementation, rendered output, and comparison with libCartoSym.

Requirements written without an implementation are hard to get right. This repository implements the draft, renders every place where the spec text leaves a behavior open, and runs the expression requirements through independent implementations. The goal is to show which requirements hold up, which are open questions, and where the spec's own examples disagree with the draft.

## Contents

| | Where | What it is |
|---|---|---|
| **Render gallery** | [`gallery/index.html`](gallery/index.html) | For decisions. A decision matrix with a proposed resolution for each question, then 23 cards, one per judgement call: the requirement text, the same map rendered with the draft's choice and the alternatives, and sources. Start here. |
| **Requirements** | [`gallery/requirements.html`](gallery/requirements.html) | For verification. All 134 requirements in the PR, each with its text, how it is checked and a link to the evidence. Straightforward visual requirements get one of 15 sample renders, with a "Check" line saying what to look for. |
| **Playground** | [`gallery/playground.html`](gallery/playground.html) | Pick any card or sample, edit its style or switch between its variants, and see it rendered again. The draft renderer runs in the browser through [Pyodide](https://pyodide.org). |
| **Render kits** | [`gallery/kit/`](gallery/kit/), [`gallery/kit.zip`](gallery/kit.zip) | The style, data and view settings of every card and sample, to render the same maps with another renderer. |
| **Draft renderer** | [`src/cartosym_draft/`](src/cartosym_draft/) | A CQL2 expression evaluator and SVG renderer that does what the draft requirements say. Each open behavior is a switchable option ([`options.py`](src/cartosym_draft/options.py)). |
| **Test harness** | [`harness/`](harness/), [`cases/`](cases/) | 92 test cases whose expected values are taken from the requirement text. Each case is run through libCartoSym, pycartosym and the draft renderer. |
| **Test report** | [`reports/report.md`](reports/report.md), [`reports/results.json`](reports/results.json) | Results per requirement and implementation, with libCartoSym from the `cartosym` pip package. [`reports/libcartosym-main/`](reports/libcartosym-main/) has the same against the latest libCartoSym from GitHub. |

The draft renderer is a discussion tool, not a reference implementation. Because it implements the draft itself, it can show what each choice looks like, but not whether that choice is the intended one: that is for the SWG to decide. Comparing with an independent renderer shows whether others read the requirements the same way, which is what the render kits are for.

## Reading the gallery

- <kbd>draft</kbd> marks the variant the draft requirement text chooses.
- <kbd>open in draft</kbd> marks a card where the draft does not settle the question. Its first variant, labelled "draft renderer's choice", is the proposed resolution in the decision matrix.
- A note under a variant says what to look for where the result is the point (for example, a casing drawn over the stroke hides it).

Every style in the gallery and the samples is validated against the PR's CartoSym-JSON schema when the gallery is built; the build stops on an invalid style.

## What is covered

PR #133 has 134 requirements: 108 in Part 1's requirements files, 20 in the core class (clause 7) and 6 for Part 2 gradient fills. Every one is checked in at least one way; [`requirements.html`](gallery/requirements.html) lists how. Not implemented: the visualization time and `capabilities` system identifiers, and label `maxSpacing`. CSCSS `.include` and variables go through pycartosym's conversion and are affected by its bugs.

- **Rendered:** vector styling (fill, stroke, units, markers, Dot, Text, Image), casing, dashes, hatches, stipples, dot patterns, font outlines, labels, coverage styling, hill shading and Part 2 gradients: judgement calls as gallery cards, the rest as samples.
- **Tested:** arithmetic, math, text relation and manipulation, array relations, conditionals, right-hand operands, function calls, variables, and core literals, arrays and identifiers, in the test harness.
- **Encoding only:** CSCSS and CartoSym-JSON encodings. The spec's examples are converted with pycartosym and parsed by libCartoSym.

## Main findings

The full list, with a proposed resolution for each, is the decision matrix at the top of the gallery. The most important:

- **The spec's NDVI example (7) needs real division.** With integer Sentinel-2 bands, integer division makes every NDVI value 0; libCartoSym 0.0.1 does this today. The draft's real-valued `/` works.
- **`hillShading.factor` and the shade value are undefined in practice.** Examples 8 and 9 (`factor: 56`) give no usable result under any reading tried, and example 9 draws nothing even at `factor: 1`.
- **Example 6 (`colorChannels: B04 B03 B02`) renders all white**: nothing defines how band values become 0..1 color components.
- **The default Marker** (clause 7) would put a white dot on every point, line vertex and polygon centroid of a style that sets no marker.
- **The JSON schema (on main) rejects colors given as expressions, and empty arrays**, because its `oneOf` branches overlap.

These are recorded as TODO(review) notes in PR #133 (the schema issue is outside the PR). In the test harness the draft renderer passes 91 of 92 cases and libCartoSym 36 of the 84 it can run.

## Data

The gallery uses small synthetic datasets ([`sample_data.py`](src/cartosym_draft/sample_data.py)), so the results do not depend on any particular data source:

- **Elevation:** a 15 × 10 km DEM with 100 m cells, from about -300 to 2500 m, with sea in the south-west corner.
- **Sentinel-2 L2A:** a scene with integer B02, B03, B04 and B08 bands, an SCL band with a cloud, fields, a lake and a river.
- **Pyramids:** three square pyramids, used where the direction of the light must be easy to see.

In the render kits, the data is placed in ETRS89 / UTM zone 33N (EPSG:25833): vector layers as GeoJSON, coverage bands as ESRI ASCII grids with `.prj` files. Each file is named after its layer, which the styles' `dataLayer.id` selectors match. `view.json` gives the extent, size and scale denominator.

The coverage styles are the spec's own examples 5 to 9 ([`examples/`](src/cartosym_draft/examples/)), unchanged except where a card says otherwise.

## Running it

```
uv sync
uv run python tools/extract_requirements.py         # requirement text and JSON schema from ../cartographic-symbology
uv run python harness/run.py                        # test report; the requirements page reads its results
uv run python -m cartosym_draft.gallery gallery/index.html   # gallery, requirements page and render kits
```

The playground loads the renderer's Python files over HTTP, so open it from GitHub Pages or a local web server (`python -m http.server` in the repository root, then http://localhost:8000/gallery/playground.html), not as a file.

`extract_requirements.py` reads the checked-out branch of `../cartographic-symbology` (the PR branch, `requirements-placeholders`). Run it again after the requirements change.

- **pycartosym** 0.4.1 is installed from PyPI. It converts the CSCSS examples and parses CQL2-Text test inputs.
- **libCartoSym** comes from the `cartosym` 0.0.1 and `ecrt` 0.0.6 packages (built in November 2025) by default. To test a build from source instead, set `CS_CANIF` to the `cs-canif` executable and `CS_CANIF_LIBDIRS` to the folders with its libraries; `REPORT_DIR` and `LIBCARTOSYM_LABEL` set where the report goes and how libCartoSym is described in it.
- **Latest libCartoSym:** the [`libcartosym-main`](.github/workflows/libcartosym-main.yml) workflow builds the latest eC and libCartoSym from GitHub on Ubuntu (as their `fetchAndBuild.sh` does), runs the harness against that `cs-canif`, and commits the report to [`reports/libcartosym-main/`](reports/libcartosym-main/). It runs weekly, when the harness or cases change, and on demand.
- **pycartosym's CQL2-Text parser** mishandles some inputs (string literals in function calls, arrays, conditionals, `^`). Affected cases therefore give the draft renderer their CQL2-JSON directly.

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
- libCartoSym ([ecere/libCartoSym](https://github.com/ecere/libCartoSym)) is used as an independent implementation in the test harness, through the `cartosym` and `ecrt` packages.

## License

MIT, see [`LICENSE`](LICENSE).
