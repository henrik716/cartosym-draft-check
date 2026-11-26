"""CartoSym-CSS / CQL2-Text tokenizer and parser.

Written from the ANTLR lexer and grammar in spec/1-core/schemas only.
Expressions are parsed into an AST made of plain dicts, then converted to
CQL2-JSON-like structures by to_json().
"""
import re


class ParseError(Exception):
    pass


KEYWORDS = {'in': 'IN', 'not': 'NOT', 'is': 'IS', 'like': 'LIKE', 'between': 'BETWEEN',
            'and': 'AND', 'or': 'OR', 'div': 'IDIV'}
UNITS = {'px', 'm', 'ft', 'pc', 'pt', 'em', 'inch', 'cm', 'mm'}

NUM_RE = re.compile(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?')
STR_PART_RE = re.compile(r"'(?:''|\\'|[^'])*'")
HEX_RE = re.compile(r'#[0-9a-fA-F]+')
WS_RE = re.compile(r'[ \t\r\n]+')
NEG_RE = re.compile(r'[ \t\r\n]+-(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?')


def _id_start(c):
    return c == '_' or c.isalpha()


def _id_part(c):
    return _id_start(c) or c.isdigit() or '̀' <= c <= 'ͯ' or c in '‿⁀'


def _num(text):
    if re.fullmatch(r'\d+', text):
        return int(text)
    return float(text)


def _unescape(part):
    body = part[1:-1]
    return body.replace("''", "'").replace("\\'", "'")


def tokenize(s):
    toks = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in ' \t\r\n':
            m = NEG_RE.match(s, i)
            if m:
                text = m.group(0).strip()
                toks.append(('NEG', -_num(text[1:]), i))
                i = m.end()
                continue
            i = WS_RE.match(s, i).end()
            continue
        if s.startswith('//', i):
            j = s.find('\n', i)
            i = n if j < 0 else j
            continue
        if s.startswith('/*', i):
            j = s.find('*/', i + 2)
            if j < 0:
                raise ParseError('unterminated comment')
            i = j + 2
            continue
        if c == "'":
            m = STR_PART_RE.match(s, i)
            if not m:
                raise ParseError('unterminated text literal at %d' % i)
            val = _unescape(m.group(0))
            i = m.end()
            while True:  # adjacent literal parts separated by whitespace are joined
                w = WS_RE.match(s, i)
                j = w.end() if w else i
                if w and j < n and s[j] == "'":
                    m2 = STR_PART_RE.match(s, j)
                    if not m2:
                        break
                    val += _unescape(m2.group(0))
                    i = m2.end()
                else:
                    break
            toks.append(('STR', val, i))
            continue
        if c == '"':
            j = s.find('"', i + 1)
            if j < 0:
                raise ParseError('unterminated quoted identifier')
            toks.append(('ID', (s[i + 1:j], True), i))
            i = j + 1
            continue
        if c.isdigit() or (c == '.' and i + 1 < n and s[i + 1].isdigit()):
            m = NUM_RE.match(s, i)
            toks.append(('NUM', _num(m.group(0)), i))
            i = m.end()
            continue
        if c == '#':
            m = HEX_RE.match(s, i)
            if not m:
                raise ParseError('bad hex literal')
            toks.append(('HEX', m.group(0), i))
            i = m.end()
            continue
        if _id_start(c):
            j = i + 1
            while j < n and _id_part(s[j]):
                j += 1
            word = s[i:j]
            if word.lower() in KEYWORDS:
                toks.append((KEYWORDS[word.lower()], word, i))
            elif word in UNITS:
                toks.append(('UNIT', word, i))
            else:
                toks.append(('ID', (word, False), i))
            i = j
            continue
        if s.startswith('<>', i) or s.startswith('<=', i) or s.startswith('>=', i):
            toks.append((s[i:i + 2], s[i:i + 2], i))
            i += 2
            continue
        if c in '{}.;[](),=<>?:*/%^-+@':
            toks.append((c, c, i))
            i += 1
            continue
        raise ParseError('unexpected character %r at %d' % (c, i))
    toks.append(('EOF', None, n))
    return toks


class Parser:
    def __init__(self, toks):
        self.t = toks
        self.p = 0

    # --- helpers
    def peek(self, k=0):
        return self.t[min(self.p + k, len(self.t) - 1)][0]

    def val(self, k=0):
        return self.t[min(self.p + k, len(self.t) - 1)][1]

    def next(self):
        tok = self.t[self.p]
        self.p += 1
        return tok

    def accept(self, typ):
        if self.peek() == typ:
            return self.next()
        return None

    def expect(self, typ):
        if self.peek() != typ:
            raise ParseError('expected %s but found %s at %d' % (typ, self.peek(), self.t[self.p][2]))
        return self.next()

    # --- expressions, lowest precedence first (ANTLR alternative order)
    def expression(self):
        c = self.p_or()
        if self.peek() == '?':
            self.next()
            a = self.expression()
            self.expect(':')
            b = self.expression()
            return {'k': 'cond', 'args': [c, a, b]}
        return c

    def p_or(self):
        left = self.p_and()
        while self.peek() == 'OR':
            self.next()
            left = {'k': 'op', 'op': 'or', 'args': [left, self.p_and()]}
        return left

    def p_and(self):
        left = self.p_not()
        while self.peek() == 'AND':
            self.next()
            left = {'k': 'op', 'op': 'and', 'args': [left, self.p_not()]}
        return left

    def p_not(self):
        if self.peek() == 'NOT':
            self.next()
            return {'k': 'op', 'op': 'not', 'args': [self.p_not()]}
        return self.p_between()

    def p_between(self):
        left = self.p_rel()
        neg = False
        if self.peek() == 'BETWEEN' or (self.peek() == 'NOT' and self.peek(1) == 'BETWEEN'):
            if self.peek() == 'NOT':
                self.next()
                neg = True
            self.next()
            lo = self.p_add()
            self.expect('AND')
            hi = self.p_add()
            node = {'k': 'op', 'op': 'between', 'args': [left, lo, hi]}
            if neg:
                node = {'k': 'op', 'op': 'not', 'args': [node]}
            return node
        return left

    def p_rel(self):
        left = self.p_add()
        while True:
            t = self.peek()
            if t in ('=', '<>', '<', '<=', '>', '>='):
                self.next()
                left = {'k': 'op', 'op': t, 'args': [left, self.p_add()]}
            elif t == 'IN' or (t == 'NOT' and self.peek(1) == 'IN'):
                neg = t == 'NOT'
                if neg:
                    self.next()
                self.next()
                right = self.p_add()
                node = {'k': 'op', 'op': 'in', 'args': [left, right]}
                left = {'k': 'op', 'op': 'not', 'args': [node]} if neg else node
            elif t == 'LIKE' or (t == 'NOT' and self.peek(1) == 'LIKE'):
                neg = t == 'NOT'
                if neg:
                    self.next()
                self.next()
                node = {'k': 'op', 'op': 'like', 'args': [left, self.p_add()]}
                left = {'k': 'op', 'op': 'not', 'args': [node]} if neg else node
            elif t == 'IS':
                self.next()
                neg = bool(self.accept('NOT'))
                right = self.p_add()
                if not (right.get('k') == 'lit' and right['v'] is None):
                    raise ParseError('"is" can only be used with the null literal')
                node = {'k': 'op', 'op': 'isNull', 'args': [left]}
                left = {'k': 'op', 'op': 'not', 'args': [node]} if neg else node
            else:
                return left

    def p_add(self):
        left = self.p_mul()
        while self.peek() in ('+', '-'):
            op = self.next()[0]
            left = {'k': 'op', 'op': op, 'args': [left, self.p_mul()]}
        return left

    def p_mul(self):
        left = self.p_pow()
        while self.peek() in ('*', '/', 'IDIV', '%'):
            t = self.next()[0]
            op = 'div' if t == 'IDIV' else t
            left = {'k': 'op', 'op': op, 'args': [left, self.p_pow()]}
        return left

    def p_pow(self):
        left = self.p_unary()
        while self.peek() == '^':
            self.next()
            left = {'k': 'op', 'op': '^', 'args': [left, self.p_unary()]}
        return left

    def p_unary(self):
        if self.peek() in ('-', '+'):
            op = self.next()[0]
            x = self.p_unary()
            return {'k': 'un', 'op': op, 'x': x}
        return self.p_postfix()

    def p_postfix(self):
        e = self.p_primary()
        while True:
            if self.peek() == '.' and self.peek(1) == 'ID':
                self.next()
                e = {'k': 'member', 'x': e, 'name': self.next()[1][0]}
            elif self.peek() == '[' and self.peek(1) in ('NUM', 'NEG', 'HEX'):
                self.next()
                idx = self.constant()
                self.expect(']')
                e = {'k': 'index', 'x': e, 'i': idx}
            else:
                return e

    def constant(self):
        t = self.peek()
        if t in ('NUM', 'NEG'):
            v = self.next()[1]
            u = self.next()[1] if self.peek() == 'UNIT' else None
            return {'k': 'num', 'v': v, 'u': u}
        if t == 'HEX':
            return {'k': 'hex', 'v': self.next()[1]}
        raise ParseError('constant expected')

    def is_id_or_const_ahead(self):
        t = self.peek()
        if t in ('NUM', 'NEG', 'HEX'):
            return True
        if t == 'ID' and self.peek(1) not in ('(', '{'):
            return True
        return False

    def id_or_const(self):
        if self.peek() == 'ID':
            name, quoted = self.next()[1]
            return self.ident_node(name, quoted)
        return self.constant()

    @staticmethod
    def ident_node(name, quoted):
        if not quoted:
            low = name.lower()
            if low == 'null':
                return {'k': 'lit', 'v': None}
            if low == 'true':
                return {'k': 'lit', 'v': True}
            if low == 'false':
                return {'k': 'lit', 'v': False}
        return {'k': 'id', 'name': name, 'quoted': quoted}

    def p_primary(self):
        t = self.peek()
        if t in ('NUM', 'NEG', 'HEX', 'ID'):
            if t == 'ID' and self.peek(1) == '(':
                name = self.next()[1][0]
                self.next()
                args = self.arg_list(')')
                return {'k': 'call', 'name': name, 'args': args}
            if t == 'ID' and self.peek(1) == '{':
                name = self.next()[1][0]
                return self.instance(name, '}')
            first = self.id_or_const()
            if self.is_id_or_const_ahead():
                items = [first]
                while self.is_id_or_const_ahead():
                    items.append(self.id_or_const())
                return {'k': 'tuple', 'items': items}
            return first
        if t == 'STR':
            return {'k': 'lit', 'v': self.next()[1]}
        if t == '(':
            self.next()
            if self.accept(')'):
                return {'k': 'array', 'items': []}
            e = self.expression()
            if self.peek() == ',':
                items = [e]
                while self.accept(','):
                    items.append(self.expression())
                self.expect(')')
                return {'k': 'array', 'items': items}
            self.expect(')')
            return {'k': 'paren', 'x': e}
        if t == '[':
            self.next()
            return {'k': 'array', 'items': self.arg_list(']')}
        if t == '{':
            return self.instance(None, '}')
        if t == '@':
            self.next()
            name = self.expect('ID')[1][0]
            return {'k': 'var', 'name': name}
        raise ParseError('unexpected token %s at %d' % (t, self.t[self.p][2]))

    def arg_list(self, close):
        items = []
        if self.accept(close):
            return items
        items.append(self.expression())
        while self.accept(','):
            items.append(self.expression())
        self.expect(close)
        return items

    # --- instances: [Class] { member: value ; value , ... }
    def lh_value(self):
        """Parse IDENT (. IDENT | [ n ])* when followed by ':'; returns path or None (no consumption)."""
        save = self.p
        if self.peek() != 'ID':
            return None
        path = [self.next()[1][0]]
        while True:
            if self.peek() == '.' and self.peek(1) == 'ID':
                self.next()
                path.append(self.next()[1][0])
            elif self.peek() == '[' and self.peek(1) in ('NUM',):
                self.next()
                path.append(self.next()[1])
                if not self.accept(']'):
                    self.p = save
                    return None
            else:
                break
        if self.peek() == ':':
            self.next()
            return path
        self.p = save
        return None

    def instance(self, cls, close):
        self.expect('{')
        members = []  # (path or None, expr)
        while self.peek() != close:
            path = self.lh_value()
            e = self.expression()
            members.append((path, e))
            if self.peek() in (';', ','):
                self.next()
            elif self.peek() != close:
                raise ParseError('unexpected token %s in instance' % self.peek())
        self.expect(close)
        return {'k': 'inst', 'cls': cls, 'members': members}


def parse_expression(text):
    p = Parser(tokenize(text))
    e = p.expression()
    if p.peek() != 'EOF':
        raise ParseError('unexpected token %s after expression' % p.peek())
    return e


# ---------------------------------------------------------------- AST -> JSON

POINT_PROPS = {'position', 'hotSpot'}
SYS_ROOTS = {'viz', 'visualization', 'dataLayer', 'feature', 'capabilities'}


def _dotted(e):
    """Return dotted name of identifier / member chain, or None."""
    if e['k'] == 'id':
        return [e['name']]
    if e['k'] == 'member':
        base = _dotted(e['x'])
        return None if base is None else base + [e['name']]
    return None


def to_json(e, prop=None, parent_cls=None):
    k = e['k']
    if k == 'lit':
        return e['v']
    if k == 'num':
        return {e['u']: e['v']} if e['u'] else e['v']
    if k == 'hex':
        return e['v']
    if k == 'paren':
        return to_json(e['x'], prop, parent_cls)
    if k == 'un':
        x = to_json(e['x'])
        if e['op'] == '-':
            if isinstance(x, (int, float)) and not isinstance(x, bool):
                return -x
            return {'op': '-', 'args': [0, x]}
        return x
    if k in ('id', 'member'):
        d = _dotted(e)
        if d is not None:
            if d[0] in SYS_ROOTS and not e.get('quoted', False):
                return {'sysId': '.'.join(d)}
            if len(d) == 1:
                return {'property': d[0]}
            return {'property': d[0], 'member': d[1:]}
        raise ParseError('bad member access')
    if k == 'index':
        return {'op': 'index', 'args': [to_json(e['x']), to_json(e['i'])]}
    if k == 'var':
        return {'$ref': '#/$variables/' + e['name']}
    if k == 'op':
        return {'op': e['op'], 'args': [to_json(a) for a in e['args']]}
    if k == 'cond':
        return {'op': '?:', 'args': [to_json(a) for a in e['args']]}
    if k == 'call':
        return {'op': e['name'], 'args': [to_json(a) for a in e['args']]}
    if k == 'array':
        return [to_json(a) for a in e['items']]
    if k == 'tuple':
        items = [to_json(a) for a in e['items']]
        if prop in POINT_PROPS or (prop == 'size' and parent_cls == 'Image'):
            if len(items) not in (2, 3):
                raise ParseError('a point needs two or three coordinates')
            return {n: (float(v) if isinstance(v, int) else v) for n, v in zip('xyz', items)}
        if prop == 'size':
            raise ParseError('a tuple cannot be the size of a %s' % (parent_cls or 'graphic'))
        return items
    if k == 'inst':
        return inst_to_json(e)
    raise ParseError('cannot convert %s' % k)


def _merge(dst, src):
    for key, v in src.items():
        if key in dst and isinstance(dst[key], dict) and isinstance(v, dict):
            _merge(dst[key], v)
        else:
            dst[key] = v


def assign(dst, path, value):
    """Apply 'a.b.c: v' as a partial update (rc-json: alter), 'a[1]: v' as an element update."""
    if len(path) == 1:
        dst_val = {path[0]: value}
    else:
        node = value
        for name in reversed(path[1:]):
            if isinstance(name, int):
                node = {'index': name, 'value': node}
            else:
                node = {'alter': True, name: node}
        dst_val = {path[0]: node}
    _merge(dst, dst_val)


def inst_to_json(e):
    cls = e['cls']
    out = {}
    if cls:
        out['type'] = cls
    positional = []
    for path, expr in e['members']:
        if path is None:
            positional.append(to_json(expr))
        else:
            val = to_json(expr, prop=path[0] if len(path) == 1 else path[-1], parent_cls=cls)
            assign(out, path, val)
    if positional:
        out['_positional'] = positional
    return out


# ---------------------------------------------------------------- style sheets

def parse_style(text):
    p = Parser(tokenize(text))
    style = {}
    meta_map = {'identifier': 'identifier', 'title': 'title', 'description': 'description',
                'author': 'authors', 'keyword': 'keywords', 'geoDataClass': 'geoDataClasses'}
    meta = {}
    while p.peek() == '.' and p.peek(1) == 'ID' and p.val(1)[0] in meta_map:
        p.next()
        name = p.next()[1][0]
        v = p.expect('STR')[1]
        key = meta_map[name]
        if key in ('authors', 'keywords', 'geoDataClasses'):
            meta.setdefault(key, []).append(v)
        else:
            meta[key] = v
    if meta:
        style['metadata'] = meta
    variables = {}
    while p.peek() == '@':
        p.next()
        name = p.expect('ID')[1][0]
        p.expect('=')
        variables[name] = to_json(p.expression())
        p.expect(';')
    if variables:
        style['$variables'] = variables
    rules = []
    while p.peek() != 'EOF':
        rules.append(parse_rule(p))
    style['stylingRules'] = rules
    return style


def parse_rule(p):
    names, exprs = [], []
    while p.peek() in ('ID', '['):
        if p.peek() == 'ID':
            names.append(p.next()[1][0])
        else:
            p.next()
            exprs.append(to_json(p.expression()))
            p.expect(']')
    p.expect('{')
    rule = {}
    sel = []
    if names:
        conds = [{'op': '=', 'args': [{'sysId': 'dataLayer.id'}, n]} for n in names]
        c = conds[0]
        for x in conds[1:]:
            c = {'op': 'or', 'args': [c, x]}
        sel.append(c)
    sel.extend(exprs)
    if sel:
        s = sel[-1]
        for x in reversed(sel[:-1]):
            s = {'op': 'and', 'args': [x, s]}
        rule['selector'] = s
    if p.peek() == '.' and p.peek(1) == 'ID' and p.val(1)[0] == 'name':
        p.next()
        p.next()
        rule['name'] = p.expect('STR')[1]
    symb = {}
    nested = []
    while p.peek() != '}':
        if p.peek() == 'EOF':
            raise ParseError('unexpected end of style sheet')
        path = p.lh_value()
        if path is not None:
            val = to_json(p.expression(), prop=path[-1] if not isinstance(path[-1], int) else path[0])
            assign(symb, path, val)
            if p.peek() == ';':
                p.next()
            elif p.peek() != '}':
                raise ParseError('expected ; after property value')
        else:
            nested.append(parse_rule(p))
    p.expect('}')
    if symb:
        rule['symbolizer'] = symb
    if nested:
        rule['nestedRules'] = nested
    return rule
