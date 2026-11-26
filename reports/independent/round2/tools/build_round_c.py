"""Build the round C cases (expressions) from draft-check's cases/*.yaml, without expected values or notes.

uv run --no-project --with pyyaml python build_round_c.py <draft-check> <scratchpad>
"""
import glob
import json
import sys
from pathlib import Path

import yaml

dc, S = Path(sys.argv[1]), Path(sys.argv[2])
out = S / "round-c" / "sealed"
out.mkdir(parents=True, exist_ok=True)
cases, private = [], {}
for f in sorted(glob.glob(str(dc / "cases" / "*.yaml"))):
    for c in yaml.safe_load(open(f, encoding="utf-8")):
        case = {"id": c["id"], "requirement": c["requirement"]}
        if c["kind"] == "expression":
            case["kind"] = "expression"
            case["cql2_text"] = c["input"]
            if "json" in c:
                case["cql2_json"] = c["json"]
            for k in ("properties", "system", "definitions", "variables"):
                if k in c:
                    case[k] = c[k]
        else:
            case["kind"] = "style"
            case["style"] = c["input"]
            if "csjson" in c:
                case["at"] = c["csjson"]["at"]
        cases.append(case)
        private[c["id"]] = {"file": Path(f).name, "expect": c["expect"], "draft_only": c.get("draft_only", False)}

# Probes with no expected value: unary minus (#199) and how CartoSym-CSS reads a minus between numbers (#259).
probes = [
    ("minus-01", "/req/arithmetic/pow", "-2 ^ 2", None),
    ("minus-02", "/req/arithmetic/pow", "- 2 ^ 2", None),
    ("minus-03", "/req/arithmetic/pow", "-a ^ 2", {"a": 3}),
    ("minus-04", "/req/arithmetic/pow", "2 ^ -1", None),
    ("minus-05", "/req/arithmetic/pow", "-(2 ^ 2)", None),
    ("minus-06", "/req/arithmetic/sub", "3 - -2", None),
    ("minus-07", "/req/arithmetic/mul", "-a * 2", {"a": 3}),
    ("minus-08", "/req/arithmetic/mul", "2 * -a", {"a": 3}),
    ("minus-09", "/req/arithmetic/pow", "-2 ^ 0.5", None),
    ("minus-10", "/req/arithmetic/sub", "10 -4", None),
]
for pid, req, text, props in probes:
    case = {"id": pid, "requirement": req, "kind": "expression", "cql2_text": text}
    if props:
        case["properties"] = props
    cases.append(case)
    private[pid] = {"file": "probe", "expect": None}
pos = "/stylingRules/0/symbolizer/marker/elements/0/position"
size = "/stylingRules/0/symbolizer/marker/elements/0/size"
for pid, value, at in [("css-01", "position: 10 - 4", pos), ("css-02", "position: 10-4", pos),
                       ("css-03", "position: 10 -4", pos), ("css-04", "size: 10 -4", size),
                       ("css-05", "position: -10 -4", pos), ("css-06", "position: 10 (-4)", pos)]:
    cases.append({"id": pid, "requirement": "/req/cscss/expressions", "kind": "style",
                  "style": f"Huts {{ marker: {{ elements: [ Dot {{ {value}; size: 6 }} ] }}; }}\n".replace(
                      "; size: 6 }", " }" if value.startswith("size") else "; size: 6 }"), "at": at})
    private[pid] = {"file": "probe", "expect": None}

(out / "cases.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
(S / "private").mkdir(exist_ok=True)
(S / "private" / "round-c-expected.json").write_text(json.dumps(private, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(len(cases), "cases")
