"""Switchable behaviors for judgement calls in the draft requirements.

Each field corresponds to a decision the requirements make where the spec text
did not settle it. The defaults follow the requirement text of the snapshot
(main, which has #133, plus the wording changes of #192).
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Options:
    # /req/core/opacity: the Symbolizer opacity multiplies the opacity of the
    # fill, the stroke and the marker graphics, not labels. "whole" applies it
    # to these parts together, as a group (/rec/core/opacity-together);
    # "per-element" multiplies it into each part separately, which meets the
    # requirement but lets them show through each other.
    opacity: str = "whole"
    # With visualization passes and "whole": one group per visualization pass ("per-pass", draft: each pass
    # is drawn after the whole map of the earlier ones), or one group for all passes of a data layer and
    # zOrder ("all-passes"), so a layer's passes don't show through each other.
    opacity_passes: str = "per-pass"

    # /req/casing/casing: "below" draws the casing beneath the main stroke.
    casing: str = "below"
    # Casing width: "extra" means it extends that much beyond each side of the
    # stroke (draft, per Jérôme); "total" means casing.width is the full width
    # of the casing band.
    casing_width: str = "extra"
    # Casing at crossings: "all-first" draws the casings of all features with
    # the same zOrder before their strokes, so crossings and junctions merge
    # (draft, per Jérôme and the painter's algorithm in clause 7);
    # "with-feature" draws each line's casing with its own stroke. Either way,
    # the fills of all features with the same zOrder are drawn first (Jérôme's
    # order on #198: fill, casing, main stroke, center line).
    casing_pass: str = "all-first"
    # Which features "all features with the same zOrder" covers (/req/casing/casing): "all" data layers, so
    # the casings of roads and a railway with the same zOrder merge (draft; also the painter's algorithm,
    # which is commented out of clause 7); "per-layer" draws each data layer's fills, casings, main strokes
    # and center lines before the next layer's, as separate QGIS or MapLibre layers do.
    casing_layers: str = "all"

    # /req/vector/fonts: the unit of a font `size` given without one: "pt" (main: "a `size` specified in
    # points") or "px", like every other length (agreed on #100; the font-size PR writes `pt` in the
    # examples, so their figures are the same either way).
    font_size_unit: str = "pt"

    # /req/font-outlines/outline: "below" draws the outline beneath the glyphs.
    font_outline: str = "below"

    # /req/core/default-values: the default Marker is "Single default Dot"
    # (white, 10 px). "dot" applies it to every feature that sets no marker,
    # as the table says (and as intended, per Jérôme); "none" leaves it out,
    # which the gallery cards use to stay readable.
    default_marker: str = "dot"

    # /req/core/z-order: "higher-on-top" draws higher zOrder later.
    z_order: str = "higher-on-top"

    # Hatch angle direction from horizontal lines: "counter-clockwise" (the
    # figure of the default 45 degree hatch, and the tightened table), or
    # "clockwise" (the table before it was tightened).
    hatch_angle: str = "counter-clockwise"

    # /req/dashes/dash-pattern: unqualified dashPattern lengths in "px"
    # (draft), or as multiples of the stroke width ("stroke-width", as
    # MapLibre). Qualified lengths always follow their unit; `pc` is percent
    # of the stroke width (/per/dashes/dash-pattern-units).
    dash_units: str = "px"

    # /req/vector/image: default hot spot of an Image graphic, as a fraction
    # of its width and height: the centre (draft and libCartoSym; Jérôme
    # confirmed it after first saying top-left).
    image_hotspot: tuple[float, float] = (0.5, 0.5)

    # /req/arithmetic/div: "real" always returns a real quotient (draft);
    # "integer-if-both-integers" follows libCartoSym.
    division: str = "real"

    # /req/stipples/ratio, /req/dot-patterns/*: how the dots look (#84).
    # "fill-1px": 1 px squares in the fill color; "dot-defaults": the Dot
    # class defaults (white, 10 px).
    dots: str = "fill-1px"

    # /req/labels/placement: "higher-wins" places the higher priority value
    # first; "lower-wins" treats 1 as the most important.
    label_priority: str = "higher-wins"
    # minSpacing / maxSpacing in "px" or in map units ("m").
    label_spacing_units: str = "px"
    # /req/labels/label: "on-top" draws labels in a separate pass above all
    # features; "with-feature" draws each label with its own feature.
    # /rec/labels/overlap: labels that would overlap are always omitted.
    label_pass: str = "on-top"
    # With "on-top" and visualization passes: the labels pass comes after all visualization passes
    # ("after-all", draft: "on top of all styled vector features") or at the end of the visualization pass
    # that sets the label ("own-pass"), under later passes. A feature's label comes from the first pass
    # in which it is drawn with one.
    label_viz_pass: str = "after-all"
    # Labels on lines: "straight" places each one as a whole, turned to the line's direction at its
    # position (draft); "curved" lays it along the line, Text bent glyph by glyph, other graphics turned to
    # the line where they are, kept upright, and left out where the line is shorter than the label or bends
    # too sharply (the proposal for #142: Jérôme on #142 and #241, "labels curving along the road").
    label_lines: str = "straight"

    # /req/coverage/color-map, /req/coverage/opacity-map: "interpolate"
    # between entries, or "step" (each entry applies up to the next one).
    map_mode: str = "interpolate"
    # Values outside the map: "clamp" to the first/last entry, or "transparent".
    map_outside: str = "clamp"

    # /req/coverage/color-channels: how band values become 0..1 color
    # components. "as-given" uses them unscaled (draft: colorChannels is 0..1,
    # and the style scales the bands, as example 6 does); "reflectance" divides
    # Sentinel-2 L2A digital numbers by 10000; "display" divides by 3000, a
    # common true-color stretch.
    color_channels_scale: str = "as-given"

    # /req/coverage/gamma: "exponent" applies c ** gamma (draft); "inverse"
    # applies c ** (1 / gamma), as SE GammaValue does (> 1 brightens).
    gamma: str = "exponent"

    # /req/hill-shading/factor: "exaggeration" multiplies the horizontal
    # components of the surface normal by factor before normalizing it (draft,
    # as in Jérôme's renderer); "intensity" multiplies the darkening by factor
    # (the earlier draft text); "percent" uses factor / 100 as the intensity.
    hillshade_factor: str = "exaggeration"
    # /req/hill-shading/sun: azimuth "clockwise-from-north" (compass bearing)
    # or "counter-clockwise-from-east" (mathematical angle).
    hillshade_azimuth: str = "clockwise-from-north"  # draft: a compass bearing, per Jérôme

    # /req/gradients/angle: "math" (0 = towards the right, counter-clockwise;
    # draft, per Jérôme) or "css" (0 = towards the top, clockwise).
    gradient_angle: str = "math"
    # /req/gradients/position, /req/gradients/size: relative to the feature's
    # bounding box ("feature") or to the whole map ("map").
    gradient_frame: str = "feature"

    def with_(self, **changes) -> Options:
        return replace(self, **changes)
