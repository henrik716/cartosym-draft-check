"""Switchable behaviors for judgement calls in the draft requirements.

Each field corresponds to a decision the draft makes where the spec text
does not settle it. The defaults are what the draft (PR #133) proposes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Options:
    # /req/core/opacity: "whole" applies Symbolizer opacity to the portrayal
    # as a group; "per-element" multiplies it into fill and stroke separately.
    opacity: str = "whole"

    # /req/casing/casing: "below" draws the casing beneath the main stroke.
    casing: str = "below"
    # Casing width: "total" means casing.width is the full width of the casing
    # band; "extra" means it extends that much beyond each side of the stroke.
    casing_width: str = "total"
    # Casing at crossings: "all-first" draws every casing before any stroke,
    # so crossings and junctions merge; "with-feature" draws each line's
    # casing with its own stroke. The draft does not say.
    casing_pass: str = "all-first"

    # /req/font-outlines/outline: "below" draws the outline beneath the glyphs.
    font_outline: str = "below"

    # /req/core/default-values: the default Marker is "Single default Dot"
    # (white, 10 px). "dot" applies it to every feature that sets no marker,
    # as the table says; "none" leaves it out, which keeps the other cards readable.
    default_marker: str = "none"

    # /req/core/z-order: "higher-on-top" draws higher zOrder later.
    z_order: str = "higher-on-top"

    # Hatch angle direction: "clockwise" from the positive x axis (draft table:
    # "Hatches orientation clockwise degree"), or "counter-clockwise".
    hatch_angle: str = "clockwise"

    # /req/dashes/dash-pattern: dashPattern values in "px", or as multiples
    # of the stroke width ("stroke-width"). The draft does not say.
    dash_units: str = "px"

    # /req/vector/image: default hot spot of an Image graphic, as a fraction
    # of its width and height.
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
    label_pass: str = "on-top"

    # /req/coverage/color-map, /req/coverage/opacity-map: "interpolate"
    # between entries, or "step" (each entry applies up to the next one).
    map_mode: str = "interpolate"
    # Values outside the map: "clamp" to the first/last entry, or "transparent".
    map_outside: str = "clamp"

    # /req/coverage/color-channels: how band values become 0..1 color
    # components. "as-given" uses them unscaled (the schema types colorChannels
    # as 0..1); "reflectance" divides Sentinel-2 L2A digital numbers by 10000;
    # "display" divides by 3000, a common true-color stretch.
    color_channels_scale: str = "as-given"

    # /req/coverage/gamma: "exponent" applies c ** gamma (draft); "inverse"
    # applies c ** (1 / gamma), as SE GammaValue does (> 1 brightens).
    gamma: str = "exponent"

    # /req/hill-shading/factor: "intensity" multiplies the darkening by factor
    # (draft); "percent" uses factor / 100 as the intensity; "exaggeration"
    # multiplies the terrain slope (vertical exaggeration).
    hillshade_factor: str = "intensity"
    # /req/hill-shading/sun: azimuth "clockwise-from-north" (compass bearing)
    # or "counter-clockwise-from-east" (mathematical angle).
    hillshade_azimuth: str = "clockwise-from-north"

    # /req/gradients/angle: "css" (0 = towards the top, clockwise) or "math"
    # (0 = towards the right, counter-clockwise).
    gradient_angle: str = "css"
    # /req/gradients/position, /req/gradients/size: relative to the feature's
    # bounding box ("feature") or to the whole map ("map").
    gradient_frame: str = "feature"

    def with_(self, **changes) -> Options:
        return replace(self, **changes)
