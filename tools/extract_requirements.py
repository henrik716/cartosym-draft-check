"""Snapshot the requirement text of PR #133 for the gallery.

Usage: python tools/extract_requirements.py [path to cartographic-symbology]

Reads the requirement files (and the clause files, where the core class is) of the checked-out branch (requirements-placeholders)
and writes src/cartosym_draft/requirements.json: for each requirement, recommendation and permission identifier,
the file, line and `part::` sentences. Also copies the branch's CartoSym-JSON
schema, which the gallery build validates every style against.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "cartosym_draft" / "requirements.json"
SCHEMA_OUT = ROOT / "src" / "cartosym_draft" / "CartoSym-JSON.schema.json"


def main(argv: list[str]) -> int:
    spec = Path(argv[0] if argv else ROOT.parent / "cartographic-symbology")
    git = ["git", "-C", str(spec)]
    branch = subprocess.run([*git, "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
    commit = subprocess.run([*git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run([*git, "status", "--porcelain", "--", "1-core", "2-shapes"],
                                capture_output=True, text=True).stdout.strip())
    reqs: dict[str, dict] = {}
    # Most requirements are in rc-*.adoc files; the core class is inline in clause 7.
    files = [*spec.glob("1-core/requirements/rc-*.adoc"), *spec.glob("2-shapes/requirements/rc-*.adoc"),
             *spec.glob("1-core/sections/clause_*.adoc"), *spec.glob("2-shapes/sections/clause_*.adoc")]
    for f in sorted(files):
        current = None
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), start=1):
            if line.startswith(("identifier:: /req/", "identifier:: /rec/", "identifier:: /per/")):
                current = line.split("::", 1)[1].strip()
                reqs[current] = {"file": f.relative_to(spec).as_posix(), "line": n, "parts": []}
            elif line.startswith("part::") and current:
                reqs[current]["parts"].append(line.split("::", 1)[1].strip())
            elif line.strip() == "====" and current and reqs[current]["parts"]:
                current = None
    OUT.write_text(json.dumps({"branch": branch, "commit": commit, "uncommitted_changes": dirty,
                               "requirements": reqs}, indent=1, ensure_ascii=False), encoding="utf-8")
    SCHEMA_OUT.write_text((spec / "1-core/schemas/CartoSym-JSON.schema.json").read_text(encoding="utf-8"), encoding="utf-8")
    print(f"{len(reqs)} requirements from {branch} @ {commit}{' (with uncommitted changes)' if dirty else ''} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
