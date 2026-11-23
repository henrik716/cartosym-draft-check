"""Navigation shared by every page of the site.

A sticky top bar: the site name (a link to the home page), the pages, a Records menu, a light/dark theme switch
and, on long pages, a "Jump to" menu; a table of contents beside the content on wide screens; and a small script
for the menu, copyable card links and highlighting the current section. Without JavaScript the links and the
Records menu still work.

The pages live in gallery/, the home page at the repository root: *base* is the path from the page to gallery/.
The walkthroughs are records with their own styles; `insert_topbar` puts the bar into them.
"""

from __future__ import annotations

import html
import re

HOME = "home"  # the active key of the home page, index.html at the repository root
REPO = "https://github.com/henrik716/cartosym-draft-check"
# (file in gallery/, label)
PAGES = [("examples.html", "Examples"), ("requirements.html", "Requirements"), ("index.html", "Judgement calls"), ("passes.html", "Rendering passes"),
         ("playground.html", "Playground")]
# (href, label, description): files in gallery/ are relative, the rest absolute.
RECORDS = [
    ("pr133-requirements-walkthrough.html", "#133 walkthrough",
     "The Part 1 requirements class by class, as prepared for the SWG meeting of 13 November 2026, where #133 was merged"),
    ("pr192-renders-walkthrough.html", "#192 walkthrough",
     "The examples and figures in the Part 1 document, and the wording checked with independent renderers"),
    (f"{REPO}/blob/main/reports/wording-decisions.md", "Wording decisions",
     "For each requirement whose wording #192 tightened: the text before, how each reader rendered it, the reading proposed"),
    (f"{REPO}/tree/main/reports/independent", "Independent renders",
     "Renderers and expression evaluators written from the requirement text alone, with their notes and images"),
    (f"{REPO}/blob/main/reports/libcartosym-main/report.md", "Expression test report",
     "Every test case with each implementation's full output, against the latest libCartoSym (CI)"),
]

# The bar alone: what the walkthroughs get. It resets what their own `nav` rules would do to the bar.
BAR_CSS = """
[id] { scroll-margin-top: 64px; }
.topbar { position: sticky; top: 0; z-index: 10; background: var(--card); border-bottom: 1px solid var(--line);
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; line-height: 1.4; }
.topbar-in { max-width: 1600px; margin: 0 auto; padding: 8px 16px; display: flex; align-items: center; gap: 6px 14px; flex-wrap: wrap; }
.topbar .brand { font-weight: 600; margin-right: 6px; color: var(--fg); text-decoration: none; font-size: 15px; }
.topbar .brand:hover { color: var(--accent); }
.topbar nav { position: static; max-height: none; overflow: visible; display: flex; gap: 4px; flex-wrap: wrap; align-items: center; font-size: 14px; }
.topbar nav a, .topbar .records summary { padding: 4px 10px; border-radius: 6px; text-decoration: none; color: var(--fg); font-size: 14px; }
.topbar nav a:hover, .topbar .records summary:hover { background: var(--bg); }
.topbar nav a.active, .topbar .records.active summary { background: var(--accent-bg); color: var(--fg); font-weight: 600; box-shadow: inset 0 -2px 0 var(--accent); }
.topbar .records { position: relative; display: flex; align-items: center; margin-left: 6px; padding-left: 10px; border-left: 1px solid var(--line); }
.topbar .records summary { cursor: pointer; list-style: none; display: block; }
.topbar .records summary::-webkit-details-marker { display: none; }
.topbar .records summary::after { content: " ▾"; color: var(--muted); font-size: 12px; }
.topbar .records .menu { position: absolute; top: calc(100% + 6px); left: 0; z-index: 11; width: min(360px, calc(100vw - 32px));
  background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 6px; box-shadow: 0 6px 24px rgba(0,0,0,.14); }
.topbar .records .menu a { display: block; padding: 6px 10px; }
.topbar .records .menu a small { display: block; color: var(--muted); font-size: 12px; font-weight: 400; line-height: 1.35; }
.topbar .records .menu a.active { box-shadow: inset 2px 0 0 var(--accent); }
.topbar .tools { margin-left: auto; display: flex; gap: 8px; align-items: center; }
.topbar .theme { font: inherit; font-size: 13px; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--line);
  background: var(--card); color: var(--fg); cursor: pointer; white-space: nowrap; }
.topbar .jump { max-width: 320px; font: inherit; font-size: 13px; padding: 4px 6px; border-radius: 6px;
  border: 1px solid var(--line); background: var(--card); color: var(--fg); }
.record-note { max-width: 1600px; margin: 0 auto; padding: 6px 16px; font-size: 13px; color: var(--muted);
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
@media (max-width: 640px) {
  .topbar .tools { margin-left: 0; }
  .topbar .records { margin-left: 0; padding-left: 0; border-left: 0; }
  .topbar .jump { max-width: 100%; }
}
"""

