"""Evaluator for the expression and style cases in ../cases.json.

Written from the draft text in ../spec only. The readings it implements are
listed in ../notes.md.
"""
import json
import math
import os
import random
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASES = os.path.join(ROOT, 'cases.json')
SCHEMA = os.path.join(ROOT, 'spec', '1-core', 'schemas', 'CartoSym-JSON.schema.json')
RESULTS = os.path.join(ROOT, 'results.json')


class Invalid(Exception):
    """Text that is not a valid expression or style sheet."""


# ------------------------------------------------------------------ tokens

KEYWORDS = {'and', 'or', 'not', 'like', 'between', 'in', 'is', 'div',
            'true', 'false', 'null'}
IDENT_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*')
NUM_RE = re.compile(r'(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?')
TWO_CHAR_OPS = ('<>', '<=', '>=')
ONE_CHAR_OPS = '=<>+-*/%^?:(),[]{};'


def to_number(text):
    if '.' in text or 'e' in text or 'E' in text:
        return float(text)
    return int(text)


def tokenize(src):
    """Tokens carry a flag `ws` (whitespace directly before them).

    A '-' that follows whitespace and directly precedes a number is a sign
    (token NEG), as in CartoSym-CSS; any other '-' is an operator (OP).
    """
    toks = []
    i = 0
    n = len(src)
    ws = False

    def add(kind, val):
        toks.append({'k': kind, 'v': val, 'ws': ws})

    while i < n:
        c = src[i]
        if c.isspace():
            ws = True
            i += 1
            continue
        if c == "'":
            j = i + 1
            buf = []
            while True:
                if j >= n:
                    raise Invalid('unterminated text literal')
                if src[j] == "'":
                    if j + 1 < n and src[j + 1] == "'":
                        buf.append("'")
                        j += 2
                        continue
                    break
                buf.append(src[j])
                j += 1
            add('STR', ''.join(buf))
            i = j + 1
        elif c == '"':
            j = src.find('"', i + 1)
            if j < 0:
                raise Invalid('unterminated quoted identifier')
            add('QID', src[i + 1:j])
            i = j + 1
        elif c == '@':
            m = IDENT_RE.match(src, i + 1)
            if not m:
                raise Invalid('@ is not followed by a name')
            add('VAR', m.group(0))
            i = m.end()
        elif c == '-' and ws and i + 1 < n and (
                src[i + 1].isdigit() or
                (src[i + 1] == '.' and i + 2 < n and src[i + 2].isdigit())):
            m = NUM_RE.match(src, i + 1)
            add('NEG', -to_number(m.group(0)))
            i = m.end()
        elif c.isdigit() or (c == '.' and i + 1 < n and src[i + 1].isdigit()):
            m = NUM_RE.match(src, i)
            add('NUM', to_number(m.group(0)))
            i = m.end()
        elif c == '_' or ('a' <= c.lower() <= 'z'):
            m = IDENT_RE.match(src, i)
            word = m.group(0)
            if '.' not in word and word.lower() in KEYWORDS:
                add('KW', word.lower())
            else:
                add('IDENT', word)
            i = m.end()
        elif src[i:i + 2] in TWO_CHAR_OPS:
            add('OP', src[i:i + 2])
            i += 2
        elif c in ONE_CHAR_OPS:
            add('OP', c)
            i += 1
        else:
            raise Invalid('unexpected character %r' % c)
        ws = False
    return toks


def describe(t):
    return '%s %r' % (t['k'], t['v'])


# ------------------------------------------------------------------ parser
# The parser builds CQL2-JSON-like trees: lists are arrays, {"op", "args"}
# are operations, {"property"} and {"sysId"} are identifiers, {"$ref"} a
# variable, and other values are literals (None is NULL).
# Precedence follows the ANTLR grammar in schemas/CartoSym-CSS-Grammar.g4,
# where earlier alternatives bind tighter: unary sign, ^, * / div %, + -,
# relational and between, not, and, or, then ?: (right-associative).

