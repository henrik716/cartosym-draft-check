"""CartoSym-CSS as HTML with its parts colored, at build time (no script on the page).

The colors are the page's JSON tokens (`--json-k` and so on in gallery.CSS), so they follow light and dark mode.
A hex color or a CSS color name gets a small swatch of itself. Anything the patterns do not know stays plain text.
"""

from __future__ import annotations

import html
import re

from .colors import NAMED_COLORS

NAMED = {k.lower(): v for k, v in NAMED_COLORS.items()}

_TOKEN = re.compile(r"""
  (?P<comment>//[^\n]*|/\*.*?\*/)
| (?P<string>'(?:[^'\\]|\\.)*')
| (?P<quoted>"(?:[^"\\]|\\.)*")
| (?P<meta>(?m:^[ \t]*)\.[A-Za-z]\w*)
| (?P<color>\#[0-9a-fA-F]{8}\b|\#[0-9a-fA-F]{6}\b|\#[0-9a-fA-F]{3,4}\b)
| (?P<sysid>\b(?:viz|visualization|dataLayer|feature|capabilities)\.[A-Za-z_][\w.]*)
| (?P<keyword>\b(?i:and|or|not|in|like|between|is|true|false|null)\b)
| (?P<prop>\b[A-Za-z_][\w.]*(?=[ \t]*:(?!:)))
| (?P<number>(?<![\w.])-?\d+(?:\.\d+)?(?:[ \t]*(?:px|pt|pc|mm|cm|in|em|ft|deg|m)\b|%)?)
| (?P<variable>@[A-Za-z_]\w*)
| (?P<word>\b[A-Za-z]+\b)
""", re.X | re.S)

CLASSES = {"comment": "c-com", "string": "c-str", "quoted": "c-id", "meta": "c-meta", "color": "c-num", "sysid": "c-sys",
           "keyword": "c-kw", "prop": "c-prop", "number": "c-num", "variable": "c-sys"}

CSS = """
pre.cscss { white-space: pre-wrap; overflow-wrap: anywhere; }
/* One block per line with a hanging indent: a long line that wraps continues under its own text, 2 characters in */
pre.cscss .ln { display: block; padding-left: calc((var(--i, 0) + 2) * 1ch); text-indent: calc((var(--i, 0) + 2) * -1ch); }
pre.cscss .ln:empty::before { content: " "; }
pre.cscss .c-com { color: var(--muted); font-style: italic; }
pre.cscss .c-str { color: var(--json-s); }
pre.cscss .c-id { color: var(--json-b); }
pre.cscss .c-meta { color: var(--accent); font-weight: 600; }
pre.cscss .c-sys { color: var(--json-b); }
pre.cscss .c-kw { color: var(--json-b); font-weight: 600; }
pre.cscss .c-prop { color: var(--json-k); }
pre.cscss .c-num { color: var(--json-n); }
pre.cscss .sw { display: inline-block; width: .8em; height: .8em; border-radius: 2px; margin-right: 3px;
  vertical-align: -1px; border: 1px solid rgba(127,127,127,.5); }
"""


def _span(cls: str, text: str) -> str:
    """*text* in a span of class *cls*, closed and reopened at each line end, so that no span crosses a line."""
    return "\n".join(f'<span class="{cls}">{html.escape(seg)}</span>' if seg else "" for seg in text.split("\n"))


def cscss(source: str) -> str:
    """The HTML inside <pre class="cscss"> for *source*: one block per line, its parts colored."""
    out, pos = [], 0
    for m in _TOKEN.finditer(source):
        out.append(html.escape(source[pos:m.start()]))
        kind = m.lastgroup
        if kind == "word":  # a CSS color name gets a swatch; other words stay plain
            if m.group(0).lower() not in NAMED:
                out.append(html.escape(m.group(0)))
                pos = m.end()
                continue
            kind, value = "color", NAMED[m.group(0).lower()]
        else:
            value = m.group(0)
        swatch = f'<span class="sw" style="background:{value}"></span>' if kind == "color" else ""
        out.append(swatch + _span(CLASSES[kind], m.group(0)))
        pos = m.end()
    out.append(html.escape(source[pos:]))
    lines = []
    for src_line, html_line in zip(source.split("\n"), "".join(out).split("\n")):
        indent = len(src_line.expandtabs(4)) - len(src_line.expandtabs(4).lstrip(" "))
        lines.append(f'<span class="ln" style="--i:{indent}">{html_line}</span>')
    return "".join(lines)


def plain(highlighted: str) -> str:
    """The source text back from cscss() (to check that nothing was lost)."""
    lines = re.findall(r'<span class="ln" style="--i:\d+">(.*?)</span>(?=<span class="ln"|$)', highlighted, flags=re.S)
    return "\n".join(html.unescape(re.sub(r"<[^>]+>", "", line)) for line in lines)


__all__ = ["CSS", "cscss", "plain"]
