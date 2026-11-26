"""Lexer for CartoSym-CSS, written from spec/1-core/schemas/CartoSym-CSS-Lexer.g4.

ANTLR lexer semantics: at each position the longest match wins; on a tie the
rule defined first in the grammar wins.  WS and comments go to hidden channels.
"""
import re

# Character classes from the lexer grammar.
_ID_START = (
    "_A-Za-zÀ-ÖØ-öø-˿Ͱ-ͽͿ-῾"
    "‌-‍⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�"
)
_ID_PART = _ID_START + "0-9̀-ͯ‿-⁀"

_WHITESPACE_CHARS = (
    "\u0009\u000A\u000B\u000C\u000D \u0085   - "
    "    　"
)
_ALPHA_NODBLQUOTE = (
    "\u0007-\u0008!#-&(-/:-\u0084\u0086-\u009F"
    "¡-ᙿᚁ-῿​-‧‪-‮‰-⁞"
    "⁠-⿿、-퟿-�"
)
_CHAR_NODBLQUOTE = "[" + _ALPHA_NODBLQUOTE + "0-9" + _WHITESPACE_CHARS + "]"
# CHARACTER : CHARACTER_NODLBQUOTE | '"' | ESCAPED_QUOTE ;  ESCAPED_QUOTE : '\'\'' | '\\\''
_CHARACTER = "(?:''|\\\\'|" + _CHAR_NODBLQUOTE + '|")'
_CHAR_PART = "'" + _CHARACTER + "*'"

_NUM = r"(?:[0-9]+(?:\.(?:[0-9]+)?)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"

# (name, regex, flags).  Order = order of definition in the .g4 file.
_RULES = [
    ("LCBR", r"\{"), ("RCBR", r"\}"), ("DOT", r"\."), ("SEMI", r";"),
    ("LSBR", r"\["), ("RSBR", r"\]"), ("LPAR", r"\("), ("RPAR", r"\)"),
    ("COMMA", r","), ("EQ", r"="), ("NEQ", r"<>"), ("LT", r"<"), ("LTEQ", r"<="),
    ("GT", r">"), ("GTEQ", r">="),
    ("IN", r"(?i:in)"), ("NOT", r"(?i:not)"), ("IS", r"(?i:is)"),
    ("LIKE", r"(?i:like)"), ("BETWEEN", r"(?i:between)"),
    ("QUESTION", r"\?"), ("COLON", r":"),
    ("AND", r"(?i:and)"), ("OR", r"(?i:or)"),
    ("MUL", r"\*"), ("DIV", r"/"), ("IDIV", r"(?i:div)"), ("MOD", r"%"),
    ("POW", r"\^"), ("MINUS", r"-"), ("PLUS", r"\+"),
    ("UNIT", r"(?:px|m|ft|pc|pt|em|inch|cm|mm)"),
    ("HEX_LITERAL", r"#[0-9a-fA-F]+"),
    ("NUMERIC_LITERAL", _NUM),
    ("NEGATIVE_NUMERIC_LITERAL", r"[ \t\r\n]+-" + _NUM),
    ("CHARACTER_LITERAL", _CHAR_PART + r"(?:[ \t\r\n]+" + _CHAR_PART + ")*"),
    ("IDENTIFIER", "(?:[" + _ID_START + "][" + _ID_PART + "]*|\"" + _CHAR_NODBLQUOTE + "*\")"),
    ("AT_SIGN", r"@"),
    ("COMMENT", r"/\*.*?\*/"),
    ("LINE_COMMENT", r"//[^\r\n]*"),
    ("WS", r"[ \t\r\n]+"),
]
_COMPILED = [(n, re.compile(rx, re.S)) for n, rx in _RULES]
_HIDDEN = {"COMMENT", "LINE_COMMENT", "WS"}

# Every alternative inside UNIT can match; ANTLR takes the longest one.
_UNIT_LONGEST = re.compile(r"inch|px|ft|pc|pt|em|cm|mm|m")


class LexError(Exception):
    pass


class Token:
    __slots__ = ("type", "text", "pos")

    def __init__(self, type_, text, pos):
        self.type, self.text, self.pos = type_, text, pos

    def __repr__(self):
        return f"{self.type}({self.text!r})"


def _longest(rx, s, i):
    """Longest match of rx at position i (Python's regex is not longest-match
    for alternations, so try to extend a CHARACTER_LITERAL greedily)."""
    m = rx.match(s, i)
    return m.end() - i if m else -1


def tokenize(s):
    toks = []
    i = 0
    n = len(s)
    while i < n:
        best_len, best_name = -1, None
        for name, rx in _COMPILED:
            if name == "UNIT":
                m = _UNIT_LONGEST.match(s, i)
                ln = m.end() - i if m else -1
            else:
                ln = _longest(rx, s, i)
            if ln > best_len:
                best_len, best_name = ln, name
        if best_len <= 0:
            raise LexError(f"unexpected character {s[i]!r} at offset {i}")
        text = s[i:i + best_len]
        if best_name not in _HIDDEN:
            toks.append(Token(best_name, text, i))
        i += best_len
    toks.append(Token("EOF", "", n))
    return toks


def string_value(lit):
    """Value of a CHARACTER_LITERAL token: the quoted parts joined with nothing
    between them (clause 16, Text literals).  '' and \\' stand for a quote
    (ESCAPED_QUOTE in the lexer); no other escape is defined, so a backslash
    followed by anything else is kept as it is."""
    parts = []
    i = 0
    while i < len(lit):
        if lit[i] != "'":
            i += 1  # whitespace between parts
            continue
        i += 1
        buf = []
        while True:
            c = lit[i]
            if c == "'" and i + 1 < len(lit) and lit[i + 1] == "'":
                buf.append("'")
                i += 2
            elif c == "\\" and i + 1 < len(lit) and lit[i + 1] == "'" and _quote_is_escape(lit, i + 1):
                buf.append("'")
                i += 2
            elif c == "'":
                i += 1
                break
            else:
                buf.append(c)
                i += 1
        parts.append("".join(buf))
    return "".join(parts)


def _quote_is_escape(lit, j):
    # A \' is an escaped quote only if the literal still closes after it.
    return lit.find("'", j + 1) != -1
