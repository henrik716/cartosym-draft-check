# 12-shared-zorder: Two data layers sharing a zOrder

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212](https://github.com/opengeospatial/cartographic-symbology/issues/212). Added for #212 from the list on [#197](https://github.com/opengeospatial/cartographic-symbology/issues/197) (cartosym-draft-check).

The same mechanisms on a real map: Annex C examples 12 (visualization passes) and 13 (casings, `zOrder` and a
feature pass), roads and the railway at Otta, in [#233](https://github.com/opengeospatial/cartographic-symbology/pull/233).

## Style

```css
// Roads and a railway in two data layers with the same zOrder, both with
// casings. "The casings of all features with the same zOrder" are drawn
// beneath "the main strokes of all those features" (/req/casing/casing):
// does that include the features of other data layers?
Roads { marker: null; stroke: { color: #f5d76e; width: 8 px; casing: { color: #6b4f1d; width: 1.5 px } }; }
Rails { marker: null; stroke: { color: white; width: 3 px; dashPattern: [ 6 px, 6 px ]; casing: { color: #333333; width: 1.5 px } }; }
```

## What should be drawn

Roads and the railway have the same `zOrder` (the default). Reading "all features" across data layers: the casings of the roads and the railway are drawn first, then the main strokes in data layer order, roads then railway. Where the railway crosses a road, its white dashes lie on the yellow road with no dark casing across it, and no road casing cuts the railway.

## Open question

`/req/casing/casing` draws "the casings of all features with the same `zOrder`" beneath "the main strokes of all those features". Does that include the features of other data layers? The painter's algorithm in clause 7 says so, but it is commented out of the published text; QGIS orders only within one map layer (kraftto on #212).

The draft renderer draws each reading:

- Casings of all data layers first (draft renderer)
- Each data layer complete before the next. As separate QGIS or MapLibre layers draw: the railway's dark casing cuts across the roads.

## Files

- `style.cscss`: the style in CartoSym-CSS
- `style.cs.json`: the same in CartoSym-JSON, converted from `style.cscss` with pycartosym 0.6.7
- `Roads.geojson`: the data layer `Roads` (3 features, EPSG:25833)
- `Rails.geojson`: the data layer `Rails` (1 feature, EPSG:25833)
- `view.json`: extent (EPSG:25833), size in pixels, scale denominator and map background
- `draft-render.png`: the draft renderer, at 2 × the size of `view.json`
- `draft-render-detail.png`: the same, the crossing and the T-junction enlarged 4 ×
- `draft-render-each-data-layer-complete-before-the-next.png`: the draft renderer, reading: Each data layer complete before the next, at 2 × the size of `view.json`
- `draft-render-each-data-layer-complete-before-the-next-detail.png`: the same, the crossing and the T-junction enlarged 4 ×

Render each data layer with the style at the extent and size of `view.json`, on its background color.

## Other renderers

Pull requests to [henrik716/cartosym-draft-check](https://github.com/henrik716/cartosym-draft-check) are welcome:
`style.sld` (SLD/SE), `style.maplibre.json` or a note on why MapLibre can't express the case, and renders from
other software (e.g. `qgis-render.png`), with a line here on what it can't express.

- QGIS 4.2.3 (`qgis-render*.png`, set up and rendered by [`qgis/render_kits.py`](../../../qgis/render_kits.py)): `qgis-render.png` puts both data layers in one map layer (a memory layer with a rule per data layer), so the casings at rendering pass 0 go beneath all main strokes. `qgis-render-each-data-layer-complete-before-the-next.png` has a map layer per data layer, which is what QGIS draws without that merge.

## SLD/SE and MapLibre

Written by pycartosym (main, after 0.6.6) from the style, as `cartosym <style>.cscss --to-format sld|maplibre`. They show what the two formats do with the case; they are not renders.

- `style.cscss`, SLD/SE: not written, the writer refuses it: `Stroke.casing` has no SLD/SE mapping
- `style.cscss`, MapLibre: not written, the writer refuses it: `stroke.casing` has no MapLibre mapping
