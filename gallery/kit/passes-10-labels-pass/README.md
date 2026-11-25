# 10-labels-pass: Labels and visualization passes

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212](https://github.com/opengeospatial/cartographic-symbology/issues/212). Added for #212 from the list on [#197](https://github.com/opengeospatial/cartographic-symbology/issues/197) (cartosym-draft-check).

The same mechanisms on a real map: Annex C examples 12 (visualization passes) and 13 (casings, `zOrder` and a
feature pass), roads and the railway at Otta, in [#233](https://github.com/opengeospatial/cartographic-symbology/pull/233).

## Style

```css
// Labels on roads drawn in two visualization passes. Labels are drawn
// "as a separate pass on top of all styled vector features" (/req/labels/label):
// after the last visualization pass, or at the end of the pass that sets them?
Roads
{
   marker: null;
   label: { elements: [ Text { text: name, alignment: center middle,
                               font: { face: 'Arial', size: 11, bold: true, color: black } } ] };
   [viz.pass = 0] { stroke: { color: black; width: 12 px }; }
   [viz.pass = 1] { stroke: { color: white; width: 8 px }; }
}
```

## What should be drawn

Pass 0: the black 12 px strokes of the roads; pass 1: their white 8 px strokes; then the labels, black on the white roads, on top of everything. Each label is drawn once, although its rule applies in both passes. Road 2's label would overlap Road 1's, so only Road 1's is drawn (`/rec/labels/overlap`; both have the same priority, and Road 1 comes first).

## Open question

Labels are drawn "as a separate pass on top of all styled vector features and coverages" (`/req/labels/label`). With visualization passes, is that after the last pass, or at the end of the pass that draws the label? The label is set in a rule that doesn't test `viz.pass`, so it applies in both passes: is it drawn once?

The draft renderer draws each reading:

- Labels after the last pass (draft renderer)
- Labels at the end of their pass. The labels come with pass 0, so the white strokes of pass 1 cover them.

## Files

- `style.cscss`: the style in CartoSym-CSS
- `style.cs.json`: the same in CartoSym-JSON, converted from `style.cscss` with pycartosym 0.6.7
- `Roads.geojson`: the data layer `Roads` (3 features, EPSG:25833)
- `view.json`: extent (EPSG:25833), size in pixels, scale denominator and map background
- `draft-render.png`: the draft renderer, at 2 × the size of `view.json`
- `draft-render-detail.png`: the same, the crossing and the T-junction enlarged 4 ×
- `draft-render-labels-at-the-end-of-their-pass.png`: the draft renderer, reading: Labels at the end of their pass, at 2 × the size of `view.json`
- `draft-render-labels-at-the-end-of-their-pass-detail.png`: the same, the crossing and the T-junction enlarged 4 ×

Render each data layer with the style at the extent and size of `view.json`, on its background color.

## Other renderers

Pull requests to [henrik716/cartosym-draft-check](https://github.com/henrik716/cartosym-draft-check) are welcome:
`style.sld` (SLD/SE), `style.maplibre.json` or a note on why MapLibre can't express the case, and renders from
other software (e.g. `qgis-render.png`), with a line here on what it can't express.

- QGIS 4.2.3 (`qgis-render*.png`, set up and rendered by [`qgis/render_kits.py`](../../../qgis/render_kits.py)): QGIS draws all labels after all map layers, so it can only draw the first reading, each label once. DejaVu Sans Bold stands in for Arial, which isn't installed; the size is read as 11 pt. The labels are anchored strictly at the middle of their line: otherwise QGIS moves Road 1's label along the line, away from the crossing, and draws Road 2's as well.

## SLD/SE and MapLibre

Written by pycartosym (main, after 0.6.6) from the style, as `cartosym <style>.cscss --to-format sld|maplibre`. They show what the two formats do with the case; they are not renders.

- `style.cscss`, SLD/SE: `style.sld`
- `style.cscss`, MapLibre: not written, the writer refuses it: `Font.bold` has no MapLibre mapping
