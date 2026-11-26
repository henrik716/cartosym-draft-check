"""Parser for CartoSym-CSS expressions and style sheets, written from
spec/1-core/schemas/CartoSym-CSS-Grammar.g4.

Operator precedence follows how ANTLR 4 reads the left-recursive `expression`
rule: an alternative listed earlier binds tighter, binary operators are
left-associative unless marked <assoc=right>, and the operand of a prefix
operator is parsed at that operator's own level.  The order in the grammar is

    . member   [index]        (postfix)
    unary + -                 (prefix)   <- above ^, so -2 ^ 2 is (-2) ^ 2
    ^
    * / div %
    + -
    relational (= <> < <= > >= in, not in, is, is not, like, not like)
    between / not between
    not                       (prefix)
    and
    or
    ? :                       (right-associative)

AST nodes are tuples: (kind, ...).
"""
from lexer import tokenize, string_value, Token

P_TERNARY, P_OR, P_AND, P_NOT, P_BETWEEN, P_REL, P_ADD, P_MUL, P_POW, P_UNARY, P_POSTFIX = range(1, 12)

REL_TOKENS = {"EQ": "=", "NEQ": "<>", "LT": "<", "LTEQ": "<=", "GT": ">", "GTEQ": ">="}
MUL_TOKENS = {"MUL": "*", "DIV": "/", "IDIV": "div", "MOD": "%"}
ADD_TOKENS = {"PLUS": "+", "MINUS": "-"}
CONST_START = {"NUMERIC_LITERAL", "NEGATIVE_NUMERIC_LITERAL", "HEX_LITERAL"}


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, text):
        self.toks = tokenize(text)
        self.i = 0

    # -- helpers
    def peek(self, k=0):
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def accept(self, type_):
        if self.peek().type == type_:
            return self.next()
        return None

    def expect(self, type_):
        t = self.peek()
        if t.type != type_:
            raise ParseError(f"expected {type_}, found {t.type} {t.text!r} at offset {t.pos}")
        return self.next()

    # -- expressions
    def parse_expression_only(self):
        e = self.expression()
        if self.peek().type != "EOF":
            t = self.peek()
            raise ParseError(f"unexpected {t.type} {t.text!r} at offset {t.pos}")
        return e

    def expression(self, min_prec=0, allow_tuple=True, between_bound=False):
        left = self.prefix(allow_tuple=allow_tuple, between_bound=between_bound)
        while True:
            t = self.peek()
            tt = t.type
            if tt == "DOT" and P_POSTFIX >= min_prec:
                self.next()
                name = self.expect("IDENTIFIER").text
                left = ("member", left, name)
                continue
            if tt == "LSBR" and P_POSTFIX >= min_prec:
                # expression LSBR expConstant RSBR
                save = self.i
                self.next()
                if self.peek().type in CONST_START:
                    c = self.constant()
                    if self.accept("RSBR"):
                        left = ("index", left, c)
                        continue
                self.i = save
                break
            if tt == "POW" and P_POW >= min_prec:
                self.next()
                right = self.expression(P_POW + 1, allow_tuple, between_bound)
                left = ("bin", "^", left, right)
                continue
            if tt in MUL_TOKENS and P_MUL >= min_prec:
                self.next()
                right = self.expression(P_MUL + 1, allow_tuple, between_bound)
                left = ("bin", MUL_TOKENS[tt], left, right)
                continue
            if tt in ADD_TOKENS and P_ADD >= min_prec:
                self.next()
                right = self.expression(P_ADD + 1, allow_tuple, between_bound)
                left = ("bin", ADD_TOKENS[tt], left, right)
                continue
            if between_bound:
                break
            if P_REL >= min_prec:
                op = None
                if tt in REL_TOKENS:
                    self.next()
                    op = REL_TOKENS[tt]
                elif tt == "IN":
                    self.next()
                    op = "in"
                elif tt == "NOT" and self.peek(1).type == "IN":
                    self.next(); self.next()
                    op = "not in"
                elif tt == "IS" and self.peek(1).type == "NOT":
                    self.next(); self.next()
                    op = "is not"
                elif tt == "IS":
                    self.next()
                    op = "is"
                elif tt == "LIKE":
                    self.next()
                    op = "like"
                elif tt == "NOT" and self.peek(1).type == "LIKE":
                    self.next(); self.next()
                    op = "not like"
                if op is not None:
                    right = self.expression(P_REL + 1, allow_tuple)
                    left = ("bin", op, left, right)
                    continue
            if P_BETWEEN >= min_prec and (tt == "BETWEEN" or (tt == "NOT" and self.peek(1).type == "BETWEEN")):
                neg = tt == "NOT"
                self.next()
                if neg:
                    self.next()
                lo = self.expression(P_ADD, allow_tuple=False, between_bound=True)
                self.expect("AND")
                hi = self.expression(P_ADD, allow_tuple=False, between_bound=True)
                left = ("between", neg, left, lo, hi)
                continue
            if tt == "AND" and P_AND >= min_prec:
                self.next()
                right = self.expression(P_AND + 1, allow_tuple)
                left = ("bin", "and", left, right)
                continue
            if tt == "OR" and P_OR >= min_prec:
                self.next()
                right = self.expression(P_OR + 1, allow_tuple)
                left = ("bin", "or", left, right)
                continue
            if tt == "QUESTION" and P_TERNARY >= min_prec:
                self.next()
                then = self.expression(0, allow_tuple)
                self.expect("COLON")
                els = self.expression(P_TERNARY, allow_tuple)
                left = ("cond", left, then, els)
                continue
            break
        return left

    def constant(self):
        t = self.next()
        if t.type == "HEX_LITERAL":
            return ("hex", t.text[1:])
        if t.type == "NUMERIC_LITERAL":
            v = _num(t.text)
        elif t.type == "NEGATIVE_NUMERIC_LITERAL":
            v = _num(t.text.strip())
        else:
            raise ParseError(f"expected a constant, found {t.type} {t.text!r}")
        unit = None
        if self.peek().type == "UNIT":
            unit = self.next().text
        return ("num", v, unit)

    def id_or_constant(self):
        t = self.peek()
        if t.type == "IDENTIFIER":
            self.next()
            return _ident(t)
        return self.constant()

    def starts_id_or_constant(self):
        t = self.peek()
        if t.type in CONST_START:
            return True
        if t.type == "IDENTIFIER":
            # a following ( or { would make it a call or an instance, not an idOrConstant
            return self.peek(1).type not in ("LPAR", "LCBR", "COLON")
        return False

    def maybe_tuple(self, first, allow_tuple):
        if not allow_tuple or not self.starts_id_or_constant():
            return first
        elems = [first]
        while self.starts_id_or_constant():
            elems.append(self.id_or_constant())
        return ("tuple", elems)

    def prefix(self, allow_tuple=True, between_bound=False):
        t = self.peek()
        tt = t.type
        if tt in ("MINUS", "PLUS"):
            self.next()
            operand = self.expression(P_UNARY, allow_tuple, between_bound)
            return ("neg", operand) if tt == "MINUS" else ("pos", operand)
        if tt == "NOT" and not between_bound:
            self.next()
            operand = self.expression(P_NOT, allow_tuple)
            return ("not", operand)
        if tt == "LPAR":
            self.next()
            if self.accept("RPAR"):
                return ("array", [], "(")
            first = self.expression(0, allow_tuple)
            if self.accept("COMMA"):
                elems = [first, self.expression(0, allow_tuple)]
                while self.accept("COMMA"):
                    elems.append(self.expression(0, allow_tuple))
                self.expect("RPAR")
                return ("array", elems, "(")
            self.expect("RPAR")
            # Ambiguous in the grammar: expArray ( LPAR arrayElements RPAR ) and
            # LPAR expression RPAR both match.  Read as grouping (see notes.md).
            return ("group", first)
        if tt == "LSBR":
            self.next()
            elems = []
            if not self.accept("RSBR"):
                elems.append(self.expression(0, allow_tuple))
                while self.accept("COMMA"):
                    elems.append(self.expression(0, allow_tuple))
                self.expect("RSBR")
            return ("array", elems, "[")
        if tt == "LCBR":
            return self.instance(None)
        if tt == "CHARACTER_LITERAL":
            self.next()
            return ("str", string_value(t.text))
        if tt in CONST_START:
            c = self.constant()
            return self.maybe_tuple(c, allow_tuple)
        if tt == "AT_SIGN":
            self.next()
            name = self.expect("IDENTIFIER").text
            return ("var", name)
        if tt == "IDENTIFIER":
            nt = self.peek(1).type
            if nt == "LPAR":
                # expCall comes before expInstance in the grammar: Name( ... ) is a call
                self.next()
                self.next()
                args = []
                if not self.accept("RPAR"):
                    args.append(self.expression(0, allow_tuple))
                    while self.accept("COMMA"):
                        args.append(self.expression(0, allow_tuple))
                    self.expect("RPAR")
                return ("call", t.text, args)
            if nt == "LCBR":
                self.next()
                return self.instance(t.text)
            self.next()
            return self.maybe_tuple(_ident(t), allow_tuple)
        raise ParseError(f"unexpected {tt} {t.text!r} at offset {t.pos}")

    def instance(self, cls):
        self.expect("LCBR")
        members = []  # list of (lhvalue path or None, expr)
        while self.peek().type != "RCBR":
            if self.is_assignment_start():
                path = self.lhvalue()
                self.expect("COLON")
                members.append((path, self.expression(0)))
            else:
                members.append((None, self.expression(0)))
            if self.accept("SEMI") or self.accept("COMMA"):
                continue
            if self.peek().type != "RCBR":
                t = self.peek()
                raise ParseError(f"unexpected {t.type} {t.text!r} at offset {t.pos} in instance")
        self.expect("RCBR")
        return ("instance", cls, members)

    def is_assignment_start(self):
        """lhValue: IDENTIFIER ( . IDENTIFIER | [ expConstant ] )* followed by ':'"""
        j = self.i
        toks = self.toks
        if toks[j].type != "IDENTIFIER":
            return False
        j += 1
        while True:
            if toks[j].type == "DOT" and toks[j + 1].type == "IDENTIFIER":
                j += 2
            elif toks[j].type == "LSBR" and toks[j + 1].type in CONST_START and toks[j + 2].type == "RSBR":
                j += 3
            else:
                break
        return toks[j].type == "COLON"

    def lhvalue(self):
        path = [self.expect("IDENTIFIER").text]
        while True:
            if self.accept("DOT"):
                path.append(self.expect("IDENTIFIER").text)
            elif self.peek().type == "LSBR":
                self.next()
                c = self.constant()
                self.expect("RSBR")
                path.append(int(c[1]))
            else:
                return path

    # -- style sheets
    def style_sheet(self):
        meta = []
        while self.peek().type == "DOT":
            self.next()
            name = self.expect("IDENTIFIER").text
            meta.append((name, string_value(self.expect("CHARACTER_LITERAL").text)))
        variables = []
        while self.peek().type == "AT_SIGN":
            self.next()
            name = self.expect("IDENTIFIER").text
            self.expect("EQ")
            variables.append((name, self.expression(0)))
            self.expect("SEMI")
        rules = []
        while self.peek().type != "EOF":
            rules.append(self.styling_rule())
        return {"metadata": meta, "variables": variables, "rules": rules}

    def styling_rule(self):
        layers, exprs = [], []
        while self.peek().type in ("IDENTIFIER", "LSBR"):
            if self.peek().type == "IDENTIFIER":
                layers.append(_ident_name(self.next()))
            else:
                self.next()
                exprs.append(self.expression(0))
                self.expect("RSBR")
        self.expect("LCBR")
        name = None
        if self.peek().type == "DOT":
            self.next()
            kw = self.expect("IDENTIFIER").text
            if kw != "name":
                raise ParseError(f"only .name is allowed in a styling rule, found .{kw}")
            name = string_value(self.expect("CHARACTER_LITERAL").text)
        assigns = []
        # (propertyAssignmentList SEMI)? : every assignment ends with ';'
        while self.is_assignment_start():
            path = self.lhvalue()
            self.expect("COLON")
            assigns.append((path, self.expression(0)))
            self.expect("SEMI")
        nested = []
        while self.peek().type != "RCBR":
            nested.append(self.styling_rule())
        self.expect("RCBR")
        return {"layers": layers, "selectors": exprs, "name": name, "assigns": assigns, "nested": nested}


def _num(text):
    if any(c in text for c in ".eE"):
        return float(text)
    return int(text)


def _ident_name(tok):
    t = tok.text
    return t[1:-1] if t.startswith('"') else t


def _ident(tok):
    t = tok.text
    if t.startswith('"'):
        return ("id", t[1:-1], True)
    return ("id", t, False)


def parse_expression(text):
    return Parser(text).parse_expression_only()


def parse_style(text):
    p = Parser(text)
    return p.style_sheet()
