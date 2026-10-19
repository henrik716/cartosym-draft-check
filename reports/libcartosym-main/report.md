# CartoSym draft requirements vs implementations

Generated 2026-10-19 with libCartoSym (cs-canif built from ecere/libCartoSym main @ f180e04 and ecere/eC main @ 5601fab, on Ubuntu) and pycartosym 0.4.1.

Expected values are what the **draft requirement** says. `FAIL` means the implementation disagrees with the draft, which may mean the draft or the implementation is wrong. pycartosym does not evaluate expressions, so for expression cases it only reports whether the expression parses. The draft renderer is `cartosym_draft` in this repository, which implements the draft requirements; a FAIL there means it does not do what the draft says.

## Summary

| Implementation | pass | FAIL | unsupported | CRASH | error |
|---|---|---|---|---|---|
| draft renderer | 91 | 1 | 0 | 0 | 0 |
| libCartoSym | 40 | 5 | 34 | 3 | 2 |
| pycartosym | 84 | 0 | 0 | 0 | 0 |

## How the cases are run

- **libCartoSym:** the Input text is written to `expr.cql2` and evaluated with `cs-canif eval expr.cql2` (cs-canif built from ecere/libCartoSym main @ f180e04 and ecere/eC main @ 5601fab, on Ubuntu).
- **pycartosym:** expressions are only parsed, with `pycartosym.cql2.parse_text(input)`; pycartosym does not evaluate them.
- **draft renderer:** `cartosym_draft.evaluate.evaluate(expression, Context(...))`. Where a case gives its own CQL2-JSON (54 cases), that is what it evaluates, and the result is marked _(CQL2-JSON)_; otherwise the Input text is converted with `pycartosym.cql2.to_cql2_json(cql2.parse_text(input))`, whose parser mishandles some inputs (string literals in function calls, arrays, conditionals, `^`).
- **Values:** feature properties, system identifiers, style variables (`@name`) and variables set by the application that a case is evaluated with are listed under its input (_with …_).
- **Draft renderer only** (8 cases): cases that need such values. The harness does not pass them to `cs-canif` or pycartosym, so those columns show `-`.

The cases are in [`cases/`](../cases/), the calls in [`harness/adapters.py`](../harness/adapters.py), and every result with the implementation's full output in [`results.json`](results.json).

## Results by requirement

### `/req/arithmetic/add`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| arith-add | `1 + 2` | `3` | pass: 3 | pass: parses | pass: 3 |

### `/req/arithmetic/div`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| arith-div-reals | `7.0 / 2` | `3.5` | pass: 3.5 | pass: parses | pass: 3.5 |
| arith-div-integers | `7 / 2` | `3.5` | FAIL: got `3`, draft expects `3.5` | pass: parses | pass: 3.5 |
| | _Draft says `/` is always real-valued, even for two integers (`div` is integer division)._ | | | | |

### `/req/arithmetic/int-div`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| arith-int-div | `7 div 2` | `3` | CRASH: exit code -11 | pass: parses | pass: 3 |
| arith-int-div-negative | `-7 div 2` | `-3` | CRASH: exit code -11 | pass: parses | pass: -3 |
| | _Draft says truncation toward zero (floor division would give -4)._ | | | | |

### `/req/arithmetic/mod`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| arith-mod | `7 % 3` | `1` | pass: 1 | pass: parses | pass: 1 |
| arith-mod-negative | `-7 % 3` | `-1` | pass: -1 | pass: parses | pass: -1 |
| | _Draft says the result has the sign of the first operand._ | | | | |

### `/req/arithmetic/mul`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| arith-mul | `3 * 4` | `12` | pass: 12 | pass: parses | pass: 12 |

### `/req/arithmetic/pow`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| arith-pow | `2 ^ 10` | `1024` | pass: 1024.0 | pass: parses | pass: 1024 _(CQL2-JSON)_ |

### `/req/arithmetic/sub`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| arith-sub | `5 - 7` | `-2` | pass: -2 | pass: parses | pass: -2 |

### `/req/array-relations/a-contained-by`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| array-contained-by | `a_containedBy((1, 2), (1, 2, 3))` | `true` | pass: true | pass: parses | pass: true |

### `/req/array-relations/a-contains`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| array-contains | `a_contains((1, 2, 3), (1, 2))` | `true` | pass: true | pass: parses | pass: true |

