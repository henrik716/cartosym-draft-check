# 09-center-line: Built-in casing and center line

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212](https://github.com/opengeospatial/cartographic-symbology/issues/212). Added for #212 from the list on [#197](https://github.com/opengeospatial/cartographic-symbology/issues/197) (cartosym-draft-check).

The same mechanisms on a real map: Annex C examples 12 (visualization passes) and 13 (casings, `zOrder` and a
feature pass), roads and the railway at Otta, in [#233](https://github.com/opengeospatial/cartographic-symbology/pull/233).

## Style

```css
// Built-in casing and center line: within a zOrder, the casings of all roads
// go beneath all main strokes, and the center lines of all roads on top of
// them, so a joining road cuts neither (/req/casing/casing, /req/casing/center).
Roads
{
   marker: null;
   stroke: { color: #f5d76e; width: 10 px; casing: { color: #6b4f1d; width: 1.5 px }; center: { color: #6b4f1d; width: 1 px } };
}
```

The same with three visualization passes, `style-passes.cscss`:

```css
// The same map as 09-center-line, written with three visualization passes:
// all casings, then all main strokes, then all center lines.
Roads
{
   marker: null;
   [viz.pass = 0] { stroke: { color: #6b4f1d; width: 13 px }; }
   [viz.pass = 1] { stroke: { color: #f5d76e; width: 10 px }; }
   [viz.pass = 2] { stroke: { color: #6b4f1d; width: 1 px }; }
}
```

## What should be drawn

Each road has a yellow 10 px stroke, a brown casing 1.5 px beyond each side and a brown 1 px center line. The casings of all roads are drawn first, then the main strokes, then the center lines: at the crossing and the T-junction the yellow strokes join with no casing across them, and the center lines run through (road 2's over road 1's). `style-passes.cscss` writes the same order with three visualization passes and draws the same image (the build checks this).

## Files

- `style.cscss`: the style in CartoSym-CSS
- `style.cs.json`: the same in CartoSym-JSON, converted from `style.cscss` with pycartosym 0.6.5 (corrected by cartosym-draft-check: centerLine renamed center (#120))
- `style-passes.cscss`, `style-passes.cs.json`: the same with three visualization passes
- `Roads.geojson`: the data layer `Roads` (3 features, EPSG:25833)
- `view.json`: extent (EPSG:25833), size in pixels, scale denominator and map background
- `draft-render.png`: the draft renderer, at 2 × the size of `view.json`
- `draft-render-detail.png`: the same, the crossing and the T-junction enlarged 4 ×
- `draft-render-passes.png`: the draft renderer, style `style-passes.cscss`, at 2 × the size of `view.json`
- `draft-render-passes-detail.png`: the same, the crossing and the T-junction enlarged 4 ×

Render each data layer with the style at the extent and size of `view.json`, on its background color.

## Other renderers

Pull requests to [henrik716/cartosym-draft-check](https://github.com/henrik716/cartosym-draft-check) are welcome:
`style.sld` (SLD/SE), `style.maplibre.json` or a note on why MapLibre can't express the case, and renders from
other software (e.g. `qgis-render.png`), with a line here on what it can't express.
