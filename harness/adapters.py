"""Run test cases against the implementations under test.

Each adapter returns an Outcome: what the implementation produced, or why it
could not produce anything (unsupported, error, crash).
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
SITE = Path(sys.prefix) / "Lib" / "site-packages"

# Windows access violation, reported by libCartoSym 0.0.1 on some inputs.
CRASH_CODES = {-1073741819, 3221225477}


@dataclass
class Outcome:
    status: str  # "ok", "unsupported", "error" or "crash"
    value: str | None = None
    detail: str = ""


def _write(name: str, content: str) -> Path:
    WORK.mkdir(exist_ok=True)
    path = WORK / name
    path.write_text(content, encoding="utf-8")
    return path


# --------------------------------------------------------------- libCartoSym

def _canif_env() -> dict[str, str]:
    env = dict(os.environ)
    dlls = [SITE / "ecrt" / "lib", SITE / "cscql2" / "bin", SITE / "cartosym" / "bin"]
    env["PATH"] = os.pathsep.join([str(p) for p in dlls] + [env.get("PATH", "")])
    return env


def _canif(*args: str) -> Outcome:
    exe = SITE / "cartosym" / "bin" / "cs-canif.exe"
    try:
        proc = subprocess.run(
            [str(exe), *args], capture_output=True, text=True,
            env=_canif_env(), timeout=30,
        )
    except subprocess.TimeoutExpired:
        return Outcome("error", detail="timeout")
    out = (proc.stdout + proc.stderr).strip()
    if proc.returncode in CRASH_CODES:
        return Outcome("crash", detail=f"exit code {proc.returncode}")
    if proc.returncode != 0:
        return Outcome("error", detail=out or f"exit code {proc.returncode}")
    if out.startswith("Failed to parse"):
        return Outcome("unsupported", detail=out)
    if out.startswith("Unresolved expression"):
        return Outcome("ok", value="<unresolved>", detail=out)
    return Outcome("ok", value=out)


def libcartosym_eval(expression: str) -> Outcome:
    """Evaluate a CQL2-Text expression with `cs-canif eval`."""
    return _canif("eval", str(_write("expr.cql2", expression)))


def libcartosym_parse_style(style: str, fmt: str) -> Outcome:
    """Check a style parses, by converting it to CartoSym-CSS with `cs-canif convert`."""
    src = _write(f"style.{fmt}", style)
    dst = WORK / "style-out.cscss"
    dst.unlink(missing_ok=True)
    result = _canif("convert", str(src), str(dst))
    if result.status == "ok":
        return Outcome("ok", value="valid" if dst.exists() else "invalid", detail=result.value or "")
    return result


# ---------------------------------------------------------------- pycartosym

def _cartosym_cli(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    exe = Path(sys.prefix) / "Scripts" / "cartosym.exe"
    return subprocess.run(
        [str(exe), *args],
        capture_output=True, text=True, env=env, timeout=60,
    )


def pycartosym_parse_expression(expression: str) -> Outcome:
    """pycartosym does not evaluate expressions; check it can parse them as CQL2."""
    try:
        from pycartosym import cql2
        cql2.parse_text(expression)
        return Outcome("ok", value="parsed")
    except Exception as exc:  # noqa: BLE001 - any parse failure counts
        return Outcome("unsupported", detail=f"{type(exc).__name__}: {exc}")


def pycartosym_validate_style(style: str, fmt: str) -> Outcome:
    """Validate a style against the CartoSym-CSS grammar or the CartoSym-JSON schema."""
    ext = {"cscss": "cscss", "csjson": "cs.json"}[fmt]
    path = _write(f"style.{ext}", style)
    proc = _cartosym_cli("validate", str(path))
    out = (proc.stdout + proc.stderr).strip()
    return Outcome("ok", value="valid" if proc.returncode == 0 else "invalid", detail=out)


# ------------------------------------------------------------ draft renderer

def _format(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        return repr(value)
    return str(value)


def draft_eval(expression: str, json_expr=None, properties: dict | None = None, variables: dict | None = None,
               definitions: dict | None = None, system: dict | None = None) -> Outcome:
    """Evaluate with the draft renderer (cartosym_draft, in this repository).

    Uses the case's CQL2-JSON when given; otherwise converts the CQL2-Text with
    pycartosym, whose parser has known bugs (string literals in function calls,
    arrays, conditionals, `^`).
    """
    from cartosym_draft.evaluate import Context, EvaluationError, evaluate
    if json_expr is not None:
        expr = json_expr
    else:
        try:
            from pycartosym import cql2
            expr = cql2.to_cql2_json(cql2.parse_text(expression))
        except Exception as exc:  # noqa: BLE001 - any parse failure counts
            return Outcome("unsupported", detail=f"does not parse: {type(exc).__name__}: {exc}")
    try:
        ctx = Context(properties=properties or {}, system=system or {}, variables=variables or {},
                      definitions=definitions or {})
        return Outcome("ok", value=_format(evaluate(expr, ctx)))
    except EvaluationError as exc:
        return Outcome("ok", value="<invalid>", detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - a crash in the draft renderer is a finding
        return Outcome("error", detail=f"{type(exc).__name__}: {exc}")