class Parser:
    def __init__(self, toks):
        self.toks = list(toks) + [{'k': 'EOF', 'v': None, 'ws': False}]
        self.i = 0

    def peek(self, off=0):
        return self.toks[min(self.i + off, len(self.toks) - 1)]

    def take(self):
        t = self.toks[self.i]
        self.i = min(self.i + 1, len(self.toks) - 1)
        return t

    def is_op(self, v, off=0):
        t = self.peek(off)
        return t['k'] == 'OP' and t['v'] == v

    def is_kw(self, v, off=0):
        t = self.peek(off)
        return t['k'] == 'KW' and t['v'] == v

    def expect_op(self, v):
        if not self.is_op(v):
            raise Invalid('expected %r, found %s' % (v, describe(self.peek())))
        self.take()

    def parse_top(self):
        node = self.expr()
        t = self.peek()
        if t['k'] == 'NEG':
            raise Invalid('"%s" is a tuple (a space, a minus sign and a number '
                          'start a new tuple element); a tuple is not a value '
                          'of a basic data type, so it is not a subtraction'
                          % self.text_so_far())
        if t['k'] != 'EOF':
            raise Invalid('unexpected %s' % describe(t))
        return node

    def text_so_far(self):
        return ' '.join(str(t['v']) for t in self.toks[:self.i + 1]
                        if t['k'] != 'EOF')

    def expr(self):
        cond = self.or_()
        if self.is_op('?'):
            self.take()
            then = self.expr()
            self.expect_op(':')
            other = self.expr()
            return {'op': '?:', 'args': [cond, then, other]}
        return cond

    def or_(self):
        left = self.and_()
        while self.is_kw('or'):
            self.take()
            left = {'op': 'or', 'args': [left, self.and_()]}
        return left

    def and_(self):
        left = self.not_()
        while self.is_kw('and'):
            self.take()
            left = {'op': 'and', 'args': [left, self.not_()]}
        return left

    def not_(self):
        if self.is_kw('not'):
            self.take()
            return {'op': 'not', 'args': [self.not_()]}
        return self.rel()

    def rel(self):
        left = self.add()
        while True:
            t = self.peek()
            if t['k'] == 'OP' and t['v'] in ('=', '<>', '<', '<=', '>', '>='):
                self.take()
                left = {'op': t['v'], 'args': [left, self.add()]}
            elif self.kw_pair('in'):
                neg = self.take_not()
                self.take()
                right = self.add()
                if not isinstance(right, list):
                    right = [right]
                left = self.maybe_not({'op': 'in', 'args': [left, right]}, neg)
            elif self.kw_pair('like'):
                neg = self.take_not()
                self.take()
                left = self.maybe_not({'op': 'like', 'args': [left, self.add()]}, neg)
            elif self.kw_pair('between'):
                neg = self.take_not()
                self.take()
                lo = self.add()
                if not self.is_kw('and'):
                    raise Invalid('between needs "and"')
                self.take()
                hi = self.add()
                left = self.maybe_not({'op': 'between', 'args': [left, lo, hi]}, neg)
            elif self.is_kw('is'):
                self.take()
                neg = False
                if self.is_kw('not'):
                    self.take()
                    neg = True
                right = self.add()
                if right is not None:
                    raise Invalid('is is only used with null')
                left = self.maybe_not({'op': 'isNull', 'args': [left]}, neg)
            else:
                return left

    def kw_pair(self, word):
        """True at `word` or at `not word`."""
        if self.is_kw(word):
            return True
        return self.is_kw('not') and self.is_kw(word, 1)

    def take_not(self):
        if self.is_kw('not'):
            self.take()
            return True
        return False

    @staticmethod
    def maybe_not(node, neg):
        return {'op': 'not', 'args': [node]} if neg else node

    def add(self):
        left = self.mul()
        while self.peek()['k'] == 'OP' and self.peek()['v'] in ('+', '-'):
            op = self.take()['v']
            left = {'op': op, 'args': [left, self.mul()]}
        return left

    def mul(self):
        left = self.pow_()
        while True:
            t = self.peek()
            if (t['k'] == 'OP' and t['v'] in ('*', '/', '%')) or (t['k'] == 'KW' and t['v'] == 'div'):
                self.take()
                left = {'op': t['v'], 'args': [left, self.pow_()]}
            else:
                return left

    def pow_(self):
        left = self.unary()
        while self.is_op('^'):
            self.take()
            left = {'op': '^', 'args': [left, self.unary()]}
        return left

    def unary(self):
        if self.is_op('-'):
            self.take()
            return {'op': '-', 'args': [self.unary()]}
        if self.is_op('+'):
            self.take()
            return self.unary()
        return self.primary()

    def primary(self):
        t = self.take()
        k = t['k']
        if k in ('NUM', 'NEG', 'STR'):
            return t['v']
        if k == 'KW':
            if t['v'] == 'true':
                return True
            if t['v'] == 'false':
                return False
            if t['v'] == 'null':
                return None
            raise Invalid('unexpected keyword %s' % t['v'])
        if k == 'QID':
            return {'property': t['v']}
        if k == 'IDENT':
            if self.is_op('('):
                return {'op': t['v'], 'args': self.args()}
            if '.' in t['v']:
                return {'sysId': t['v']}
            return {'property': t['v']}
        if k == 'VAR':
            return {'$ref': '#/$variables/' + t['v']}
        if k == 'OP' and t['v'] == '(':
            if self.is_op(')'):
                self.take()
                return []
            first = self.expr()
            if self.is_op(','):
                items = [first]
                while self.is_op(','):
                    self.take()
                    items.append(self.expr())
                self.expect_op(')')
                return items
            self.expect_op(')')
            return first
        raise Invalid('unexpected %s' % describe(t))

    def args(self):
        self.expect_op('(')
        out = []
        if self.is_op(')'):
            self.take()
            return out
        out.append(self.expr())
        while self.is_op(','):
            self.take()
            out.append(self.expr())
        self.expect_op(')')
        return out


