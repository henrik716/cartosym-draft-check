# 14-xplanung: Bands of rendering passes and the order by `ebene` in an XPlanung plan

Part of the rendering-pass cases of [opengeospatial/cartographic-symbology#212](https://github.com/opengeospatial/cartographic-symbology/issues/212): the XPlanung case from xmas-plugin ([xmas-plugin#136](https://gitlab.opencode.de/xleitstelle/xmas-plugin/-/work_items/136)). It shows a section of Hamburg's development plan (Bebauungsplan) HafenCity 13, where an elevated railway crosses roads, styled by xmas-plugin's style for XPlanung.

## Data

- `HafenCity13.gml` (XPlanGML 5.4), converted to XPlanung 6.0 with xmas-core (`xmas convert --to 6.0`).
- One GeoJSON file per featuretype (a data layer, EPSG:25832), holding the areas and lines that meet the view. Their arcs are split into short straight segments, as GeoJSON has no curves. Their properties are as xmas-app stores them.
- Left out: points, whose image sizes are metres in xmas-plugin's style, which the spec can't state yet ([#100](https://github.com/opengeospatial/cartographic-symbology/issues/100)), and the plan's presentation objects.
- Three areas of `SO_Schienenverkehrsrecht` (the elevated railway) and two of `SO_Strassenverkehr` have `ebene` 1 (above ground). They lie over roads, railway areas and a Kennzeichnung at ground level.

## Style

`style.cs.json` holds xmas-plugin's rules for these featuretypes, for XPlanung 6, in the spec's encoding:

- The first rule is the base rule. Its `zOrder` is `ebene` by its absolute value, with a missing `ebene` as 0. It unsets fill, stroke and marker, so only what a rule sets is drawn ([#207](https://github.com/opengeospatial/cartographic-symbology/issues/207)).
- Each symbol layer has a `viz.pass` in a band, by what it draws, following the order of xmas-plugin's layers:

  | `viz.pass` | Symbol layers |
  |---|---|
  | 0–99 | fills of areas (here 0) |
  | 1–99 | pattern fills of areas (here 1) |
  | 100–199 | the rest of an area: borders, dashed and pattern lines (here 100) |
  | 200–299 | lines (here 200) |
  | 300–399 | points (not in this kit) |
  | 400–499 | plan and Bereich (not in this kit) |

- xmas-plugin stacks a featuretype's symbol layers as nested rules without a selector. Here they are `feature.pass`es, numbered through the data layer in the order QGIS draws them. A data layer with a single one has none.
- The two sides of `flaechenschluss` are XPlanung's definition of a Flächenschlussobjekt (`flaechenschluss` true, and `ebene` 0 or none) and its negation.
- Pattern strokes use Part 2's `stroke.pattern`, `patternGap` and `patternInitialGap`. Our line offset, trim, marker placements and pattern rotation are vendor keys on the Symbolizer, which a renderer without them ignores.
- Sizes are in metres (`{m: …}`). That includes an Image's `transform.scaling`, which xmas-plugin reads as metres, not as a factor ([#100](https://github.com/opengeospatial/cartographic-symbology/issues/100)).
- Property paths are xmas-plugin's (`zweckbestimmung.0.allgemein`), as [#238](https://github.com/opengeospatial/cartographic-symbology/issues/238) is still open.
- Rules that no object of the view matches are left out.
- The images in `svg/` are xmas-plugin's, under CC0.

`style.cs.json` validates against the CartoSym-JSON schema on main (fefe225). There is no `style.cscss`: pycartosym (main, 0ae840a) accepts `patternGap` only as a plain number, not as `{m: 5}`.

## What should be drawn

Pass by pass, across all data layers. Within a pass, the objects with `ebene` 1 come after those at ground level (`zOrder`), and ties keep data layer order:

- **Pass 0:** the fills of the Baugebiet, the ground-level railway and roads, and the raised roads, which lie over the ground-level ones.
- **Pass 1:** the hatches of the ground-level roads, Spezielle Bauweise and Überbaubare Grundstücksfläche.
- **Pass 100:** the borders of all areas: railway, roads, Textabschnitt, the Kennzeichnung with its pattern line, Spezielle Bauweise, Überbaubare Grundstücksfläche, the dashed Unverbindliche Vormerkung and Denkmalschutz, and Wasserrecht. The raised railway, drawn by its borders alone, lies over the borders beneath it.
- **Pass 200:** the lines: Wegerecht (a line and a pattern line), Straßenbegrenzungslinien and Baugrenzen.

## Files

- `style.cs.json`: the style in CartoSym-JSON
- `svg/`: the images the style names
- `<featuretype>.geojson`: one data layer per featuretype (EPSG:25832), bottom to top in `view.json`
- `view.json`: extent (EPSG:25832), size in pixels (1:2000), scale denominator and map background
- `qgis-render.png`: xmas-plugin's rendering in QGIS, at 2 × the size of `view.json`

Render each data layer with the style at the extent and size of `view.json`, on its background colour.

## Other renderers

Pull requests to [henrik716/cartosym-draft-check](https://github.com/henrik716/cartosym-draft-check) are welcome:
`style.sld` (SLD/SE), `style.maplibre.json` or a note on why MapLibre can't express the case, and renders from
other software, with a line here on what it can't express.

- QGIS 4.2.3 (`qgis-render.png`, rendered by [`qgis/render_kits.py`](../../../qgis/render_kits.py)): This is what xmas-plugin draws. Its plan layers are Flächenschlussobjekte, Überlagerungsobjekte and Linienobjekte, bottom to top, styled from the plugin's own style file, of which `style.cs.json` is the spec's encoding. Its symbol levels are the `viz.pass`es above, and `zOrder` is each layer's feature order, but both apply within one map layer only. The bands follow that layer order, so lines lie over areas as in a spec renderer. One difference remains: the Überlagerungsobjekte lie over the Flächenschlussobjekte as a whole. So the raised roads' fill (pass 0) and the hatches of Spezielle Bauweise and Überbaubare Grundstücksfläche (pass 1) cover the borders of the ground-level roads (pass 100), where a spec renderer draws those borders on top.
