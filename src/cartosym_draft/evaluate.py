"""Evaluate CQL2-JSON expressions following the draft requirements.

Covers the Part 1 operators and functions: logical, relational, arithmetic,
text relation, conditional, array relation, text manipulation and math.
Where the draft proposes a behavior the spec does not settle, the behavior is
taken from :class:`~cartosym_draft.options.Options`.
"""

from __future__ import annotations

import math
import random
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from .options import Options


@dataclass
class Context:
    """What an expression can refer to while a feature is being portrayed."""

    properties: dict[str, Any] = field(default_factory=dict)
    system: dict[str, Any] = field(default_factory=dict)  # e.g. {"viz.sd": 50000, "dataLayer.id": "Roads"}
    options: Options = field(default_factory=Options)
    # /req/variables/definition: values the application sets at run time,
    # overriding the style's own definitions (e.g., from a slider).
    variables: dict[str, Any] = field(default_factory=dict)
    # The style's `$variables` (set by cascade.resolve).
    definitions: dict[str, Any] = field(default_factory=dict)


_VARIABLE_REF = "#/$variables/"


class EvaluationError(Exception):
    pass


def evaluate(expr: Any, ctx: Context) -> Any:
    """Evaluate a CQL2-JSON expression (or a literal) in *ctx*."""
    if isinstance(expr, list):
        return [evaluate(e, ctx) for e in expr]
    if not isinstance(expr, dict):
        return expr
    if "property" in expr:
        return ctx.properties.get(expr["property"])
    if "sysId" in expr:
        return ctx.system.get(expr["sysId"])
    if "$ref" in expr:  # /req/variables/expression, /req/json/variables
        ref = expr["$ref"]
        if not isinstance(ref, str) or not ref.startswith(_VARIABLE_REF):
            raise EvaluationError(f"unsupported $ref {ref!r}")
        name = ref[len(_VARIABLE_REF):]
        if name in ctx.variables:
            return ctx.variables[name]
        if name in ctx.definitions:
            # Evaluated without this definition, so a variable cannot refer to itself.
            rest = {k: v for k, v in ctx.definitions.items() if k != name}
            return evaluate(ctx.definitions[name], Context(ctx.properties, ctx.system, ctx.options, ctx.variables, rest))
        raise EvaluationError(f"undefined variable {name!r}")
    if "op" in expr:
        return _operation(expr["op"], expr.get("args", []), ctx)
    return expr  # an object literal, e.g. a color or unit value


def _num(v: Any) -> float | int:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise EvaluationError(f"expected a number, got {v!r}")
    return v


def _like(text: str, pattern: str) -> bool:
    """CQL2 LIKE: % matches any sequence, _ one character, \\ escapes."""
    regex, i = "", 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\" and i + 1 < len(pattern):
            regex += re.escape(pattern[i + 1])
            i += 2
            continue
        regex += ".*" if ch == "%" else "." if ch == "_" else re.escape(ch)
        i += 1
    return re.fullmatch(regex, text, re.DOTALL) is not None


