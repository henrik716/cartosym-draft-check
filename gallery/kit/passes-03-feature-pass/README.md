# 03-feature-pass: feature.pass: one feature at a time

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212](https://github.com/opengeospatial/cartographic-symbology/issues/212). From maxcollombin/pycartosym [`examples/passes/03-feature-pass`](https://github.com/maxcollombin/pycartosym/tree/main/examples/passes) (MIT License, © Maxime Collombin), with `marker: null;` added to each top-level rule so that no default Dot is drawn.

The same mechanisms on a real map: Annex C examples 12 (visualization passes) and 13 (casings, `zOrder` and a
feature pass), roads and the railway at Otta, in [#233](https://github.com/opengeospatial/cartographic-symbology/pull/233).

## Style

```css
// Each feature is drawn with the black stroke, then with the white one,
// before the next feature is drawn.
[kind = 'road']
{
   marker: null;
   [feature.pass = 0] { stroke: { color: black; width: 5 px; }; }
   [feature.pass = 1] { stroke: { color: white; width: 3 px; }; }
}
```

The same with wider strokes (12 px and 8 px), `style-wide.cscss`:

```css
// 03-feature-pass with wider strokes, so that the difference from 04 shows:
// each feature is drawn with the black stroke, then with the white one,
// before the next feature is drawn.
[kind = 'road']
{
   marker: null;
   [feature.pass = 0] { stroke: { color: black; width: 12 px; }; }
   [feature.pass = 1] { stroke: { color: white; width: 8 px; }; }
}
```

## What should be drawn

Each road is drawn with its black 5 px stroke and then its white 3 px stroke, before the next road. Roads are drawn in data order (road 1, 2, 3), so at the crossing road 2's black edges cut across road 1's white line, and at the T-junction road 3's black end cuts into road 1's white line. The edges are 1 px wide, so the difference from 04 is small; `style-wide.cscss` is the same style with 12 px and 8 px strokes, where it shows clearly.

## Files

- `style.cscss`: the style in CartoSym-CSS
- `style.cs.json`: the same in CartoSym-JSON, converted from `style.cscss` with pycartosym 0.6.5 (corrected by cartosym-draft-check: capabilities.*/feature.* written as sysId)
- `style-wide.cscss`, `style-wide.cs.json`: the same with wider strokes (12 px and 8 px)
- `Roads.geojson`: the data layer `Roads` (3 features, EPSG:25833)
- `view.json`: extent (EPSG:25833), size in pixels, scale denominator and map background
- `draft-render.png`: the draft renderer, at 2 × the size of `view.json`
- `draft-render-detail.png`: the same, the crossing and the T-junction enlarged 4 ×
- `draft-render-wide.png`: the draft renderer, style `style-wide.cscss`, at 2 × the size of `view.json`
- `draft-render-wide-detail.png`: the same, the crossing and the T-junction enlarged 4 ×

Render each data layer with the style at the extent and size of `view.json`, on its background color.

## Other renderers

Pull requests to [henrik716/cartosym-draft-check](https://github.com/henrik716/cartosym-draft-check) are welcome:
`style.sld` (SLD/SE), `style.maplibre.json` or a note on why MapLibre can't express the case, and renders from
other software (e.g. `qgis-render.png`), with a line here on what it can't express.

- QGIS 4.2.3 (`qgis-render*.png`, set up and rendered by [`qgis/render_kits.py`](../../../qgis/render_kits.py)): The two strokes are line layers of one symbol at the same rendering pass, which QGIS draws one feature at a time, as `feature.pass` does. `qgis-render-wide.png` is `style-wide`.

## SLD/SE and MapLibre

Written by pycartosym (main, after 0.6.6) from the style, as `cartosym <style>.cscss --to-format sld|maplibre`. They show what the two formats do with the case; they are not renders.

- `style.cscss`, SLD/SE: `style.sld`
- `style.cscss`, MapLibre: not written, the writer refuses it: a rule with no name or data layer has no MapLibre layer id, and `feature.pass` has no mapping (a layer draws all its features)
- `style-wide.cscss`, SLD/SE: `style-wide.sld`
- `style-wide.cscss`, MapLibre: not written, the writer refuses it: a rule with no name or data layer has no MapLibre layer id, and `feature.pass` has no mapping (a layer draws all its features)