def parse_text(src):
    return Parser(tokenize(src)).parse_top()


# ------------------------------------------------------------------ evaluation

class Ctx:
    def __init__(self, props, system, definitions, variables):
        self.props = props
        self.system = system
        self.definitions = definitions
        self.variables = variables


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def tri(x):
    """A boolean, or NULL for anything else."""
    return x if isinstance(x, bool) else None


def tri_and(a, b):
    a, b = tri(a), tri(b)
    if a is False or b is False:
        return False
    if a is True and b is True:
        return True
    return None


def tri_or(a, b):
    a, b = tri(a), tri(b)
    if a is True or b is True:
        return True
    if a is False and b is False:
        return False
    return None


def evaluate(node, ctx):
    if node is None or isinstance(node, (bool, int, float, str)):
        return node
    if isinstance(node, list):
        return [evaluate(x, ctx) for x in node]
    if 'property' in node:
        return ctx.props.get(node['property'])
    if 'sysId' in node:
        return ctx.system.get(node['sysId'])
    if '$ref' in node:
        name = node['$ref'].rsplit('/', 1)[-1]
        if name in ctx.variables:
            return evaluate(ctx.variables[name], ctx)
        if name in ctx.definitions:
            return evaluate(ctx.definitions[name], ctx)
        return None
    op = node['op']
    args = node.get('args', [])
    if op == 'and':
        return tri_and(evaluate(args[0], ctx), evaluate(args[1], ctx))
    if op == 'or':
        return tri_or(evaluate(args[0], ctx), evaluate(args[1], ctx))
    if op == '?:':
        return evaluate(args[1], ctx) if evaluate(args[0], ctx) is True else evaluate(args[2], ctx)
    return apply_op(op, [evaluate(a, ctx) for a in args])


def arith(op, a, b):
    if not (is_num(a) and is_num(b)):
        return None
    if op == '+':
        return a + b
    if op == '-':
        return a - b
    if op == '*':
        return a * b
    if op == '/':
        return None if b == 0 else a / b
    if op == 'div':
        return None if b == 0 else int(math.trunc(a / b))
    if op == '%':
        return None if b == 0 else math.fmod(a, b)
    if op == '^':
        return power(a, b)
    raise Invalid('unknown operator %s' % op)


def power(a, b):
    if a == 0 and b < 0:
        return None
    if a < 0 and not float(b).is_integer():
        return None
    try:
        return math.pow(a, b)
    except (OverflowError, ValueError):
        return None


def compare(op, a, b):
    if a is None or b is None:
        return None
    if is_num(a) and is_num(b):
        pass
    elif isinstance(a, str) and isinstance(b, str):
        pass
    elif isinstance(a, bool) and isinstance(b, bool) and op in ('=', '<>'):
        pass
    else:
        return None
    if op == '=':
        return a == b
    if op == '<>':
        return a != b
    if op == '<':
        return a < b
    if op == '<=':
        return a <= b
    if op == '>':
        return a > b
    if op == '>=':
        return a >= b
    raise Invalid('unknown comparison %s' % op)