### `/req/array-relations/a-equals`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| array-equals | `a_equals((1, 2), (1, 2))` | `true` | pass: true | pass: parses | pass: true |
| array-equals-order | `a_equals((1, 2), (2, 1))` | `false` | pass: false | pass: parses | pass: false |
| | _Draft says order matters._ | | | | |

### `/req/array-relations/a-overlaps`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| array-overlaps | `a_overlaps((1, 2), (2, 3))` | `true` | pass: true | pass: parses | pass: true |
| array-overlaps-none | `a_overlaps((1, 2), (3, 4))` | `false` | pass: false | pass: parses | pass: false _(CQL2-JSON)_ |

### `/req/conditional/condition`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| cond-string-then | `2 > 1 ? 'yes' : 'no'` | `yes` | pass: 'yes' | pass: parses | pass: yes _(CQL2-JSON)_ |
| cond-string-else | `2 < 1 ? 'yes' : 'no'` | `no` | pass: 'no' | pass: parses | pass: no _(CQL2-JSON)_ |

### `/req/conditional/else-exp`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| cond-false | `1 > 2 ? 10 : 20` | `20` | pass: 20 | pass: parses | pass: 20 _(CQL2-JSON)_ |

### `/req/conditional/then-exp`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| cond-true | `1 < 2 ? 10 : 20` | `10` | pass: 10 | pass: parses | pass: 10 _(CQL2-JSON)_ |

### `/req/core/arrays`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| core-array | `a_equals((1, 2, 3), (1, 2, 3))` | `true` | pass: true | pass: parses | pass: true _(CQL2-JSON)_ |

### `/req/core/expressions-field-identifiers`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| core-field-identifier | `population * 2`<br>with `population = 1500` | `3000` | - | - | pass: 3000 _(CQL2-JSON)_ |

### `/req/core/expressions-system-identifiers`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| core-system-identifier | `viz.sd < 50000`<br>with `viz.sd = 25000` | `true` | - | - | pass: true _(CQL2-JSON)_ |

### `/req/core/literals`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| core-literal-string | `'abc'` | `abc` | pass: 'abc' | pass: parses | pass: abc _(CQL2-JSON)_ |
| core-literal-real | `3.25` | `3.25` | pass: 3.25 | pass: parses | pass: 3.25 _(CQL2-JSON)_ |
| core-literal-boolean | `true` | `true` | pass: true | pass: parses | pass: true _(CQL2-JSON)_ |

### `/req/core/logical`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| core-and | `1 < 2 and 3 < 4` | `true` | pass: true | pass: parses | pass: true |
| core-or | `1 > 2 or 3 < 4` | `true` | pass: true | pass: parses | pass: true |
| core-not | `not (1 = 2)` | `true` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: true |
| core-not-in-and | `(1 < 2) and not (3 = 4)` | `true` | error: Unresolved expression (flags: ) | pass: parses | pass: true |

### `/req/core/operations`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| core-priority | `(1 + 2) * 3` | `9` | pass: 9 | pass: parses | pass: 9 |

### `/req/core/relational`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| core-equal | `2 = 2` | `true` | pass: true | pass: parses | pass: true |
| core-not-equal | `2 <> 3` | `true` | FAIL: got `-1`, draft expects `true` | pass: parses | pass: true |
| core-lesser-equal | `2 <= 2` | `true` | pass: true | pass: parses | pass: true |
| core-between | `5 between 1 and 10` | `true` | pass: true | pass: parses | pass: true |
| core-not-between | `5 not between 6 and 10` | `true` | pass: true | pass: parses | pass: true |
| core-in | `2 in (1, 2, 3)` | `true` | FAIL: got `1`, draft expects `true` | pass: parses | pass: true |
| core-not-in | `4 not in (1, 2, 3)` | `true` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: true |
| core-is-null | `null is null` | `true` | pass: true | pass: parses | pass: true |

### `/req/core/scale`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| core-scale | `visualization.scaleDenominator`<br>with `visualization.scaleDenominator = 25000` | `25000` | - | - | pass: 25000 _(CQL2-JSON)_ |

### `/req/functions/call-expressions`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| fn-call | `abs(-2)` | `2` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 2 _(CQL2-JSON)_ |
| fn-wrong-arity | `abs(1, 2)` | `<invalid>` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: <invalid> _(CQL2-JSON)_ |
| | _The draft says a call whose arguments do not match the function's parameters is invalid._ | | | | |

