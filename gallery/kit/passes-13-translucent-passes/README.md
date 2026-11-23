# 13-translucent-passes: A translucent layer with visualization passes

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212](https://github.com/opengeospatial/cartographic-symbology/issues/212). Added for #212 from the list on [#197](https://github.com/opengeospatial/cartographic-symbology/issues/197) (cartosym-draft-check).

The same mechanisms on a real map: Annex C examples 12 (visualization passes) and 13 (casings, `zOrder` and a
feature pass), roads and the railway at Otta, in [#233](https://github.com/opengeospatial/cartographic-symbology/pull/233).

## Style

```css
// A translucent road layer drawn in two visualization passes over a zone.
// The Symbolizer opacity applies to the parts of a feature together
// (/rec/core/opacity-together): for each pass, or for the layer's passes
// together?
Zones { marker: null; fill: { color: #5b8c5a }; }
Roads
{
   marker: null;
   opacity: 0.5;
   [viz.pass = 0] { stroke: { color: black; width: 12 px }; }
   [viz.pass = 1] { stroke: { color: white; width: 8 px }; }
}
```

## What should be drawn

Pass 0: the green zone (with the default black 1 px stroke), then the roads' black 12 px strokes at 50 % as one group, so they don't show through each other at the crossing. Pass 1: the roads' white 8 px strokes at 50 %, as a second group over the first, so the black shows through the white: light gray roads with dark edges, through which the zone shows.

## Open question

`/rec/core/opacity-together` applies the Symbolizer `opacity` to the parts of a feature together, "either for each feature or for all features of a data layer with the same `zOrder` drawn at once". With visualization passes, is that one group per pass, or one group for all of the layer's passes?

The draft renderer draws each reading:

- A group per pass (draft renderer)
- One group for all passes. The white covers the black inside the group: a 50 % white line with 50 % black edges.
- Each stroke on its own. Meets /req/core/opacity but not the recommendation: the strokes show through each other at the crossing.

## Files

- `style.cscss`: the style in CartoSym-CSS
- `style.cs.json`: the same in CartoSym-JSON, converted from `style.cscss` with pycartosym 0.6.5
- `Zones.geojson`: the data layer `Zones` (1 feature, EPSG:25833)
- `Roads.geojson`: the data layer `Roads` (3 features, EPSG:25833)
- `view.json`: extent (EPSG:25833), size in pixels, scale denominator and map background
- `draft-render.png`: the draft renderer, at 2 × the size of `view.json`
- `draft-render-detail.png`: the same, the crossing and the T-junction enlarged 4 ×
- `draft-render-one-group-for-all-passes.png`: the draft renderer, reading: One group for all passes, at 2 × the size of `view.json`
- `draft-render-one-group-for-all-passes-detail.png`: the same, the crossing and the T-junction enlarged 4 ×
- `draft-render-each-stroke-on-its-own.png`: the draft renderer, reading: Each stroke on its own, at 2 × the size of `view.json`
- `draft-render-each-stroke-on-its-own-detail.png`: the same, the crossing and the T-junction enlarged 4 ×

Render each data layer with the style at the extent and size of `view.json`, on its background color.

## Other renderers

Pull requests to [henrik716/cartosym-draft-check](https://github.com/henrik716/cartosym-draft-check) are welcome:
`style.sld` (SLD/SE), `style.maplibre.json` or a note on why MapLibre can't express the case, and renders from
other software (e.g. `qgis-render.png`), with a line here on what it can't express.

## SLD/SE and MapLibre

Written by pycartosym (main, after 0.6.6) from the style, as `cartosym <style>.cscss --to-format sld|maplibre`. They show what the two formats do with the case; they are not renders.

- `style.cscss`, SLD/SE: `style.sld`
- `style.cscss`, MapLibre: `style.maplibre.json`
