"""Build gallery/playground.html: edit a card's style and see it rendered.

The page runs this package in the browser with Pyodide (it uses only the
standard library). The build writes playground-data.json with every card and
sample: style, layers, view and variants. Coverage layers name the
sample_data function that makes their grid, so the data is generated in the
browser instead of being shipped.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from .options import Options

# Modules the browser loads, in /src/cartosym_draft/ of the published repo.
MODULES = ["__init__", "options", "evaluate", "cascade", "colors", "coverage", "render", "sample_data"]
PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.2/full/"


def _options(o: Options) -> dict:
    default = Options()
    out = {}
    for f in dataclasses.fields(Options):
        v = getattr(o, f.name)
        if v != getattr(default, f.name):
            out[f.name] = list(v) if isinstance(v, tuple) else v
    return out


def _layers(layers) -> list[dict]:
    out = []
    for layer in layers:
        if layer.type == "coverage" and layer.grid is not None:
            out.append({"id": layer.id, "type": "coverage", "grid": layer.grid.name})
        else:
            out.append({"id": layer.id, "type": layer.type, "features": layer.features})
    return out


def _view(v) -> dict:
    return {"bbox": list(v.bbox), "width": v.width, "height": v.height}


def data(decisions, samples) -> dict:
    entries = []
    for d in decisions:
        entries.append({
            "key": d.key, "kind": "card", "group": d.group, "title": d.title, "question": d.question,
            "style": d.style, "layers": _layers(d.layers), "view": _view(d.view), "anchors": d.anchors,
            "variants": [{"label": v.label, "draft": v.is_draft, "options": _options(v.options),
                          **({"style": v.style} if v.style else {})} for v in d.variants],
        })
    for s in samples:
        for i, p in enumerate(s.panels):
            key = f"sample-{s.key}" + (f"-{i + 1}" if len(s.panels) > 1 else "")
            title = s.title + (f" ({p.caption})" if p.caption else "")
            entries.append({
                "key": key, "kind": "sample", "group": "Samples", "title": title, "question": s.check,
                "style": p.style, "layers": _layers(p.layers), "view": _view(p.view), "anchors": p.anchors,
                "variants": [{"label": "As in the sample", "draft": False, "options": _options(p.options)}],
            })
    return {"modules": MODULES, "entries": entries}


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CartoSym Draft Playground</title>
<style>__CSS__
main { max-width: 1320px; }
.pg { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; }
@media (min-width: 1000px) { .pg { grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); } }
.pg textarea { width: 100%; min-height: 460px; font: 12.5px/1.45 ui-monospace, Consolas, monospace; background: var(--bg);
  color: var(--fg); border: 1px solid var(--line); border-radius: 6px; padding: 10px; resize: vertical; tab-size: 2; }
.pg select { width: 100%; font: inherit; padding: 6px; border-radius: 6px; border: 1px solid var(--line); background: var(--card); color: var(--fg); }
.variants-pick label { display: block; font-size: 14px; margin: 3px 0; cursor: pointer; }
#out svg { width: 100%; height: auto; border: 1px solid var(--line); border-radius: 6px; display: block; }
#status { font-size: 13px; color: var(--muted); min-height: 1.5em; margin: 6px 0; }
#status.error { color: #b03a2e; white-space: pre-wrap; font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
.row { display: flex; gap: 8px; align-items: center; margin: 8px 0; flex-wrap: wrap; }
button { font: inherit; font-size: 13px; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--line); background: var(--card); color: var(--fg); cursor: pointer; }
</style></head><body><main>
<p><a href="index.html">← Gallery</a> · <a href="requirements.html">Requirements</a></p>
<h1>Playground</h1>
<p class="lead">Edit a card's style, or switch between its variants, and the draft renderer draws it again. The renderer runs in your
browser (Python, through Pyodide); the first load takes a few seconds. Coverage cards take a second or two to draw.</p>
<section class="card">
<div class="pg">
<div>
<label for="pick"><strong>Card or sample</strong></label>
<select id="pick"></select>
<p class="question" id="question"></p>
<div class="variants-pick" id="variants"></div>
<div class="row"><strong>Style (CartoSym-JSON)</strong><button id="reset" type="button">Reset</button><button id="copy" type="button">Copy</button></div>
<textarea id="style" spellcheck="false" aria-label="Style (CartoSym-JSON)"></textarea>
</div>
<div>
<div id="status">Loading the renderer…</div>
<div id="out"></div>
</div>
</div>
</section>
</main>
<script src="__PYODIDE__pyodide.js"></script>
<script>
const $ = (id) => document.getElementById(id);
let py = null, render = null, entries = [], current = null, variant = 0, timer = null, busy = false, pending = false;

function fill() {
  const groups = {};
  for (const e of entries) (groups[e.group] = groups[e.group] || []).push(e);
  for (const [g, list] of Object.entries(groups)) {
    const og = document.createElement("optgroup"); og.label = g;
    for (const e of list) { const o = document.createElement("option"); o.value = e.key; o.textContent = e.title; og.appendChild(o); }
    $("pick").appendChild(og);
  }
}

function select(key) {
  current = entries.find((e) => e.key === key) || entries[0];
  $("pick").value = current.key;
  $("question").textContent = current.question;
  variant = Math.max(0, current.variants.findIndex((v) => v.draft));
  const box = $("variants"); box.innerHTML = "";
  if (current.variants.length > 1) {
    current.variants.forEach((v, i) => {
      const l = document.createElement("label");
      l.innerHTML = `<input type="radio" name="variant" value="${i}" ${i === variant ? "checked" : ""}> `;
      l.appendChild(document.createTextNode(v.label + (v.draft ? " (draft)" : "")));
      l.querySelector("input").addEventListener("change", () => { variant = i; loadStyle(); draw(); });
      box.appendChild(l);
    });
  }
  loadStyle();
  if (location.hash.slice(1) !== current.key) history.replaceState(null, "", "#" + current.key);
  draw();
}

function pretty(obj) {
  // Indent 2, but arrays of plain values (colors, positions) on one line.
  return JSON.stringify(obj, null, 2).replace(
    /\[\s*((?:-?[\d.eE+-]+|true|false|null|"[^"\,\[\]{}]*")(?:,\s*(?:-?[\d.eE+-]+|true|false|null|"[^"\,\[\]{}]*"))*)\s*\]/g,
    (_, inner) => "[" + inner.split(",").map((x) => x.trim()).join(", ") + "]");
}

function loadStyle() {
  const v = current.variants[variant];
  $("style").value = pretty(v.style || current.style);
}

async function draw() {
  if (!render) return;
  if (busy) { pending = true; return; }
  let style;
  try { style = JSON.parse($("style").value); }
  catch (err) { $("status").className = "error"; $("status").textContent = "JSON: " + err.message; return; }
  busy = true; $("status").className = ""; $("status").textContent = "Rendering…";
  await new Promise((r) => setTimeout(r, 20));
  const t = performance.now();
  try {
    const svg = render(JSON.stringify(current), JSON.stringify(style), JSON.stringify(current.variants[variant].options));
    $("out").innerHTML = svg;
    $("status").textContent = `Rendered in ${Math.round(performance.now() - t)} ms.`;
  } catch (err) {
    $("status").className = "error";
    $("status").textContent = String(err.message || err).split("\n").slice(-4).join("\n");
  }
  busy = false;
  if (pending) { pending = false; draw(); }
}

$("pick").addEventListener("change", (e) => select(e.target.value));
$("style").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(draw, 400); });
$("reset").addEventListener("click", () => { loadStyle(); draw(); });
$("copy").addEventListener("click", () => navigator.clipboard && navigator.clipboard.writeText($("style").value));
window.addEventListener("hashchange", () => { if (location.hash.slice(1) !== current.key) select(location.hash.slice(1)); });

(async () => {
  try {
    const data = await (await fetch("playground-data.json")).json();
    entries = data.entries; fill(); select(location.hash.slice(1));
    py = await loadPyodide({ indexURL: "__PYODIDE__" });
    py.FS.mkdirTree("/lib/cartosym_draft");
    for (const m of data.modules) {
      const src = await (await fetch(`../src/cartosym_draft/${m}.py`)).text();
      py.FS.writeFile(`/lib/cartosym_draft/${m}.py`, src);
    }
    py.runPython(`
import sys, json
sys.path.insert(0, "/lib")
from cartosym_draft import sample_data
from cartosym_draft.options import Options
from cartosym_draft.render import Layer, View, render as _render
_grids = {}
def _grid(name):
    if name not in _grids:
        _grids[name] = getattr(sample_data, name)()
    return _grids[name]
def draw(entry, style, options):
    e, o = json.loads(entry), json.loads(options)
    if "image_hotspot" in o:
        o["image_hotspot"] = tuple(o["image_hotspot"])
    layers = [Layer(l["id"], type="coverage", grid=_grid(l["grid"])) if l.get("grid")
              else Layer(l["id"], l.get("features", []), l.get("type", "vector")) for l in e["layers"]]
    v = e["view"]
    return _render(json.loads(style), layers, View(bbox=tuple(v["bbox"]), width=v["width"], height=v["height"]),
                   Options(**o), anchors=e.get("anchors", False))
`);
    render = py.globals.get("draw");
    draw();
  } catch (err) {
    $("status").className = "error";
    $("status").textContent = "Could not load the renderer: " + (err.message || err) +
      (location.protocol === "file:" ? "\nOpen this page from GitHub Pages or a local web server, not as a file." : "");
  }
})();
</script>
</body></html>"""


def write(out_dir: Path, decisions, samples, css: str) -> None:
    (out_dir / "playground-data.json").write_text(json.dumps(data(decisions, samples), ensure_ascii=False), encoding="utf-8")
    (out_dir / "playground.html").write_text(PAGE.replace("__CSS__", css).replace("__PYODIDE__", PYODIDE), encoding="utf-8")


__all__ = ["data", "write"]