def same(a, b):
    return compare('=', a, b) is True


def in_op(x, arr):
    if not isinstance(arr, list):
        return None
    if len(arr) == 0:
        return False
    if x is None:
        return None
    has_null = False
    for e in arr:
        if e is None:
            has_null = True
        elif same(x, e):
            return True
    return None if has_null else False


def like(s, pat):
    if not (isinstance(s, str) and isinstance(pat, str)):
        return None
    out = []
    i = 0
    while i < len(pat):
        ch = pat[i]
        if ch == '\\' and i + 1 < len(pat):
            out.append(re.escape(pat[i + 1]))
            i += 2
            continue
        if ch == '%':
            out.append('.*')
        elif ch == '_':
            out.append('.')
        else:
            out.append(re.escape(ch))
        i += 1
    return re.fullmatch(''.join(out), s, re.DOTALL) is not None


def array_fn(op, a, b):
    if not (isinstance(a, list) and isinstance(b, list)):
        return None
    if op == 'a_equals':
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if op == 'a_contains':
        return all(any(same(x, y) for y in a) for x in b)
    if op == 'a_containedBy':
        return all(any(same(x, y) for y in b) for x in a)
    if op == 'a_overlaps':
        return any(any(same(x, y) for y in b) for x in a)
    raise Invalid('unknown array function %s' % op)


EXTRA_FOLD = str.maketrans({
    'Ø': 'O', 'ø': 'o', 'Ł': 'L', 'ł': 'l', 'Đ': 'D', 'đ': 'd',
    'Ħ': 'H', 'ħ': 'h', 'Ŧ': 'T', 'ŧ': 't', 'Ð': 'D', 'ð': 'd'})
KEEP_MARKS = {'゙', '゚'}  # Japanese dakuten and handakuten


def fold_accents(s):
    s = s.translate(EXTRA_FOLD)
    d = unicodedata.normalize('NFD', s)
    return ''.join(c for c in d
                   if not (unicodedata.category(c) == 'Mn' and c not in KEEP_MARKS))


def round_half_away(x):
    if isinstance(x, int):
        return x
    return math.copysign(math.floor(abs(x) + 0.5), x)


NUM1 = {'abs', 'acos', 'asin', 'atan', 'ceil', 'cos', 'cosh', 'exp', 'floor',
        'log', 'log10', 'round', 'sin', 'sinh', 'sqrt', 'tan', 'tanh'}
NUM2 = {'atan2', 'pow'}
NUMN = {'max', 'min'}
STR1 = {'casei', 'accenti', 'lowerCase', 'upperCase'}
STR2 = {'concatenate', 'contains', 'startsWith', 'endsWith'}
ARR2 = {'a_containedBy', 'a_contains', 'a_equals', 'a_overlaps'}


def num_fn(op, v):
    x = v[0]
    try:
        if op == 'abs':
            r = abs(x)
        elif op == 'acos':
            r = math.acos(x) if -1 <= x <= 1 else None
        elif op == 'asin':
            r = math.asin(x) if -1 <= x <= 1 else None
        elif op == 'atan':
            r = math.atan(x)
        elif op == 'atan2':
            r = math.atan2(v[0], v[1])
        elif op == 'ceil':
            r = math.ceil(x)
        elif op == 'cos':
            r = math.cos(x)
        elif op == 'cosh':
            r = math.cosh(x)
        elif op == 'exp':
            r = math.exp(x)
        elif op == 'floor':
            r = math.floor(x)
        elif op == 'log':
            r = math.log(x) if x > 0 else None
        elif op == 'log10':
            r = math.log10(x) if x > 0 else None
        elif op == 'max':
            r = max(v)
        elif op == 'min':
            r = min(v)
        elif op == 'pow':
            r = power(v[0], v[1])
        elif op == 'round':
            r = round_half_away(x)
        elif op == 'sin':
            r = math.sin(x)
        elif op == 'sinh':
            r = math.sinh(x)
        elif op == 'sqrt':
            r = math.sqrt(x) if x >= 0 else None
        elif op == 'tan':
            r = math.tan(x)
        elif op == 'tanh':
            r = math.tanh(x)
        else:
            raise Invalid('unknown numeric function %s' % op)
    except (ValueError, OverflowError):
        return None
    if r is None:
        return None
    if op in ('ceil', 'floor', 'round'):
        if isinstance(r, float) and not math.isfinite(r):
            return None
        if abs(r) > 2 ** 63 - 1:
            return None
        return int(r)
    if isinstance(r, float) and not math.isfinite(r):
        return None
    return r


