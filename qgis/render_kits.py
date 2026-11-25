# SPDX-License-Identifier: MIT
"""QGIS renders of the rendering-pass kits (opengeospatial/cartographic-symbology#212).

Each kit's map is set up by hand in QGIS, the way a QGIS user or a converter would:

- ``viz.pass`` N: the symbol layers' rendering pass N. A rule-based renderer always
  draws by them, pass by pass across all features of the map layer.
- ``feature.pass`` k: symbol layers in that order, all at one rendering pass. Within a
  pass, the rule-based renderer draws one feature at a time.
- casing and center line: line layers beneath and above the main stroke, at passes 0, 1, 2.
- ``zOrder``: the renderer's feature order (``orderBy``) within a map layer; across data
  layers, the map layer order.

Sizes in px are taken at ``pixelSize_mm`` and rendered at 2 x the view's size, as the
draft renderer does. Lines have round caps and joins (Part 1).

Run headless with PyQGIS (QGIS 4.2.3 here)::

    python qgis/render_kits.py gallery/kit

writes ``qgis-render*.png`` into each ``passes-*`` kit. The XPlanung kit is drawn by
xmas-plugin's own style instead: it needs the plugin importable (its pixi environment).
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFillSymbol,
    QgsGeometry,
    QgsJsonUtils,
    QgsLabelLineSettings,
    QgsLineSymbol,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsPalLayerSettings,
    QgsProperty,
    QgsRectangle,
    QgsRendererCategory,
    QgsRuleBasedRenderer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsSymbolLayer,
    QgsTextFormat,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtCore import QMetaType, QSize, Qt
from qgis.PyQt.QtGui import QColor, QFont

SCALE = 2
MM = Qgis.RenderUnit.Millimeters
FONT = "DejaVu Sans"  # Arial isn't installed here


class Kit:
    def __init__(self, path: Path):
        self.path = path
        self.view = json.loads((path / "view.json").read_text())
        self.px = self.view["pixelSize_mm"]

    def data(self, name: str) -> QgsVectorLayer:
        layer = QgsVectorLayer(str(self.path / f"{name}.geojson"), name, "ogr")
        assert layer.isValid(), name
        return layer

    def line(self, color, px, level=0, dash=None, alpha=1.0) -> QgsSimpleLineSymbolLayer:
        c = QColor(color)
        assert c.isValid(), color
        c.setAlphaF(alpha)
        lyr = QgsSimpleLineSymbolLayer(c, px * self.px)
        lyr.setWidthUnit(MM)
        lyr.setPenCapStyle(Qt.PenCapStyle.RoundCap)
        lyr.setPenJoinStyle(Qt.PenJoinStyle.RoundJoin)
        if dash:
            lyr.setUseCustomDashPattern(True)
            lyr.setCustomDashVector([d * self.px for d in dash])
            lyr.setCustomDashPatternUnit(MM)
        lyr.setRenderingPass(level)
        return lyr

    def fill(self, color) -> QgsSimpleFillSymbolLayer:
        """A fill with the default stroke, black 1 px (clause 7)."""
        lyr = QgsSimpleFillSymbolLayer(
            QColor(color), Qt.BrushStyle.SolidPattern, QColor("black"), Qt.PenStyle.SolidLine, self.px
        )
        lyr.setStrokeWidthUnit(MM)
        lyr.setPenJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return lyr

    def render(self, layers: list[QgsVectorLayer], name: str = "qgis-render") -> None:
        """Draw ``layers`` bottom to top and write ``<name>.png``."""
        v = self.view
        ms = QgsMapSettings()
        ms.setDestinationCrs(QgsCoordinateReferenceSystem(v["crs"]))
        ms.setExtent(QgsRectangle(*v["bbox"]))
        ms.setOutputSize(QSize(v["width"] * SCALE, v["height"] * SCALE))
        ms.setOutputDpi(25.4 / self.px * SCALE)
        ms.setBackgroundColor(QColor(v["background"]))
        ms.setFlag(Qgis.MapSettingsFlag.Antialiasing, True)
        ms.setFlag(Qgis.MapSettingsFlag.DrawLabeling, True)
        ms.setLayers(list(reversed(layers)))  # QGIS lists the top layer first
        job = QgsMapRendererParallelJob(ms)
        job.start()
        job.waitForFinished()
        assert not job.errors(), [e.message for e in job.errors()]
        out = self.path / f"{name}.png"
        job.renderedImage().save(str(out))
        print(out)


def rule_based(renderer) -> QgsRuleBasedRenderer:
    """The rule-based equivalent of ``renderer``, its rules made by C++."""
    return QgsRuleBasedRenderer.convertFromRenderer(renderer)


def styled(layer: QgsVectorLayer, *symbol_layers, order_by: str | None = None) -> QgsVectorLayer:
    """``layer`` drawn with one symbol of ``symbol_layers``, in a rule-based renderer."""
    cls = QgsFillSymbol if layer.geometryType() == Qgis.GeometryType.Polygon else QgsLineSymbol
    r = rule_based(QgsSingleSymbolRenderer(cls(list(symbol_layers))))
    if order_by:
        r.setOrderBy(QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(order_by, True)]))
        r.setOrderByEnabled(True)
    layer.setRenderer(r)
    return layer


def enabled_if(lyr: QgsSymbolLayer, expression: str) -> QgsSymbolLayer:
    lyr.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, QgsProperty.fromExpression(expression))
    return lyr


# -- kits --------------------------------------------------------------------


def nested_override(k: Kit) -> None:
    # QGIS has no cascade: a converter writes the merged result, the white stroke
    k.render([styled(k.data("Roads"), k.line("white", 3))])


toplevel_override = nested_override


def feature_pass(k: Kit) -> None:
    for name, (w, i) in {"qgis-render": (5, 3), "qgis-render-wide": (12, 8)}.items():
        k.render([styled(k.data("Roads"), k.line("black", w), k.line("white", i))], name)


def viz_pass(k: Kit) -> None:
    for name, (w, i) in {"qgis-render": (5, 3), "qgis-render-wide": (12, 8)}.items():
        k.render([styled(k.data("Roads"), k.line("black", w, 0), k.line("white", i, 1))], name)


def casing(k: Kit) -> None:
    k.render([styled(k.data("Roads"), k.line("black", 3 + 2 * 1, 0), k.line("white", 3, 1))])


def rule_without_pass(k: Kit) -> None:
    zones = styled(k.data("Zones"), k.fill("lightgray"))
    roads = styled(k.data("Roads"), k.line("black", 5, 0), k.line("white", 3, 1))
    k.render([zones, roads])


def feature_and_viz_pass(k: Kit) -> None:
    k.render([styled(k.data("Roads"), k.line("black", 7, 0), k.line("white", 5, 0), k.line("red", 1, 1))])


def zorder(k: Kit) -> None:
    # zOrder across data layers: the map layer order, Roads (0) beneath Rails (1)
    roads = styled(k.data("Roads"), k.line("gray", 4))
    rails = styled(k.data("Rails"), k.line("black", 2))
    k.render([roads, rails])


def center_line(k: Kit) -> None:
    brown = "#6b4f1d"
    k.render([styled(k.data("Roads"), k.line(brown, 10 + 2 * 1.5, 0), k.line("#f5d76e", 10, 1), k.line(brown, 1, 2))])


def labels_pass(k: Kit) -> None:
    roads = styled(k.data("Roads"), k.line("black", 12, 0), k.line("white", 8, 1))
    fmt = QgsTextFormat()
    font = QFont(FONT)
    font.setBold(True)
    fmt.setFont(font)
    fmt.setSize(11)  # points, as the draft renderer reads it
    fmt.setSizeUnit(Qgis.RenderUnit.Points)
    fmt.setColor(QColor("black"))
    pal = QgsPalLayerSettings()
    pal.fieldName = "name"
    pal.placement = Qgis.LabelPlacement.Line
    pal.lineSettings().setPlacementFlags(Qgis.LabelLinePlacementFlag.OnLine)
    # at the middle of the line only, as the draft renderer places it
    pal.lineSettings().setLineAnchorPercent(0.5)
    pal.lineSettings().setAnchorType(QgsLabelLineSettings.AnchorType.Strict)
    pal.setFormat(fmt)
    roads.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    roads.setLabelsEnabled(True)
    k.render([roads])


def feature_pass_minus_one(k: Kit) -> None:
    roads = styled(k.data("Roads"), k.line("#6b4f1d", 8 + 2 * 1, 0), k.line("#f5d76e", 8, 1))
    dark = "#333333"
    rails = styled(
        k.data("Rails"),
        enabled_if(k.line(dark, 9 + 2 * 1), '"bridge"'),  # feature pass -1: casing,
        enabled_if(k.line("white", 9), '"bridge"'),  # the bridge's white line,
        k.line(dark, 3),  # then pass 0, the railway
        order_by='"z_order"',
    )
    k.render([roads, rails])


def shared_zorder(k: Kit) -> None:
    # fresh symbol layers each time: QgsSymbolLayer.clone() drops the rendering pass
    def road_layers():
        return [k.line("#6b4f1d", 8 + 2 * 1.5, 0), k.line("#f5d76e", 8, 1)]

    def rail_layers():
        return [k.line("#333333", 3 + 2 * 1.5, 0), k.line("white", 3, 1, dash=[6, 6])]

    # Casings of all data layers first: both data layers in one map layer
    both = QgsVectorLayer(f"LineString?crs={k.view['crs']}&field=dataLayer:string", "Roads and Rails", "memory")
    for name in ("Roads", "Rails"):  # data layer order
        for f in k.data(name).getFeatures():
            g = QgsFeature(both.fields())
            g.setGeometry(f.geometry())
            g["dataLayer"] = name
            both.dataProvider().addFeature(g)
    cats = [
        QgsRendererCategory("Roads", QgsLineSymbol(road_layers()), "Roads"),
        QgsRendererCategory("Rails", QgsLineSymbol(rail_layers()), "Rails"),
    ]
    both.setRenderer(rule_based(QgsCategorizedSymbolRenderer("dataLayer", cats)))
    k.render([both])

    # Each data layer complete before the next: a map layer each
    roads = styled(k.data("Roads"), *road_layers())
    rails = styled(k.data("Rails"), *rail_layers())
    k.render([roads, rails], "qgis-render-each-data-layer-complete-before-the-next")


def translucent_passes(k: Kit) -> None:
    def zones():
        return styled(k.data("Zones"), k.fill("#5b8c5a"))

    # A group per pass: a map layer per pass, each at 50 % layer opacity
    p0 = styled(k.data("Roads"), k.line("black", 12, 0))
    p1 = styled(k.data("Roads"), k.line("white", 8, 1))
    for layer in (p0, p1):
        layer.setOpacity(0.5)
    k.render([zones(), p0, p1])

    # One group for all passes: one map layer at 50 % layer opacity
    roads = styled(k.data("Roads"), k.line("black", 12, 0), k.line("white", 8, 1))
    roads.setOpacity(0.5)
    k.render([zones(), roads], "qgis-render-one-group-for-all-passes")

    # Each stroke on its own: 50 % in the colours
    roads = styled(k.data("Roads"), k.line("black", 12, 0, alpha=0.5), k.line("white", 8, 1, alpha=0.5))
    k.render([zones(), roads], "qgis-render-each-stroke-on-its-own")


def xplanung(k: Kit) -> None:
    """What xmas-plugin draws: its plan layers, styled from its own style file, of which
    ``style.cs.json`` is the spec's encoding (levels as rendering passes, the order by
    ``ebene`` as the layers' feature order)."""
    try:
        import xmas_plugin
        from xmas_plugin.core.style.builder import FEATURE_VERSION, build_renderer, layer_context
        from xmas_plugin.core.style.tree import VERSION_VARIABLE, load_rules
    except ImportError:
        print(f"{k.path.name}: skipped, it needs xmas-plugin")
        return
    rules = load_rules(Path(xmas_plugin.__file__).parents[1] / "style/definitions/xplan.yaml")

    def fs(p):  # XPlanung's Flächenschlussobjekt, as the plugin splits its polygon layers
        return p.get("flaechenschluss") is True and p.get("ebene") in (0, None)

    layers = []  # the plugin's plan layers in the view, bottom to top
    for name, geometry, fixed, accepts in [
        ("Flächenschlussobjekte", "polygon", {"flaechenschluss": True}, fs),
        ("Überlagerungsobjekte", "polygon", {"flaechenschluss": False}, lambda p: not fs(p)),
        ("Linienobjekte", "line", None, lambda p: True),
    ]:
        kind = {"polygon": "Polygon", "line": "LineString"}[geometry]
        layer = QgsVectorLayer(f"Multi{kind}?crs={k.view['crs']}", name, "memory")
        layer.dataProvider().addAttributes(
            [
                QgsField("featuretype", QMetaType.Type.QString),
                QgsField("properties", QMetaType.Type.QVariantMap),
                QgsField("version", QMetaType.Type.QString),
            ]
        )
        layer.updateFields()
        layer.addExpressionField(FEATURE_VERSION, QgsField(VERSION_VARIABLE, QMetaType.Type.Int))
        for data in k.view["layers"]:
            for f in json.loads((k.path / f"{data['id']}.geojson").read_text())["features"]:
                if f["geometry"]["type"].removeprefix("Multi") == kind and accepts(f["properties"]):
                    g = QgsFeature(layer.fields())
                    g.setGeometry(QgsGeometry(QgsJsonUtils.geometryFromGeoJson(json.dumps(f["geometry"]))))
                    g.setAttributes([data["id"], f["properties"], "6.0", None])
                    layer.dataProvider().addFeature(g)
        layer.setRenderer(build_renderer(rules, layer_context(geometry, fixed, None, "6.0")))
        layers.append(layer)
    k.render(layers)


KITS = {
    "01-nested-override": nested_override,
    "02-toplevel-override": toplevel_override,
    "03-feature-pass": feature_pass,
    "04-viz-pass": viz_pass,
    "05-casing": casing,
    "06-rule-without-pass": rule_without_pass,
    "07-feature-and-viz-pass": feature_and_viz_pass,
    "08-zorder": zorder,
    "09-center-line": center_line,
    "10-labels-pass": labels_pass,
    "11-feature-pass-minus-one": feature_pass_minus_one,
    "12-shared-zorder": shared_zorder,
    "13-translucent-passes": translucent_passes,
    "14-xplanung": xplanung,
}


def main(root: Path) -> None:
    app = QgsApplication([], False)
    app.initQgis()
    for case, setup in KITS.items():
        setup(Kit(root / f"passes-{case}"))
    app.exitQgis()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
