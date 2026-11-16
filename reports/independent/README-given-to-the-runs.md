# Independent rendering from the requirement text

This folder is a closed test. Its question is whether the requirement text of OGC Cartographic Symbology 2.0 Part 1 (draft) is precise enough that an implementation written only from that text renders the same maps as another one.

## What is here

- `spec/1-core/` holds the draft standard's text: `sections/*.adoc` are the clauses (clause 7 is the core class, clause 8 vector, 9 coverage and hill shading, 10 labels and font outlines, 11 dashes and casing, 12 hatches, dot patterns and stipples, 16 the JSON encoding, 17 the CSS encoding), `requirements/*.adoc` holds the requirement classes, and `schemas/` holds the CartoSym-JSON schema. Figures are not included.
- `cases/<case>/` holds one test case each:
  - `style.cs.json` is the style in CartoSym-JSON. Render from this. `style.cscss` is the same style in CartoSym-CSS, for reading only.
  - `<Layer>.geojson` are vector layers in EPSG:25833 (metres). A layer's identifier (`dataLayer.identifier` / `dataLayer.id`) is the file name without the extension. Properties are as in the file; `validDate` is an ISO date.
  - `<Layer>.<band>.asc` are coverage bands as ESRI ASCII grids in EPSG:25833. Bands with the same layer name share one grid; a cell's properties are its band names (for example `elevation`).
  - `view-N.json` describes each map to render: `bbox` (EPSG:25833), `width` and `height` in pixels, `scaleDenominator`, `pixelSize_mm` (0.28 mm, the standard pixel), the layers in drawing order, the visualization date and time interval, and the background (white).
  - `icons/` holds images that styles refer to by `path` (relative to the case folder, or `../icons/` from it).

## The task

1. Write a renderer from the text in `spec/` only, in Python. It reads a case's `style.cs.json`, the data and each `view-N.json`, and writes `out/<case>-<N>.png` at exactly `width` × `height` pixels. Use numpy and Pillow, run with `uv run --no-project --with numpy --with pillow python ...`. You may use any other general-purpose library (for example shapely, or an SVG rasterizer), but nothing that implements Cartographic Symbology, SLD/SE or CQL2 for you.
2. Every time the text does not tell you what to draw — or could be read in more than one way — make a choice, implement it, and write it down in `notes.md`: the requirement identifier (or clause and table), the exact words that leave the choice open, the readings you considered, and which one you implemented. This list matters more than the images. Also note anything you found contradictory, or used but undefined.
3. Render all 20 cases.

## Rules

- Read only files inside this folder. Do not open, search or import anything outside it: no other repository, package or website about Cartographic Symbology, pycartosym, libCartoSym or any existing renderer of this standard.
- Do not look for or guess at reference images; there are none here.
- Keep your code in `renderer/`, your images in `out/`, and your notes in `notes.md`.
