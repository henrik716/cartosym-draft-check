"""Navigation shared by the gallery, requirements and playground pages.

A sticky top bar with the three pages, a light/dark theme switch and, on long
pages, a "Jump to" menu;
a table of contents beside the content on wide screens; and a small script
for the menu, copyable card links and highlighting the current section.
Without JavaScript the links still work.
"""

from __future__ import annotations

import html

PAGES = [("index.html", "Gallery"), ("requirements.html", "Requirements"), ("playground.html", "Playground")]

NAV_CSS = """
[id] { scroll-margin-top: 64px; }
.topbar { position: sticky; top: 0; z-index: 10; background: var(--card); border-bottom: 1px solid var(--line); }
.topbar-in { max-width: 1600px; margin: 0 auto; padding: 8px 16px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.topbar .brand { font-weight: 600; margin-right: 6px; }
.topbar nav { display: flex; gap: 4px; }
.topbar nav a { padding: 4px 10px; border-radius: 6px; text-decoration: none; color: var(--fg); font-size: 14px; }
.topbar nav a:hover { background: var(--bg); }
.topbar nav a.active { background: var(--accent-bg); color: var(--fg); font-weight: 600; box-shadow: inset 0 -2px 0 var(--accent); }
.topbar .tools { margin-left: auto; display: flex; gap: 8px; align-items: center; }
.topbar .theme { font: inherit; font-size: 13px; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--line);
  background: var(--card); color: var(--fg); cursor: pointer; white-space: nowrap; }
.topbar .jump { max-width: 320px; font: inherit; font-size: 13px; padding: 4px 6px; border-radius: 6px;
  border: 1px solid var(--line); background: var(--card); color: var(--fg); }
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

# Inline right after the bar, so the saved theme is set before the page content is drawn.
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


def topbar(active: str, jump: list[tuple[str, str]] | None = None) -> str:
    """The sticky bar. *jump* is a list of (anchor id, label), or (None, label) for a group heading."""
    active_attr = ' class="active"'
    links = "".join(f'<a href="{href}"{active_attr if href == active else ""}>{label}</a>' for href, label in PAGES)
    select = ""
    if jump:
        opts = ['<option value="">Jump to…</option>']
        for anchor, label in jump:
            if anchor is None:
                opts.append(f'<option value="" disabled>— {html.escape(label)}</option>')
            else:
                opts.append(f'<option value="{html.escape(anchor)}">{html.escape(label)}</option>')
        select = f'<select class="jump" aria-label="Jump to a section">{"".join(opts)}</select>'
    return (f'<header class="topbar"><div class="topbar-in"><span class="brand">CartoSym draft check</span>'
            f'<nav aria-label="Pages">{links}</nav><div class="tools">{select}'
            f'<button class="theme" type="button" aria-label="Switch between light and dark">◐ Auto</button></div></div></header>'
            + THEME_SCRIPT)


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


__all__ = ["NAV_CSS", "NAV_SCRIPT", "permalink", "toc", "topbar"]
