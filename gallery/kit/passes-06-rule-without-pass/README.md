# 06-rule-without-pass: A rule without viz.pass next to rules with one

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212](https://github.com/opengeospatial/cartographic-symbology/issues/212). From maxcollombin/pycartosym [`examples/passes/06-rule-without-pass`](https://github.com/maxcollombin/pycartosym/tree/main/examples/passes) (MIT License, © Maxime Collombin), with `marker: null;` added to each top-level rule so that no default Dot is drawn.

The same mechanisms on a real map: Annex C examples 12 (visualization passes) and 13 (casings, `zOrder` and a
feature pass), roads and the railway at Otta, in [#233](https://github.com/opengeospatial/cartographic-symbology/pull/233).

## Style

```css
// A rule without viz.pass next to rules that have one: it applies in pass 0
// only (settled in opengeospatial/cartographic-symbology#198), so the
// background fill is drawn once, with the first pass.
Zones { marker: null; fill: { color: lightGray; }; }
Roads
{
   marker: null;
   [viz.pass = 0] { stroke: { color: black; width: 5 px; }; }
   [viz.pass = 1] { stroke: { color: white; width: 3 px; }; }
}
```

## What should be drawn

Pass 0: the light gray fill of the zone, with the default black 1 px stroke (the rule sets no stroke), and the black 5 px strokes of the roads. Pass 1: the white 3 px strokes of the roads. The Zones rule doesn't test `viz.pass`, so it is drawn in pass 0 only: a rule that doesn't test `viz.pass` is evaluated in every pass, but only a rule that tests it is drawn in a pass other than 0 (Jérôme on [#207](https://github.com/opengeospatial/cartographic-symbology/issues/207) and [#211](https://github.com/opengeospatial/cartographic-symbology/issues/211); [#198](https://github.com/opengeospatial/cartographic-symbology/issues/198)).

## Files

- `style.cscss`: the style in CartoSym-CSS
- `style.cs.json`: the same in CartoSym-JSON, converted from `style.cscss` with pycartosym 0.6.7
- `Zones.geojson`: the data layer `Zones` (1 feature, EPSG:25833)
- `Roads.geojson`: the data layer `Roads` (3 features, EPSG:25833)
- `view.json`: extent (EPSG:25833), size in pixels, scale denominator and map background
- `draft-render.png`: the draft renderer, at 2 × the size of `view.json`
- `draft-render-detail.png`: the same, the crossing and the T-junction enlarged 4 ×

Render each data layer with the style at the extent and size of `view.json`, on its background color.

## Other renderers

Pull requests to [henrik716/cartosym-draft-check](https://github.com/henrik716/cartosym-draft-check) are welcome:
`style.sld` (SLD/SE), `style.maplibre.json` or a note on why MapLibre can't express the case, and renders from
other software (e.g. `qgis-render.png`), with a line here on what it can't express.

- QGIS 4.2.3 (`qgis-render*.png`, set up and rendered by [`qgis/render_kits.py`](../../../qgis/render_kits.py)): Zones and Roads are separate map layers, Zones beneath. QGIS's rendering passes order only within a map layer, which this case doesn't need.

## SLD/SE and MapLibre

Written by pycartosym (main, after 0.6.6) from the style, as `cartosym <style>.cscss --to-format sld|maplibre`. They show what the two formats do with the case; they are not renders.

- `style.cscss`, SLD/SE: `style.sld`
- `style.cscss`, MapLibre: `style.maplibre.json`