### `/req/functions/standard-functions`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| fn-standard | `max(1, 5, 3)` | `5` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 5 _(CQL2-JSON)_ |

### `/req/math/abs`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-abs | `abs(-2)` | `2` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 2 |

### `/req/math/acos`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-acos | `acos(1)` | `0` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 0.0 _(CQL2-JSON)_ |

### `/req/math/asin`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-asin | `asin(1)` | `1.5707963267948966` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 1.5707963267948966 _(CQL2-JSON)_ |

### `/req/math/atan`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-atan | `atan(1)` | `0.7853981633974483` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 0.7853981633974483 _(CQL2-JSON)_ |

### `/req/math/atan2`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-atan2 | `atan2(1, -1)` | `2.356194490192345` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 2.356194490192345 _(CQL2-JSON)_ |
| | _atan2(y, x): the angle of (-1, 1) is 3/4 pi. Swapped arguments would give -pi/4._ | | | | |

### `/req/math/ceil`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-ceil | `ceil(-2.5)` | `-2` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: -2 _(CQL2-JSON)_ |

### `/req/math/cos`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-cos | `cos(0)` | `1` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 1.0 _(CQL2-JSON)_ |

### `/req/math/cosh`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-cosh | `cosh(0)` | `1` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 1.0 _(CQL2-JSON)_ |

### `/req/math/exp`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-exp | `exp(1)` | `2.718281828459045` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 2.718281828459045 _(CQL2-JSON)_ |

### `/req/math/floor`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-floor | `floor(-1.5)` | `-2` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: -2 |

### `/req/math/log`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-log | `log(1)` | `0` | pass: 0.0 | pass: parses | pass: 0.0 |

### `/req/math/log10`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-log10 | `log10(1000)` | `3` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 3.0 _(CQL2-JSON)_ |

### `/req/math/max`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-max | `max(2, 3)` | `3` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 3 |

### `/req/math/min`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-min | `min(2, 3)` | `2` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 2 |

### `/req/math/pow`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-pow | `pow(2, 3)` | `8` | pass: 8.0 | pass: parses | pass: 8 |

### `/req/math/random`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-random | `random() >= 0 AND random() < 1` | `true` | CRASH: exit code -11 | pass: parses | pass: true _(CQL2-JSON)_ |

### `/req/math/rint`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-rint-half | `rint(2.5)` | `2` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 2.0 |
| | _Draft says halves round to even._ | | | | |

### `/req/math/round`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-round-half | `round(2.5)` | `3` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 3 |
| | _Draft says halves round toward positive infinity._ | | | | |

### `/req/math/sin`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-sin | `sin(0)` | `0` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 0.0 _(CQL2-JSON)_ |

### `/req/math/sinh`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-sinh | `sinh(0)` | `0` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 0.0 _(CQL2-JSON)_ |

### `/req/math/sqrt`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-sqrt | `sqrt(16)` | `4` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 4.0 |

### `/req/math/tan`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-tan | `tan(0)` | `0` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 0.0 _(CQL2-JSON)_ |

### `/req/math/tanh`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| math-tanh | `tanh(0)` | `0` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: 0.0 _(CQL2-JSON)_ |

### `/req/parameter-values/expressions`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| param-expression | `lanes * 2 + 1`<br>with `lanes = 3` | `7` | - | - | pass: 7 _(CQL2-JSON)_ |
| | _Used as a stroke width._ | | | | |

### `/req/right-hand/operands`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| rhs-function | `3 < abs(-5)` | `true` | error: Unresolved expression (flags: isNotLiteral = True, isNotLiteral = True) | pass: parses | pass: true _(CQL2-JSON)_ |
| rhs-identifier | `width < height`<br>with `width = 2`, `height = 5` | `true` | - | - | pass: true _(CQL2-JSON)_ |
| | _Needs feature properties, so only the draft renderer is run. pycartosym's parser turns `height` into the string "height"._ | | | | |

