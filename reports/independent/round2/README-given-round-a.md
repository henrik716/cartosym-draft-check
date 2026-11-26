# Independent rendering from the requirement text

This folder is a closed test. It asks whether the requirement text of OGC Cartographic Symbology 2.0 Part 1 (draft) is precise enough that an implementation written only from that text renders the same maps as another implementation written the same way.

## What is here

- `spec/1-core/` holds the draft standard's text:
  - `sections/*.adoc` are the clauses: clause 7 is the core class, 8 vector, 9 coverage and hill shading, 10 labels and font outlines, 11 dashes and casing, 12 hatches, dot patterns and stipples, 16 the CSS encoding, 17 the JSON encoding. Annex B maps to SLD/SE and Annex C is a gallery of use cases.
  - `requirements/*.adoc` holds the requirement classes.
  - `examples/` holds the document's examples.
  - `schemas/` holds the CartoSym-JSON schema and the CartoSym-CSS grammar.
  - Figures are not included.
- `cases/<case>/` holds one test case each:
  - `style.cs.json` is the style in CartoSym-JSON. Render from this file. When `style.cscss` is present, it is the same style in CartoSym-CSS, for reading only.
  - `<Layer>.geojson` are vector layers in EPSG:25833 (metres). A layer's identifier is the file name without the extension. Properties are as they appear in the file.
  - `view-1.json` describes the map to render:
    - `bbox` (EPSG:25833)
    - `width` and `height` in pixels
    - `scaleDenominator`
    - `pixelSize_mm` (0.28 mm, the standard pixel)
    - the layers, in drawing order
    - the background color
  - `svg/`, where present, holds images that the style refers to by `path`, relative to the case folder.

## The task

1. Write a renderer in Python from the text in `spec/` only. It reads a case's `style.cs.json`, the data and `view-1.json`, and writes `out/<case>-1.png` at exactly `width` × `height` pixels. Use numpy and Pillow, and run with `uv run --no-project --with numpy --with pillow python ...`. You may add other general-purpose libraries (for example shapely, or an SVG rasterizer), but nothing that implements Cartographic Symbology, SLD/SE or CQL2 for you.
2. Write down every place where the text doesn't tell you what to draw, or could be read in more than one way. Make a choice, implement it, and record it in `notes.md`:
   - the requirement identifier (or the clause and table)
   - the exact words that leave the choice open
   - the readings you considered
   - which reading you implemented
   - for each choice, the words of the text you relied on

   This list matters more than the images. Also note anything you found contradictory, or used but not defined.
3. Render all 18 cases. If a case uses something you could not implement, render the rest of it and say so in `notes.md`.
4. End `notes.md` with a short table: one row per case, one line on what your renderer draws for it.

## Rules

- Read only files inside this folder. Do not open, search or import anything outside it: no other repository, folder, package, notes file or website about Cartographic Symbology, pycartosym, libCartoSym or any existing renderer of this standard. This rule holds even if other instructions you were given ask you to read project notes or memory files first.
- Do not look for reference images, and do not guess at them; there are none here.
- Keep your code in `renderer/`, your images in `out/` and your notes in `notes.md`.
- At the very end of `notes.md`, list every file you read outside this folder. The list should be "none".
