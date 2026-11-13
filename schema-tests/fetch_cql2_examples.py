"""Download the CQL2-JSON examples of OGC API - Features Part 3 into schema-tests/cql2-examples/.

Pinned to the last commit that changed them (2024-03-07), so the test documents stay the same.
"""
import json, os, urllib.request

COMMIT = "66faf8c7726661425fd842d99cdd9b2e5625d010"
DIR = "cql2/standard/schema/examples/json"
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "cql2-examples")
os.makedirs(out, exist_ok=True)

listing = json.load(urllib.request.urlopen(
    f"https://api.github.com/repos/opengeospatial/ogcapi-features/contents/{DIR}?ref={COMMIT}"))
names = sorted(f["name"] for f in listing if f["name"].endswith(".json"))
for n in names:
    url = f"https://raw.githubusercontent.com/opengeospatial/ogcapi-features/{COMMIT}/{DIR}/{n}"
    with urllib.request.urlopen(url) as r, open(os.path.join(out, n), "wb") as f:
        f.write(r.read())
print(f"{len(names)} examples in {out}")