NAV_CSS = BAR_CSS + """
.layout { max-width: 1600px; margin: 0 auto; }
.toc { display: none; }
@media (min-width: 1500px) {
  .layout.has-toc { display: grid; grid-template-columns: 250px minmax(0, 1fr); }
  .layout.has-toc .toc { display: block; position: sticky; top: 50px; align-self: start; max-height: calc(100vh - 60px);
    overflow: auto; padding: 28px 8px 24px 16px; font-size: 13px; }
  body.has-toc .jump { display: none; }
  .layout.has-toc main { margin: 0; width: 100%; }
}
.toc a { display: block; padding: 2px 8px; border-radius: 5px; color: var(--muted); text-decoration: none; line-height: 1.35; margin: 1px 0; }
.toc a:hover { color: var(--fg); background: var(--bg); }
.toc a.current { color: var(--fg); background: var(--accent-bg); box-shadow: inset 2px 0 0 var(--accent); }
.toc .toc-group { font-weight: 600; color: var(--fg); margin-top: 12px; }
.toc .open-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; border: 1px solid var(--muted); margin-left: 5px; vertical-align: middle; }
.permalink { margin-left: 8px; font-size: 15px; color: var(--muted); text-decoration: none; opacity: .5; }
.permalink:hover, .permalink.copied { opacity: 1; color: var(--accent); }
.up { margin-left: 10px; font-size: 13px; white-space: nowrap; }
"""

# The walkthroughs name their colors differently; the bar's names are set from theirs, so their dark mode carries over.
RECORD_TOKENS = """
:root { --card: var(--panel); --line: var(--rule); --fg: var(--ink); --bg: var(--paper);
  --accent-bg: color-mix(in srgb, var(--accent) 14%, var(--panel)); }
"""

# Inline right after the bar, so the saved theme is set before the page content is drawn.
# Also closes the Records menu on a click elsewhere or on Escape.
THEME_SCRIPT = """<script>
(() => {
  const modes = ["auto", "light", "dark"], labels = { auto: "◐ Auto", light: "☀ Light", dark: "☾ Dark" };
  const b = document.querySelector(".topbar .theme");
  let mode = "auto";
  try { mode = localStorage.getItem("theme") || "auto"; } catch (e) {}
  const apply = () => {
    if (mode === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", mode);
    b.textContent = labels[mode] || labels.auto;
    b.title = "Theme: " + mode + (mode === "auto" ? " (follows your system)" : "") + ". Click to change.";
  };
  b.addEventListener("click", () => {
    mode = modes[(modes.indexOf(mode) + 1) % modes.length];
    try { localStorage.setItem("theme", mode); } catch (e) {}
    apply();
  });
  apply();
  const rec = document.querySelector(".topbar .records");
  if (rec) {
    document.addEventListener("click", (e) => { if (rec.open && !rec.contains(e.target)) rec.open = false; });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && rec.open) { rec.open = false; rec.querySelector("summary").focus(); } });
  }
})();
</script>"""

NAV_SCRIPT = """<script>
(() => {
  const jump = document.querySelector(".jump");
  if (jump) jump.addEventListener("change", () => { if (jump.value) location.hash = jump.value; jump.value = ""; });
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a.permalink");
    if (!a || !navigator.clipboard) return;
    navigator.clipboard.writeText(location.href.split("#")[0] + a.getAttribute("href"));
    a.classList.add("copied"); a.title = "Link copied";
    setTimeout(() => { a.classList.remove("copied"); a.title = "Copy a link to this"; }, 1500);
  });
  const links = [...document.querySelectorAll(".toc a[href^='#']")];
  if (!links.length || !("IntersectionObserver" in window)) return;
  const byId = new Map(links.map((l) => [l.getAttribute("href").slice(1), l]));
  const visible = new Set();
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) e.isIntersecting ? visible.add(e.target.id) : visible.delete(e.target.id);
    const first = [...byId.keys()].find((id) => visible.has(id));
    if (!first) return;
    links.forEach((l) => l.classList.toggle("current", l === byId.get(first)));
  }, { rootMargin: "-60px 0px -60% 0px" });
  for (const id of byId.keys()) { const el = document.getElementById(id); if (el) io.observe(el); }
})();
</script>"""


