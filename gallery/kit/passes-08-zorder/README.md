# 08-zorder: zOrder across data layers

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212](https://github.com/opengeospatial/cartographic-symbology/issues/212). From maxcollombin/pycartosym [`examples/passes/08-zorder`](https://github.com/maxcollombin/pycartosym/tree/main/examples/passes) (MIT License, © Maxime Collombin), with `marker: null;` added to each top-level rule so that no default Dot is drawn.

The same mechanisms on a real map: Annex C examples 12 (visualization passes) and 13 (casings, `zOrder` and a
feature pass), roads and the railway at Otta, in [#233](https://github.com/opengeospatial/cartographic-symbology/pull/233).

## Style

```css
// zOrder reorders the features of one pass (here, rails above roads).
Roads { marker: null; stroke: { color: gray; width: 4 px; }; zOrder: 0; }
Rails { marker: null; stroke: { color: black; width: 2 px; }; zOrder: 1; }
```

## What should be drawn

The railway (`zOrder: 1`) is drawn above the roads (`zOrder: 0`): the black 2 px line is unbroken where it crosses the gray 4 px roads (`/req/core/z-order`). `view.json` lists Rails before Roads, so without `zOrder` the roads would be drawn over the railway: only `zOrder` puts it on top. The roads join at the crossing and the T-junction, as they are all drawn before the railway.

## Files

- `style.cscss`: the style in CartoSym-CSS
- `style.cs.json`: the same in CartoSym-JSON, converted from `style.cscss` with pycartosym 0.6.5
- `Rails.geojson`: the data layer `Rails` (1 feature, EPSG:25833)
- `Roads.geojson`: the data layer `Roads` (3 features, EPSG:25833)
- `view.json`: extent (EPSG:25833), size in pixels, scale denominator and map background
- `draft-render.png`: the draft renderer, at 2 × the size of `view.json`
- `draft-render-detail.png`: the same, the crossing and the T-junction enlarged 4 ×

Render each data layer with the style at the extent and size of `view.json`, on its background color.

## Other renderers

Pull requests to [henrik716/cartosym-draft-check](https://github.com/henrik716/cartosym-draft-check) are welcome:
`style.sld` (SLD/SE), `style.maplibre.json` or a note on why MapLibre can't express the case, and renders from
other software (e.g. `qgis-render.png`), with a line here on what it can't express.

## SLD/SE and MapLibre

Written by pycartosym (main, after 0.6.6) from the style, as `cartosym <style>.cscss --to-format sld|maplibre`. They show what the two formats do with the case; they are not renders.

- `style.cscss`, SLD/SE: `style.sld`
- `style.cscss`, MapLibre: `style.maplibre.json`
