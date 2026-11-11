"""Resolve the Symbolizer that applies to one feature, following the draft.

- /req/core/rules: rules are considered in order; later selected rules override.
- /req/core/selector, /req/core/nested: nested rules apply only if the parent is selected.
- /req/core/instances, /req/json/partial-update, /req/json/array-element-update:
  objects with ``alter: true`` and ``{index, value}`` updates modify only part of a property.
- /req/core/default-values: unset properties take the defaults from clause 7.
- /req/parameter-values/expressions: expressions in property values are evaluated per feature.
- /req/parameter-values/null: an expression evaluating to NULL gives a value by the property's data type.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any

from .evaluate import Context, EvaluationError, evaluate, matches_selector

DEFAULTS: dict[str, Any] = {
    "visibility": True,
    "opacity": 1,
    "zOrder": 1,
    "fill": {"color": "white", "opacity": 1},
    "stroke": {"color": "black", "opacity": 1, "width": {"px": 1}},
}


def _is_expression(v: Any) -> bool:
    return isinstance(v, dict) and ("op" in v or "property" in v or "sysId" in v or "$ref" in v)


def _merge(base: Any, update: Any) -> Any:
    """Apply *update* on top of *base*."""
    if isinstance(update, dict) and "index" in update and "value" in update and set(update) <= {"index", "value"}:
        result = list(base) if isinstance(base, list) else []
        while len(result) <= update["index"]:
            result.append(None)
        result[update["index"]] = _merge(result[update["index"]], update["value"])
        return result
    if isinstance(update, dict) and update.get("alter") and isinstance(base, dict):
        result = dict(base)
        for k, v in update.items():
            if k != "alter":
                result[k] = _merge(result.get(k), v)
        return result
    if isinstance(update, dict):
        return {k: v for k, v in update.items() if k != "alter"}
    return copy.deepcopy(update)


def _apply_rules(rules: list[dict], ctx: Context, sym: dict) -> None:
    for rule in rules or []:
        if not matches_selector(rule.get("selector"), ctx):
            continue
        for key, value in (rule.get("symbolizer") or {}).items():
            sym[key] = _merge(sym.get(key), value)
        _apply_rules(rule.get("nestedRules"), ctx, sym)


# /req/parameter-values/null: the value of a property whose expression evaluates
# to NULL, by the data type of the property (table-parameter-values-null).
_COLOR_KEYS = {"color", "tint", "blackTint", "colorChannels"}
_TEXT_KEYS = {"text", "face", "image", "uri"}
_ENUM_KEYS = {"hAlignment", "vAlignment", "type"}
_GRAPHIC_KEYS = {"marker", "label"}
_DROP = object()  # an enumeration: leave it unset, so its default applies


def _null_value(key: str | None) -> Any:
    if key in _GRAPHIC_KEYS:
        return None  # `null`, emptying its graphical elements
    if key == "visibility":
        return False
    if key in _COLOR_KEYS:
        return "black"
    if key in _TEXT_KEYS:
        return ""
    if key in _ENUM_KEYS:
        return _DROP
    return 0  # integer or real, such as stroke.width, opacity or zOrder


def _evaluate_values(v: Any, ctx: Context, key: str | None = None) -> Any:
    if _is_expression(v):
        try:
            result = evaluate(v, ctx)
        except EvaluationError:
            result = None
        # A property set to `null` directly is not an expression, so it stays null.
        return _null_value(key) if result is None else result
    if isinstance(v, dict):
        items = {k: _evaluate_values(x, ctx, k) for k, x in v.items()}
        return {k: x for k, x in items.items() if x is not _DROP}
    if isinstance(v, list):
        return [_evaluate_values(x, ctx, key) for x in v]
    return v



def load(path: str | Path) -> dict:
    """Read a CartoSym-JSON style, resolving `$include` (/req/json/include).

    Rules of included style sheets come before the including file's rules;
    `$variables` of the including file override those of included ones.
    """
    path = Path(path)
    style = json.loads(path.read_text(encoding="utf-8"))
    includes = style.pop("$include", None) or []
    if isinstance(includes, str):
        includes = [includes]
    rules: list = []
    variables: dict = {}
    for inc in includes:
        base = load(path.parent / inc)
        rules += base.get("stylingRules", [])
        variables.update(base.get("$variables", {}))
    variables.update(style.get("$variables", {}))
    style["stylingRules"] = rules + style.get("stylingRules", [])
    if variables:
        style["$variables"] = variables
    return style


def resolve(style: dict, ctx: Context) -> dict:
    """Return the resolved symbolizer for the feature described by *ctx*."""
    if style.get("$variables"):
        ctx = dataclasses.replace(ctx, definitions=style["$variables"])
    sym: dict[str, Any] = {}
    _apply_rules(style.get("stylingRules", []), ctx, sym)
    resolved = copy.deepcopy(DEFAULTS)
    if ctx.options.default_marker == "dot":
        resolved["marker"] = {"elements": [{"type": "Dot", "stroke": {"width": {"px": 10}, "color": "white"}}]}
    for key, value in sym.items():
        if isinstance(value, dict) and isinstance(resolved.get(key), dict):
            resolved[key] = {**resolved[key], **value}
        else:
            resolved[key] = value
    return _evaluate_values(resolved, ctx)