def _href(target: str, base: str) -> str:
    return target if target.startswith("https://") else base + target


def topbar(active: str, jump: list[tuple[str | None, str]] | None = None, base: str = "") -> str:
    """The sticky bar.

    *active* is the file of the current page in gallery/, or HOME for the home page. *base* is the path from the
    page to gallery/ ("" for pages in gallery/, "gallery/" for the home page). *jump* is a list of (anchor id,
    label), or (None, label) for a group heading.
    """
    home = "index.html" if base else "../index.html"
    act = ' class="active" aria-current="page"'
    links = "".join(f'<a href="{_href(href, base)}"{act if href == active else ""}>{label}</a>'
                    for href, label in PAGES)
    in_records = any(href == active for href, _, _ in RECORDS)
    items = "".join(
        f'<a href="{html.escape(_href(href, base))}"{act if href == active else ""}>{html.escape(label)}'
        f"<small>{html.escape(desc)}</small></a>" for href, label, desc in RECORDS)
    links += (f'<details class="records{" active" if in_records else ""}"><summary>Records</summary>'
              f'<div class="menu">{items}</div></details>')
    select = ""
    if jump:
        opts = ['<option value="">Jump to…</option>']
        for anchor, label in jump:
            if anchor is None:
                opts.append(f'<option value="" disabled>— {html.escape(label)}</option>')
            else:
                opts.append(f'<option value="{html.escape(anchor)}">{html.escape(label)}</option>')
        select = f'<select class="jump" aria-label="Jump to a section">{"".join(opts)}</select>'
    brand_act = ' aria-current="page"' if active == HOME else ""
    return (f'<header class="topbar"><div class="topbar-in"><a class="brand" href="{home}"{brand_act}>CartoSym draft check</a>'
            f'<nav aria-label="Pages">{links}</nav><div class="tools">{select}'
            f'<button class="theme" type="button" aria-label="Switch between light and dark">◐ Auto</button></div></div></header>'
            + THEME_SCRIPT)


_BAR = re.compile(r"<!-- topbar -->.*?<!-- /topbar -->\n?", re.S)
_BAR_STYLE = re.compile(r"<!-- topbar-css -->.*?<!-- /topbar-css -->\n?", re.S)


def insert_topbar(page: str, active: str, note: str = "", extra_css: str = "") -> str:
    """Put the bar into a page with its own styles (the walkthroughs), or replace the one put there before.

    *note* is a line shown under the bar; *extra_css* adapts the page's own layout to the bar.
    """
    page = _BAR_STYLE.sub("", _BAR.sub("", page))
    style = f"<!-- topbar-css --><style>{RECORD_TOKENS}{BAR_CSS}{extra_css}</style><!-- /topbar-css -->\n"
    bar = "<!-- topbar -->" + topbar(active) + (f'<p class="record-note">{note}</p>' if note else "") + "<!-- /topbar -->\n"
    head_end = page.index("</head>")
    page = page[:head_end] + style + page[head_end:]
    body = re.search(r"<body[^>]*>\n?", page)
    if not body:
        raise ValueError("no <body> in the page")
    return page[:body.end()] + bar + page[body.end():]


def toc(items: list[tuple[str | None, str, bool]]) -> str:
    """Sidebar table of contents: (anchor id or None for a group heading, label, open-in-draft marker)."""
    out = []
    for anchor, label, is_open in items:
        if anchor is None:
            out.append(f'<div class="toc-group">{html.escape(label)}</div>')
        else:
            dot = '<span class="open-dot" title="open in draft"></span>' if is_open else ""
            out.append(f'<a href="#{html.escape(anchor)}">{html.escape(label)}{dot}</a>')
    return f'<nav class="toc" aria-label="Contents">{"".join(out)}</nav>'


def permalink(anchor: str) -> str:
    return f'<a class="permalink" href="#{html.escape(anchor)}" title="Copy a link to this" aria-label="Link to this section">#</a>'


__all__ = ["BAR_CSS", "HOME", "NAV_CSS", "NAV_SCRIPT", "PAGES", "RECORDS", "REPO", "insert_topbar", "permalink", "toc",
           "topbar"]