### `/req/text-manipulation/accent-insensitize`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| textfn-accent-insensitize | `accentInsensitize('Øre') = accentInsensitize('Ore')` | `true` | FAIL: got `false`, draft expects `true` | pass: parses | FAIL: got `false`, draft expects `true` _(CQL2-JSON)_ |
| | _Draft function name._ | | | | |
| textfn-accenti | `accenti('café') = accenti('cafe')` | `true` | pass: true | pass: parses | pass: true _(CQL2-JSON)_ |
| | _CQL2 name used by both implementations._ | | | | |

### `/req/text-manipulation/case-insensitize`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| textfn-case-insensitize | `caseInsensitize('ABC') = caseInsensitize('abc')` | `true` | FAIL: got `false`, draft expects `true` | pass: parses | pass: true _(CQL2-JSON)_ |
| | _Draft function name._ | | | | |
| textfn-casei | `casei('ABC') = casei('abc')` | `true` | pass: true | pass: parses | pass: true _(CQL2-JSON)_ |
| | _CQL2 name used by both implementations._ | | | | |

### `/req/text-manipulation/concatenate`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| textfn-concatenate | `concatenate('ab', 'cd')` | `'abcd'` | pass: 'abcd' | pass: parses | pass: abcd _(CQL2-JSON)_ |

### `/req/text-manipulation/format`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| textfn-format | `format('%d items', 3)` | `'3 items'` | pass: '3 items' | pass: parses | pass: 3 items |

### `/req/text-manipulation/lower-case`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| textfn-lower-case | `lowerCase('ABC')` | `'abc'` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: abc _(CQL2-JSON)_ |

### `/req/text-manipulation/substitute`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| textfn-substitute | `substitute('a-b-c', '-', '+')` | `'a+b+c'` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: a+b+c _(CQL2-JSON)_ |

### `/req/text-manipulation/upper-case`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| textfn-upper-case | `upperCase('abc')` | `'ABC'` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: ABC _(CQL2-JSON)_ |

### `/req/text-relation/contains`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| text-contains | `contains('Oslo', 'sl')` | `true` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: true _(CQL2-JSON)_ |

### `/req/text-relation/ends-with`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| text-ends-with | `endsWith('Oslo', 'lo')` | `true` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: true _(CQL2-JSON)_ |

### `/req/text-relation/like`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| text-like-percent | `'Oslo' like 'O%'` | `true` | pass: true | pass: parses | pass: true _(CQL2-JSON)_ |
| text-like-underscore | `'Oslo' like 'O_lo'` | `true` | pass: true | pass: parses | pass: true _(CQL2-JSON)_ |
| text-like-no-match | `'Oslo' like 'B%'` | `false` | pass: false | pass: parses | pass: false _(CQL2-JSON)_ |
| text-like-escape | `'50%' like '50\%'` | `true` | pass: true | pass: parses | pass: true _(CQL2-JSON)_ |
| | _The draft does not mention an escape character; libCartoSym's code supports backslash._ | | | | |

### `/req/text-relation/not-contains`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| text-not-contains | `notContains('Oslo', 'sl')` | `false` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: false _(CQL2-JSON)_ |

### `/req/text-relation/not-ends-with`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| text-not-ends-with | `notEndsWith('Oslo', 'lo')` | `false` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: false _(CQL2-JSON)_ |

### `/req/text-relation/not-like`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| text-not-like | `'Oslo' not like 'B%'` | `true` | pass: true | pass: parses | pass: true |

### `/req/text-relation/not-starts-with`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| text-not-starts-with | `notStartsWith('Oslo', 'sl')` | `true` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: true _(CQL2-JSON)_ |

### `/req/text-relation/starts-with`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| text-starts-with | `startsWith('Oslo', 'Os')` | `true` | unsupported: returned `null` (function or operator not recognised) | pass: parses | pass: true _(CQL2-JSON)_ |

### `/req/variables/definition`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| var-override | `@roadWidth * 2`<br>with `@roadWidth = 3`, `@roadWidth = 5 (set by the application)` | `10` | - | - | pass: 10 _(CQL2-JSON)_ |
| var-defined-by-expression | `@double`<br>with `@base = 4`, `@double = @base * 2` | `8` | - | - | pass: 8 _(CQL2-JSON)_ |

### `/req/variables/expression`

| Case | Input | Expected | libCartoSym | pycartosym | draft renderer |
|---|---|---|---|---|---|
| var-reference | `@roadWidth * 2`<br>with `@roadWidth = 3` | `6` | - | - | pass: 6 _(CQL2-JSON)_ |