def str_fn(op, v):
    if op == 'casei':
        return v[0].casefold()
    if op == 'accenti':
        return fold_accents(v[0])
    if op == 'lowerCase':
        return v[0].lower()
    if op == 'upperCase':
        return v[0].upper()
    if op == 'concatenate':
        return v[0] + v[1]
    if op == 'contains':
        return v[1] in v[0]
    if op == 'startsWith':
        return v[0].startswith(v[1])
    if op == 'endsWith':
        return v[0].endswith(v[1])
    raise Invalid('unknown text function %s' % op)


def call_fn(op, v):
    n = len(v)
    if op == 'random':
        return random.random() if n == 0 else None
    if op == 'substitute':
        if n != 3 or not all(isinstance(x, str) for x in v):
            return None
        return v[0].replace(v[1], v[2]) if v[1] != '' else v[0]
    if op == 'format':
        if n < 1 or not isinstance(v[0], str):
            return None
        try:
            return v[0] % tuple(v[1:])
        except (TypeError, ValueError):
            return None
    if op in NUM1 or op in NUM2 or op in NUMN:
        if op in NUM1 and n != 1:
            return None
        if op in NUM2 and n != 2:
            return None
        if op in NUMN and n < 1:
            return None
        if any(x is None for x in v):
            return None  # null propagation: the text does not say
        if not all(is_num(x) for x in v):
            return None
        return num_fn(op, v)
    if op in STR1 or op in STR2:
        if op in STR1 and n != 1:
            return None
        if op in STR2 and n != 2:
            return None
        if any(x is None for x in v):
            return None
        if not all(isinstance(x, str) for x in v):
            return None
        return str_fn(op, v)
    if op in ARR2:
        if n != 2:
            return None
        return array_fn(op, v[0], v[1])
    raise Invalid('unknown function %s' % op)


ARITH2 = {'+', '-', '*', '/', 'div', '%', '^'}
COMPARE = {'=', '<>', '<', '<=', '>', '>='}


def apply_op(op, v):
    if op == 'not':
        x = tri(v[0])
        return None if x is None else (not x)
    if op == 'isNull':
        return v[0] is None
    if op in ARITH2 and len(v) == 2:
        if v[0] is None or v[1] is None:
            return None
        return arith(op, v[0], v[1])
    if op == '-' and len(v) == 1:
        if v[0] is None or not is_num(v[0]):
            return None
        return -v[0]
    if op in COMPARE and len(v) == 2:
        return compare(op, v[0], v[1])
    if op == 'in' and len(v) == 2:
        return in_op(v[0], v[1])
    if op == 'between' and len(v) == 3:
        return tri_and(compare('>=', v[0], v[1]), compare('<=', v[0], v[2]))
    if op == 'like' and len(v) == 2:
        return like(v[0], v[1])
    return call_fn(op, v)


# ------------------------------------------------------------------ style sheets

def load_units():
    with open(SCHEMA, encoding='utf-8') as f:
        schema = json.load(f)
    units = set()
    for entry in schema['$defs']['unitValue']['oneOf']:
        units.update(entry.get('properties', {}).keys())
    return units


UNITS = load_units()
EXPR_OPS = {'(', ')', '+', '-', '*', '/', '%', '^', '?', ':', '=', '<>', '<', '<=', '>', '>='}


def scalar(toks):
    """A single value: a number, a unit value, a text, a tuple or an expression."""
    if not toks:
        raise Invalid('missing value')
    if any(t['k'] == 'OP' and t['v'] in EXPR_OPS for t in toks) or any(t['k'] == 'KW' for t in toks):
        return Parser(toks).parse_top()
    items = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t['k'] in ('NUM', 'NEG'):
            i += 1
            if i < len(toks) and toks[i]['k'] == 'IDENT' and toks[i]['v'] in UNITS:
                items.append({toks[i]['v']: t['v']})
                i += 1
            else:
                items.append(t['v'])
        elif t['k'] in ('STR', 'IDENT', 'QID'):
            items.append(t['v'])
            i += 1
        else:
            raise Invalid('unexpected %s in a value' % describe(t))
    return items[0] if len(items) == 1 else items


