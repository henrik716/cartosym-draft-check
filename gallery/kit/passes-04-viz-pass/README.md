# 04-viz-pass: viz.pass: all features per pass

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212](https://github.com/opengeospatial/cartographic-symbology/issues/212). From maxcollombin/pycartosym [`examples/passes/04-viz-pass`](https://github.com/maxcollombin/pycartosym/tree/main/examples/passes) (MIT License, © Maxime Collombin), with `marker: null;` added to each top-level rule so that no default Dot is drawn.

The same mechanisms on a real map: Annex C examples 12 (visualization passes) and 13 (casings, `zOrder` and a
feature pass), roads and the railway at Otta, in [#233](https://github.com/opengeospatial/cartographic-symbology/pull/233).

## Style

```css
// All the roads are drawn with the black stroke first, then all of them
// with the white one: the white strokes cross over every black stroke.
Roads
{
   marker: null;
   [viz.pass = 0] { stroke: { color: black; width: 5 px; }; }
   [viz.pass = 1] { stroke: { color: white; width: 3 px; }; }
}
```

The same with wider strokes (12 px and 8 px), `style-wide.cscss`:

```css
// 04-viz-pass with wider strokes, to compare with 03-feature-pass-wide:
// all the roads are drawn with the black stroke first, then all of them
// with the white one.
Roads
{
   marker: null;
   [viz.pass = 0] { stroke: { color: black; width: 12 px; }; }
   [viz.pass = 1] { stroke: { color: white; width: 8 px; }; }
}
```

## What should be drawn

Pass 0 draws the black 5 px strokes of all roads, pass 1 their white 3 px strokes. The white lines join at the crossing and at the T-junction, with no black across them. `style-wide.cscss` is the same style with 12 px and 8 px strokes, to compare with 03's.

## Files

- `style.cscss`: the style in CartoSym-CSS
- `style.cs.json`: the same in CartoSym-JSON, converted from `style.cscss` with pycartosym 0.6.5
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

- QGIS 4.2.3 (`qgis-render*.png`, set up and rendered by [`qgis/render_kits.py`](../../../qgis/render_kits.py)): The two strokes are line layers at rendering passes 0 and 1 (symbol levels), each drawn across all features. `qgis-render-wide.png` is `style-wide`.
