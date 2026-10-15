"""Draft renderer: an evaluator and SVG renderer for the CartoSym 2.0 draft requirements.

A discussion tool, not a reference implementation. It implements the behavior
proposed in the draft requirements (opengeospatial/cartographic-symbology
PR #133), and makes each open judgement call a switchable option so the
alternatives can be rendered side by side.
"""

from .options import Options

__all__ = ["Options"]
