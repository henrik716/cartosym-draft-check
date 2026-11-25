# 07-feature-and-viz-pass: feature.pass inside a viz.pass

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212](https://github.com/opengeospatial/cartographic-symbology/issues/212). From maxcollombin/pycartosym [`examples/passes/07-feature-and-viz-pass`](https://github.com/maxcollombin/pycartosym/tree/main/examples/passes) (MIT License, © Maxime Collombin), with `marker: null;` added to each top-level rule so that no default Dot is drawn.

The same mechanisms on a real map: Annex C examples 12 (visualization passes) and 13 (casings, `zOrder` and a
feature pass), roads and the railway at Otta, in [#233](https://github.com/opengeospatial/cartographic-symbology/pull/233).

## Style

```css
// Both identifiers: for each viz.pass, each feature is drawn with its
// feature.pass symbolizers in order.
Roads
{
   marker: null;
   [viz.pass = 0]
   {
      [feature.pass = 0] { stroke: { color: black; width: 7 px; }; }
      [feature.pass = 1] { stroke: { color: white; width: 5 px; }; }
   }
   [viz.pass = 1] { stroke: { color: red; width: 1 px; }; }
}
```

## What should be drawn

Pass 0, one road at a time: its black 7 px stroke, then its white 5 px stroke (feature passes 0 and 1), so at the crossing road 2's black edges cut across road 1's white line, as in 03. Pass 1: the red 1 px line of every road, above all of pass 0 and unbroken at the crossing.

## Files

- `style.cscss`: the style in CartoSym-CSS
- `style.cs.json`: the same in CartoSym-JSON, converted from `style.cscss` with pycartosym 0.6.5 (corrected by cartosym-draft-check: capabilities.*/feature.* written as sysId)
- `Roads.geojson`: the data layer `Roads` (3 features, EPSG:25833)
- `view.json`: extent (EPSG:25833), size in pixels, scale denominator and map background
- `draft-render.png`: the draft renderer, at 2 × the size of `view.json`
- `draft-render-detail.png`: the same, the crossing and the T-junction enlarged 4 ×

Render each data layer with the style at the extent and size of `view.json`, on its background color.

## Other renderers

Pull requests to [henrik716/cartosym-draft-check](https://github.com/henrik716/cartosym-draft-check) are welcome:
`style.sld` (SLD/SE), `style.maplibre.json` or a note on why MapLibre can't express the case, and renders from
other software (e.g. `qgis-render.png`), with a line here on what it can't express.

- QGIS 4.2.3 (`qgis-render*.png`, set up and rendered by [`qgis/render_kits.py`](../../../qgis/render_kits.py)): Black and white are line layers at rendering pass 0, drawn one feature at a time; red is at pass 1.
