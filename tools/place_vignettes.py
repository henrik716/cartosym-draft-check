"""Place each requirement vignette directly under the requirement it illustrates, in the Part 1 document.

Usage: python tools/place_vignettes.py [../cartographic-symbology]

For each vignette of ``cartosym_draft.doc_examples.REQUIREMENT_EXAMPLES``, finds the requirement block whose
identifier is the vignette's first requirement (in ``1-core/sections`` or ``1-core/requirements``) and includes
the vignette's .adoc right after that block. Vignette includes placed before (by this script, or the grouped
ones under "Examples" headings) are removed first, so the script can run again after vignettes change.
Keeps the line endings of each file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from cartosym_draft.doc_examples import REQUIREMENT_EXAMPLES  # noqa: E402

MARK = "// Vignette placed by cartosym-draft-check (tools/place_vignettes.py)"
OLD_MARK = "// Examples placed by cartosym-draft-check"
# An included vignette: its caption line, the example block and the include.
BLOCK = re.compile(r"\.Example style for [^\n]*\n====\ninclude::\.\./examples/requirements/[\w-]+\.adoc\[\]\n====\n\n?")


PLACED = re.compile(re.escape(MARK) + r"\n" + BLOCK.pattern)


def block(ex) -> str:
    reqs = ", ".join(f"`{r}`" for r in ex.requirements)
    return (f"{MARK}\n.Example style for {reqs}, in CartoSym-CSS\n====\n"
            f"include::../examples/requirements/{ex.name}.adoc[]\n====\n\n")


def main(spec: Path) -> int:
    core = spec / "1-core"
    files = sorted((core / "sections").glob("*.adoc")) + sorted((core / "requirements").glob("*.adoc"))
    texts, newlines = {}, {}
    for f in files:
        raw = f.read_bytes().decode("utf-8")
        newlines[f] = "\r\n" if "\r\n" in raw else "\n"
        t = raw.replace("\r\n", "\n")
        t = PLACED.sub("", t)
        t = BLOCK.sub("", t)  # the grouped vignettes placed before this script
        t = re.sub(rf"{re.escape(OLD_MARK)}\n\n?", "", t)
        texts[f] = t
    missing = []
    # Insert in reverse order of the list, each right after its block, so that vignettes under the same
    # requirement come out in the order of the list.
    for ex in reversed(REQUIREMENT_EXAMPLES):
        target = ex.requirements[0]
        for f, t in texts.items():
            m = re.search(rf"^identifier:: {re.escape(target)}\s*$", t, re.M)
            if not m:
                continue
            end = t.index("\n====\n", m.end()) + len("\n====\n")
            # After the blank line that follows the block; at the end of the file, after a new one.
            if t[end:end + 1] == "\n":
                texts[f] = t[:end + 1] + block(ex) + t[end + 1:]
            else:
                texts[f] = t[:end] + "\n" + block(ex) + t[end:]
            break
        else:
            missing.append(f"{ex.name}: no requirement {target}")
    changed = 0
    for f, t in texts.items():
        raw = f.read_bytes().decode("utf-8")
        if t == raw.replace("\r\n", "\n"):
            continue
        out = (t.rstrip("\n") + "\n").replace("\n", newlines[f])
        if out != raw:
            f.write_bytes(out.encode("utf-8"))
            changed += 1
            print("updated", f.relative_to(spec))
    for m in missing:
        print("MISSING", m)
    print(f"{len(REQUIREMENT_EXAMPLES) - len(missing)} vignettes placed, {changed} files changed")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "cartographic-symbology"))
