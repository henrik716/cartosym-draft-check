# 11-feature-pass-minus-one: A bridge in feature pass -1

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212](https://github.com/opengeospatial/cartographic-symbology/issues/212). Added for #212 from the list on [#197](https://github.com/opengeospatial/cartographic-symbology/issues/197) (cartosym-draft-check).

The same mechanisms on a real map: Annex C examples 12 (visualization passes) and 13 (casings, `zOrder` and a
feature pass), roads and the railway at Otta, in [#233](https://github.com/opengeospatial/cartographic-symbology/pull/233).

## Style

```css
// A railway bridge over a road, as in Annex C example 13. zOrder raises the
// bridge (z_order 2) over the road (zOrder 1). In feature pass -1 the bridge
// gets a wide white line with a dark casing; in pass 0 the railway itself is
// drawn on it.
Roads { marker: null; zOrder: 1; stroke: { color: #f5d76e; width: 8 px; casing: { color: #6b4f1d; width: 1 px } }; }
Rails
{
   marker: null;
   zOrder: z_order;
   stroke: { color: #333333; width: 3 px };
   // After the rule above, so that it overrides the railway's stroke in pass -1
   [feature.pass = -1 and bridge = true] { stroke: { color: white; width: 9 px; casing: { color: #333333; width: 1 px } }; }
}
```

## What should be drawn

The roads and the two ground pieces of the railway (`z_order` 1) are at `zOrder` 1: the roads' casings first, then the main strokes in data layer order, so the railway crosses road 1 on the level, over it. The bridge piece has `z_order` 2, so it comes after everything at `zOrder` 1: first its feature pass -1, a white 9 px line with a dark casing 1 px beyond each side, covering road 2 beneath, then its pass 0, the black 3 px railway on top. At the bridge's ends, the round caps of the white line and its casing (`/req/vector/stroke`) show as half circles around the railway.

## Files

- `style.cscss`: the style in CartoSym-CSS
- `style.cs.json`: the same in CartoSym-JSON, converted from `style.cscss` with pycartosym 0.6.7
- `Roads.geojson`: the data layer `Roads` (3 features, EPSG:25833)
- `Rails.geojson`: the data layer `Rails` (3 features, EPSG:25833)
- `view.json`: extent (EPSG:25833), size in pixels, scale denominator and map background
- `draft-render.png`: the draft renderer, at 2 × the size of `view.json`
- `draft-render-detail.png`: the same, the bridge enlarged 4 ×

Render each data layer with the style at the extent and size of `view.json`, on its background color.

## Other renderers

Pull requests to [henrik716/cartosym-draft-check](https://github.com/henrik716/cartosym-draft-check) are welcome:
`style.sld` (SLD/SE), `style.maplibre.json` or a note on why MapLibre can't express the case, and renders from
other software (e.g. `qgis-render.png`), with a line here on what it can't express.

- QGIS 4.2.3 (`qgis-render*.png`, set up and rendered by [`qgis/render_kits.py`](../../../qgis/render_kits.py)): Roads and Rails are separate map layers, Roads beneath, and Rails is ordered by `z_order`. The bridge's feature pass -1 is two line layers enabled by `bridge`, before the railway's line in the same symbol and at the same rendering pass. The map layer order stands in for the roads' `zOrder` 1, which works because no rail is below it.

## SLD/SE and MapLibre

Written by pycartosym (main, after 0.6.6) from the style, as `cartosym <style>.cscss --to-format sld|maplibre`. They show what the two formats do with the case; they are not renders.

- `style.cscss`, SLD/SE: not written, the writer refuses it: `Stroke.casing` has no SLD/SE mapping
- `style.cscss`, MapLibre: not written, the writer refuses it: `stroke.casing` has no MapLibre mapping