def _accenti(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _divide(a, b, opts: Options):
    a, b = _num(a), _num(b)
    if opts.division == "integer-if-both-integers" and isinstance(a, int) and isinstance(b, int):
        return int(a / b)  # truncates toward zero, as C does
    return a / b


# Number of arguments of each standard function and fixed-arity operator
# (/req/functions/call-expressions: a call that does not match is invalid).
_ARITY = {
    "not": 1, "isnull": 1, "between": 3, "like": 2, "in": 2,
    "contains": 2, "startswith": 2, "endswith": 2,
    "notlike": 2, "notcontains": 2, "notstartswith": 2, "notendswith": 2,
    "a_contains": 2, "a_containedby": 2, "a_equals": 2, "a_overlaps": 2,
    "casei": 1, "caseinsensitize": 1, "accenti": 1, "accentinsensitize": 1,
    "lowercase": 1, "lower": 1, "uppercase": 1, "upper": 1, "substitute": 3,
    "abs": 1, "acos": 1, "asin": 1, "atan": 1, "ceil": 1, "cos": 1, "cosh": 1, "exp": 1, "floor": 1,
    "log": 1, "log10": 1, "sin": 1, "sinh": 1, "sqrt": 1, "tan": 1, "tanh": 1, "rint": 1, "round": 1,
    "atan2": 2, "pow": 2, "^": 2, "random": 0, "*": 2, "/": 2, "div": 2, "//": 2, "%": 2, "mod": 2,
    "+": 2, "=": 2, "eq": 2, "<>": 2, "!=": 2, "ne": 2, "<": 2, ">": 2, "<=": 2, ">=": 2,
    "?:": 3, "if": 3,
}


def _operation(op: str, args: list, ctx: Context) -> Any:
    op_l = op.lower()
    expected = _ARITY.get(op_l)
    if expected is not None and len(args) != expected:
        raise EvaluationError(f"{op} takes {expected} argument(s), got {len(args)}")
    if op_l == "random":  # /req/math/random
        return random.random()

    # Conditional: only the selected branch is evaluated (/req/conditional/*).
    if op_l in ("?:", "if"):
        cond = evaluate(args[0], ctx)
        return evaluate(args[1] if cond is True else args[2], ctx)

    # Short-circuit logical operators (/req/core/logical).
    if op_l == "and":
        return all(evaluate(a, ctx) is True for a in args)
    if op_l == "or":
        return any(evaluate(a, ctx) is True for a in args)

    v = [evaluate(a, ctx) for a in args]

    if op_l == "not":
        return not v[0]

    # Relational (/req/core/relational)
    if op_l in ("=", "eq"):
        return v[0] == v[1]
    if op_l in ("<>", "!=", "ne"):
        return v[0] != v[1]
    if op_l in ("<", ">", "<=", ">="):
        if v[0] is None or v[1] is None:
            return False
        return {"<": v[0] < v[1], ">": v[0] > v[1], "<=": v[0] <= v[1], ">=": v[0] >= v[1]}[op_l]
    if op_l == "between":
        return v[1] <= v[0] <= v[2]
    if op_l == "in":
        return v[0] in v[1]
    if op_l == "isnull":
        return v[0] is None

    # Arithmetic (/req/arithmetic/*)
    if op_l == "+":
        return _num(v[0]) + _num(v[1])
    if op_l == "-":
        return -_num(v[0]) if len(v) == 1 else _num(v[0]) - _num(v[1])
    if op_l == "*":
        return _num(v[0]) * _num(v[1])
    if op_l == "/":
        return _divide(v[0], v[1], ctx.options)
    if op_l in ("div", "//"):
        return int(_num(v[0]) / _num(v[1]))  # truncation toward zero
    if op_l in ("%", "mod"):
        return math.fmod(_num(v[0]), _num(v[1])) if isinstance(v[0], float) or isinstance(v[1], float) \
            else int(math.fmod(v[0], v[1]))  # sign of the first operand
    if op_l in ("^", "pow"):
        return _num(v[0]) ** _num(v[1])

    # Text relation (/req/text-relation/*)
    if op_l == "like":
        return _like(str(v[0]), str(v[1]))
    if op_l in ("contains", "startswith", "endswith"):
        a, b = str(v[0]), str(v[1])
        return {"contains": b in a, "startswith": a.startswith(b), "endswith": a.endswith(b)}[op_l]
    # The negated forms are separate operations in the draft, but have no
    # encoding in the JSON schema (which would use `not`).
    if op_l == "notlike":
        return not _like(str(v[0]), str(v[1]))
    if op_l in ("notcontains", "notstartswith", "notendswith"):
        a, b = str(v[0]), str(v[1])
        return not {"notcontains": b in a, "notstartswith": a.startswith(b), "notendswith": a.endswith(b)}[op_l]

    # Array relations (/req/array-relations/*)
    if op_l == "a_contains":
        return all(x in v[0] for x in v[1])
    if op_l == "a_containedby":
        return all(x in v[1] for x in v[0])
    if op_l == "a_equals":
        return list(v[0]) == list(v[1])
    if op_l == "a_overlaps":
        return any(x in v[1] for x in v[0])

    # Text manipulation (/req/text-manipulation/*)
    if op_l in ("casei", "caseinsensitize"):
        return str(v[0]).casefold()
    if op_l in ("accenti", "accentinsensitize"):
        return _accenti(str(v[0]))
    if op_l in ("lowercase", "lower"):
        return str(v[0]).lower()
    if op_l in ("uppercase", "upper"):
        return str(v[0]).upper()
    if op_l == "concatenate":
        return "".join(str(x) for x in v)
    if op_l == "substitute":
        return str(v[0]).replace(str(v[1]), str(v[2]))
    if op_l == "format":
        return str(v[0]) % tuple(v[1:])

    # Math (/req/math/*)
    unary = {
        "abs": abs, "acos": math.acos, "asin": math.asin, "atan": math.atan, "ceil": math.ceil,
        "cos": math.cos, "cosh": math.cosh, "exp": math.exp, "floor": math.floor, "log": math.log,
        "log10": math.log10, "sin": math.sin, "sinh": math.sinh, "sqrt": math.sqrt, "tan": math.tan,
        "tanh": math.tanh,
        "rint": lambda x: float(round(x)),  # Python round() is half-to-even
        "round": lambda x: math.floor(x + 0.5),  # halves toward positive infinity
    }
    if op_l in unary:
        return unary[op_l](_num(v[0]))
    if op_l == "atan2":
        return math.atan2(_num(v[0]), _num(v[1]))
    if op_l == "max":
        return max(v)
    if op_l == "min":
        return min(v)

    raise EvaluationError(f"unsupported operator or function {op!r}")


def matches_selector(selector: Any, ctx: Context) -> bool:
    """A rule applies if it has no selector or its selector evaluates to true."""
    if selector is None:
        return True
    try:
        return evaluate(selector, ctx) is True
    except EvaluationError:
        return False


__all__ = ["Context", "EvaluationError", "evaluate", "matches_selector"]