def put(out, key, val):
    parts = key.split('.')
    d = out
    for p in parts[:-1]:
        d = d.setdefault(p, {})
        if not isinstance(d, dict):
            raise Invalid('%s is not an object' % key)
    d[parts[-1]] = val


class StyleParser(Parser):
    def parse_sheet(self):
        rules = []
        while self.peek()['k'] != 'EOF':
            if self.is_op('['):
                self.take()
                toks = []
                while not self.is_op(']'):
                    if self.peek()['k'] == 'EOF':
                        raise Invalid('unterminated selector')
                    toks.append(self.take())
                self.take()
                selector = Parser(toks).parse_top()
            else:
                t = self.take()
                if t['k'] not in ('IDENT', 'QID'):
                    raise Invalid('expected a styling rule, found %s' % describe(t))
                selector = {'name': t['v']}
            self.expect_op('{')
            body = self.block('}')
            rules.append({'selector': selector, 'symbolizer': body})
            if self.is_op(';'):
                self.take()
        return {'stylingRules': rules}

    def block(self, close):
        out = {}
        while not self.is_op(close):
            if self.is_op(';') or self.is_op(','):
                self.take()
                continue
            t = self.take()
            if t['k'] not in ('IDENT', 'KW', 'QID'):
                raise Invalid('expected a property name, found %s' % describe(t))
            self.expect_op(':')
            put(out, t['v'], self.value())
        self.take()
        return out

    def value(self):
        t = self.peek()
        if t['k'] == 'OP' and t['v'] == '{':
            self.take()
            return self.block('}')
        if t['k'] == 'OP' and t['v'] == '[':
            self.take()
            return self.list_()
        if t['k'] == 'IDENT' and self.is_op('{', 1):
            self.take()
            self.take()
            body = self.block('}')
            if t['v'] == 'Dot' and isinstance(body.get('size'), list):
                raise Invalid('a Dot size is one unitValue, not a tuple')
            return {'type': t['v'], **body}
        toks = []
        depth = 0
        while True:
            t = self.peek()
            if t['k'] == 'EOF':
                break
            if t['k'] == 'OP' and t['v'] in (';', ',', '}', ']', '{', '[') and depth == 0:
                break
            if t['k'] == 'OP' and t['v'] == '(':
                depth += 1
            if t['k'] == 'OP' and t['v'] == ')':
                depth -= 1
            toks.append(self.take())
        return scalar(toks)

    def list_(self):
        items = []
        while not self.is_op(']'):
            if self.peek()['k'] == 'EOF':
                raise Invalid('unterminated list')
            if self.is_op(','):
                self.take()
                continue
            items.append(self.value())
        self.take()
        return items


def eval_style(src, at):
    doc = StyleParser(tokenize(src)).parse_sheet()
    if at is None:
        return doc  # no pointer given: the whole CartoSym-JSON document
    cur = doc
    for part in at.split('/')[1:]:
        try:
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]
        except (KeyError, IndexError, ValueError, TypeError):
            raise Invalid('no value at %s' % at)
    return cur


# ------------------------------------------------------------------ main

def main():
    with open(CASES, encoding='utf-8') as f:
        cases = json.load(f)
    results = {}
    notes = []
    for c in cases:
        cid = c['id']
        try:
            if c['kind'] == 'expression':
                ctx = Ctx(c.get('properties', {}), c.get('system', {}),
                          c.get('definitions', {}), c.get('variables', {}))
                if 'cql2_json' in c:
                    res = evaluate(c['cql2_json'], ctx)
                    try:
                        alt = evaluate(parse_text(c['cql2_text']), ctx)
                    except Invalid as e:
                        alt = {'error': str(e)}
                    if alt != res:
                        notes.append('%s: JSON gives %s, text gives %s' % (cid, res, alt))
                else:
                    res = evaluate(parse_text(c['cql2_text']), ctx)
            else:
                res = eval_style(c['style'], c.get('at'))
        except Invalid as e:
            res = {'error': str(e)}
        results[cid] = res
    with open(RESULTS, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        f.write('\n')
    for cid, res in results.items():
        print(cid, json.dumps(res, ensure_ascii=False))
    print('--- JSON/text disagreements:')
    for line in notes:
        print(line)
    print('--- %d cases' % len(results))


if __name__ == '__main__':
    sys.exit(main())
