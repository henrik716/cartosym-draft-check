"""Draft renderer: an evaluator and SVG renderer for the CartoSym 2.0 draft requirements.

A discussion tool, not a reference implementation. It implements the behavior
in the Part 1 requirements (opengeospatial/cartographic-symbology, first
proposed in PR #133), and makes each judgement call that was open a switchable
option so the alternatives can be rendered side by side.
"""

from .options import Options

__all__ = ["Options"]
