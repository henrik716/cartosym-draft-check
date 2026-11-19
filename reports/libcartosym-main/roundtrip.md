# Round trips through CQL2-JSON and CartoSym-JSON

Generated 2026-11-19 by [`harness/roundtrip.py`](../harness/roundtrip.py) with libCartoSym (cs-canif built from ecere/libCartoSym main @ bec9a85 and ecere/eC main @ 2280ffb, on Ubuntu) and pycartosym 0.6.5; the style examples are those of opengeospatial/cartographic-symbology at `c9808c0` (branch `main`).

This checks conversion only: whether each implementation writes the same JSON as the case or the example, and whether converting back and forth gives the same JSON again. It does not evaluate anything; [`report.md`](report.md) has the evaluation results. A difference from a case or an example may be in the case, the example or the implementation.

## Summary

| | libCartoSym | pycartosym |
|---|---|---|
| Expressions converted to CQL2-JSON (of 114) | 114 | 114 |
| Same CQL2-JSON as the case (of the 74 cases that give one) | 54 | 74 |
| Text → JSON → text → JSON gives the same JSON (of 114) | 103 | 102 |
| Examples converted from CartoSym-CSS to CartoSym-JSON (of 11) | 11 | 11 |
| Same CartoSym-JSON as the example (of 11) | 3 | 11 |
| CSS → JSON → CSS → JSON gives the same JSON (of 11) | 11 | 11 |
| The example's JSON → CSS → JSON gives it back (of 11) | 3 | 11 |

## How they are run

- **libCartoSym:** `cs-canif convert in.<ext> out.<ext>`, with `.cql2` (CQL2-Text), `.cql2json`, `.cscss` and `.csjson` (`.cs.json` is read by cs-canif as a Mapbox GL style).
- **pycartosym:** expressions with `cql2.to_cql2_json(cql2.parse_text(text))` and `cql2.to_cql2_text(json)`; styles with `cartosym in.cscss -o out.cs.json` and back.
- JSON is compared as data: member order and the spelling of numbers (`2` and `2.0`) do not matter, but `true` is not `1`. A difference is shown as the path of the first one, with the expected value (the case's or the example's, or the first conversion's for the round trip) first.

## Expressions

### libCartoSym

| Case | Input | To CQL2-JSON | Same as the case | Back to CQL2-Text | Stable |
|---|---|---|---|---|---|
| math-acos | `acos(1)` | ok | same | `ACOS(1)` | yes |
| math-asin | `asin(1)` | ok | same | `ASIN(1)` | yes |
| math-atan | `atan(1)` | ok | same | `ATAN(1)` | yes |
| math-atan2 | `atan2(1, -1)` | ok | same | `ATAN2(1, -1)` | yes |
| math-ceil | `ceil(-2.5)` | ok | same | `CEIL(-2.5)` | yes |
| math-ceil-integer | `ceil(2.5)` | ok | same | `CEIL(2.5)` | yes |
| math-floor-integer | `floor(2.5)` | ok | same | `FLOOR(2.5)` | yes |
| math-round-integer | `round(2.5)` | ok | same | `ROUND(2.5)` | yes |
| math-cos | `cos(0)` | ok | same | `COS(0)` | yes |
| math-cosh | `cosh(0)` | ok | same | `COSH(0)` | yes |
| math-exp | `exp(1)` | ok | same | `EXP(1)` | yes |
| math-log10 | `log10(1000)` | ok | same | `LOG10(1000)` | yes |
| math-sin | `sin(0)` | ok | same | `SIN(0)` | yes |
| math-sinh | `sinh(0)` | ok | same | `SINH(0)` | yes |
| math-tan | `tan(0)` | ok | same | `TAN(0)` | yes |
| math-tanh | `tanh(0)` | ok | same | `TANH(0)` | yes |
| math-random | `random() >= 0 AND random() < 1` | ok | /args/0/args: 2 items vs 1 | `>=0 AND <1` | text does not parse: error: Failed to parse in.cql2 as a CQL2-Text expression |
| text-contains | `contains('Oslo', 'sl')` | ok | same | `CONTAINS('Oslo', 'sl')` | yes |
| text-starts-with | `startsWith('Oslo', 'Os')` | ok | same | `STARTSWITH('Oslo', 'Os')` | yes |
| text-ends-with | `endsWith('Oslo', 'lo')` | ok | same | `ENDSWITH('Oslo', 'lo')` | yes |
| text-not-contains | `not contains('Oslo', 'sl')` | ok | same | `NOT CONTAINS('Oslo', 'sl')` | yes |
| text-not-starts-with | `not startsWith('Oslo', 'sl')` | ok | same | `NOT STARTSWITH('Oslo', 'sl')` | yes |
| text-not-ends-with | `not endsWith('Oslo', 'lo')` | ok | same | `NOT ENDSWITH('Oslo', 'lo')` | yes |
| cond-string-then | `2 > 1 ? 'yes' : 'no'` | ok | /: `{"op": "?:", "args": [{"op": ">", "args": [2, 1...` vs `null` | `null` | /: `null` vs `{"property": "null"}` |
| cond-string-else | `2 < 1 ? 'yes' : 'no'` | ok | /: `{"op": "?:", "args": [{"op": "<", "args": [2, 1...` vs `null` | `null` | /: `null` vs `{"property": "null"}` |
| rhs-function | `3 < abs(-5)` | ok | same | `3 < ABS(-5)` | yes |
| fn-call | `abs(-2)` | ok | same | `ABS(-2)` | yes |
| fn-wrong-arity | `pow(2)` | ok | same | `POW(2)` | yes |
| fn-wrong-type | `pow('a', 2)` | ok | /op: `"pow"` vs `"^"` | `'a' ^ 2` | yes |
| fn-int-to-real | `atan2(1, 1)` | ok | same | `ATAN2(1, 1)` | yes |
| fn-standard | `max(1, 5)` | ok | same | `MAX(1, 5)` | yes |
| fn-standard-wrong-arity | `atan2(1, 1, 1)` | ok | same | `ATAN2(1, 1, 1)` | yes |
| core-literal-string | `'abc'` | ok | same | `'abc'` | yes |
| core-literal-real | `3.25` | ok | same | `3.25` | yes |
| core-literal-boolean | `true` | ok | same | `true` | yes |
| core-array | `a_equals((1, 2, 3), (1, 2, 3))` | ok | same | `A_EQUALS((1, 2, 3), (1, 2, 3))` | yes |
| arith-add | `1 + 2` | ok | - | `1 + 2` | yes |
| arith-sub | `5 - 7` | ok | - | `5 - 7` | yes |
| arith-mul | `3 * 4` | ok | - | `3 * 4` | yes |
| arith-div-reals | `7.0 / 2` | ok | - | `7.0 / 2` | yes |
| arith-div-integers | `7 / 2` | ok | - | `7 / 2` | yes |
| arith-int-div | `7 div 2` | ok | - | `7 DIV 2` | yes |
| arith-int-div-negative | `-7 div 2` | ok | - | `-7 DIV 2` | yes |
| arith-mod | `7 % 3` | ok | - | `7  3` | /args: missing |
| arith-mod-negative | `-7 % 3` | ok | - | `-7  3` | /args: missing |
| arith-pow | `2 ^ 10` | ok | same | `2 ^ 10` | yes |
| core-and | `1 < 2 and 3 < 4` | ok | - | `1 < 2 AND 3 < 4` | yes |
| core-or | `1 > 2 or 3 < 4` | ok | - | `1 > 2 OR 3 < 4` | yes |
| core-not | `not (1 = 2)` | ok | - | `NOT(1 = 2)` | yes |
| core-not-in-and | `(1 < 2) and not (3 = 4)` | ok | - | `1 < 2 AND (NOT(3 = 4))` | yes |
| core-equal | `2 = 2` | ok | - | `2 = 2` | yes |
| core-not-equal | `2 <> 3` | ok | - | `2 <> 3` | yes |
| core-lesser-equal | `2 <= 2` | ok | - | `2 <= 2` | yes |
| core-between | `5 between 1 and 10` | ok | - | `5 BETWEEN (1 AND 10)` | yes |
| core-not-between | `5 not between 6 and 10` | ok | - | `5 NOT BETWEEN (6 AND 10)` | yes |
| core-in | `2 in (1, 2, 3)` | ok | - | `2 IN (1, 2, 3)` | yes |
| core-not-in | `4 not in (1, 2, 3)` | ok | - | `4  (1, 2, 3)` | /: `{"op": null, "args": [4, [1, 2, 3]]}` vs `null` |
| core-is-null | `null is null` | ok | - | `null IS null` | yes |
| core-priority | `(1 + 2) * 3` | ok | - | `(1 + 2) * 3` | yes |
| text-like-percent | `'Oslo' like 'O%'` | ok | same | `'Oslo' LIKE 'O%'` | yes |
| text-like-underscore | `'Oslo' like 'O_lo'` | ok | same | `'Oslo' LIKE 'O_lo'` | yes |
| text-like-no-match | `'Oslo' like 'B%'` | ok | same | `'Oslo' LIKE 'B%'` | yes |
| text-not-like | `'Oslo' not like 'B%'` | ok | - | `'Oslo' NOT LIKE 'B%'` | yes |
| text-like-escape | `'50%' like '50\%'` | ok | /args/1: `"50\\%"` vs `"50%"` | `'50%' LIKE '50%'` | yes |
| cond-true | `1 < 2 ? 10 : 20` | ok | /: `{"op": "?:", "args": [{"op": "<", "args": [1, 2...` vs `null` | `null` | /: `null` vs `{"property": "null"}` |
| cond-false | `1 > 2 ? 10 : 20` | ok | /: `{"op": "?:", "args": [{"op": ">", "args": [1, 2...` vs `null` | `null` | /: `null` vs `{"property": "null"}` |
| array-contains | `a_contains((1, 2, 3), (1, 2))` | ok | - | `A_CONTAINS((1, 2, 3), (1, 2))` | yes |
| array-contained-by | `a_containedBy((1, 2), (1, 2, 3))` | ok | - | `A_CONTAINEDBY((1, 2), (1, 2, 3))` | yes |
| array-equals | `a_equals((1, 2), (1, 2))` | ok | - | `A_EQUALS((1, 2), (1, 2))` | yes |
| array-equals-order | `a_equals((1, 2), (2, 1))` | ok | - | `A_EQUALS((1, 2), (2, 1))` | yes |
| array-overlaps | `a_overlaps((1, 2), (2, 3))` | ok | - | `A_OVERLAPS((1, 2), (2, 3))` | yes |
| array-overlaps-none | `a_overlaps((1, 2), (3, 4))` | ok | same | `A_OVERLAPS((1, 2), (3, 4))` | yes |
| textfn-case-insensitize | `caseInsensitize('ABC') = caseInsensitize('abc')` | ok | /args/0/op: `"caseInsensitize"` vs `"CASEINSENSITIZE"` | `CASEINSENSITIZE('ABC') = CASEINSENSITIZE('abc')` | yes |
| textfn-casei | `casei('ABC') = casei('abc')` | ok | same | `CASEI('ABC') = CASEI('abc')` | yes |
| textfn-accent-insensitize | `accentInsensitize('café') = accentInsensitize('cafe')` | ok | /args/0/op: `"accentInsensitize"` vs `"ACCENTINSENSITIZE"` | `ACCENTINSENSITIZE('cafu00e9') = ACCENTINSENSITIZE('cafe')` | /args/0/args/0: `"café"` vs `"cafu00e9"` |
| textfn-accenti-o-stroke | `accenti('Øre') = accenti('Ore')` | ok | same | `ACCENTI('u00d8re') = ACCENTI('Ore')` | /args/0/args/0: `"Øre"` vs `"u00d8re"` |
| textfn-accenti | `accenti('café') = accenti('cafe')` | ok | same | `ACCENTI('cafu00e9') = ACCENTI('cafe')` | /args/0/args/0: `"café"` vs `"cafu00e9"` |
| textfn-upper-case | `upperCase('abc')` | ok | same | `UPPERCASE('abc')` | yes |
| textfn-lower-case | `lowerCase('ABC')` | ok | same | `LOWERCASE('ABC')` | yes |
| textfn-concatenate | `concatenate('ab', 'cd')` | ok | same | `CONCATENATE('ab', 'cd')` | yes |
| textfn-substitute | `substitute('a-b-c', '-', '+')` | ok | same | `SUBSTITUTE('a-b-c', '-', '+')` | yes |
| textfn-format | `format('%d items', 3)` | ok | - | `FORMAT('%d items', 3)` | yes |
| math-abs | `abs(-2)` | ok | - | `ABS(-2)` | yes |
| math-pow | `pow(2, 3)` | ok | - | `2 ^ 3` | yes |
| math-min | `min(2, 3)` | ok | - | `MIN(2, 3)` | yes |
| math-max | `max(2, 3)` | ok | - | `MAX(2, 3)` | yes |
| math-max-several | `max(1, 5, 3)` | ok | - | `MAX(1, 5, 3)` | yes |
| math-min-one | `min(7)` | ok | - | `MIN(7)` | yes |
| math-log | `log(1)` | ok | - | `LOG(1)` | yes |
| math-round-half | `round(2.5)` | ok | - | `ROUND(2.5)` | yes |
| math-round-negative-half | `round(-2.5)` | ok | - | `ROUND(-2.5)` | yes |
| math-sqrt | `sqrt(16)` | ok | - | `SQRT(16)` | yes |
| math-floor | `floor(-1.5)` | ok | - | `FLOOR(-1.5)` | yes |
| neq-equal-operands | `2 <> 2` | ok | same | `2 <> 2` | yes |
| neq-reversed | `3 <> 2` | ok | same | `3 <> 2` | yes |
| neq-larger-first | `10 <> 2` | ok | same | `10 <> 2` | yes |
| neq-text | `'a' <> 'b'` | ok | same | `'a' <> 'b'` | yes |
| neq-text-equal | `'a' <> 'a'` | ok | same | `'a' <> 'a'` | yes |
| neq-no-spaces | `2<>3` | ok | same | `2 <> 3` | yes |
| neq-arithmetic | `1 + 1 <> 3` | ok | same | `(1 + 1) <> 3` | yes |
| neq-and | `1 <> 2 and 3 <> 4` | ok | same | `1 <> 2 AND 3 <> 4` | yes |
| neq-compared-to-true | `(2 <> 3) = true` | ok | same | `2 <> 3 = true` | yes |
| neq-not | `not (2 <> 2)` | ok | same | `NOT(2 <> 2)` | yes |
| null-arithmetic | `null + 1` | ok | /args/0: `null` vs `{"property": "null"}` | `null + 1` | yes |
| null-equal | `null = 1` | ok | /args/0: `null` vs `{"property": "null"}` | `null = 1` | yes |
| null-not-equal | `null <> 1` | ok | /args/0: `null` vs `{"property": "null"}` | `null <> 1` | yes |
| null-compare | `null > 1` | ok | /args/0: `null` vs `{"property": "null"}` | `null > 1` | yes |
| null-like | `null like 'a%'` | ok | /args/0: `null` vs `{"property": "null"}` | `null LIKE 'a%'` | yes |
| null-not | `not (null > 1)` | ok | /args/0/args/0: `null` vs `{"property": "null"}` | `NOT(null > 1)` | yes |
| null-and-true | `(null > 1) and true` | ok | /args/0/args/0: `null` vs `{"property": "null"}` | `null > 1 AND true` | yes |
| null-and-false | `(null > 1) and false` | ok | /args/0/args/0: `null` vs `{"property": "null"}` | `null > 1 AND false` | yes |
| null-or-true | `(null > 1) or true` | ok | /args/0/args/0: `null` vs `{"property": "null"}` | `null > 1 OR true` | yes |
| null-or-false | `(null > 1) or false` | ok | /args/0/args/0: `null` vs `{"property": "null"}` | `null > 1 OR false` | yes |
| null-is-null | `(null + 1) is null` | ok | /args/0/args/0: `null` vs `{"property": "null"}` | `null + 1 IS null` | yes |

### pycartosym

| Case | Input | To CQL2-JSON | Same as the case | Back to CQL2-Text | Stable |
|---|---|---|---|---|---|
| math-acos | `acos(1)` | ok | same | `acos(1)` | yes |
| math-asin | `asin(1)` | ok | same | `asin(1)` | yes |
| math-atan | `atan(1)` | ok | same | `atan(1)` | yes |
| math-atan2 | `atan2(1, -1)` | ok | same | `atan2(1, -1)` | yes |
| math-ceil | `ceil(-2.5)` | ok | same | `ceil(-2.5)` | yes |
| math-ceil-integer | `ceil(2.5)` | ok | same | `ceil(2.5)` | yes |
| math-floor-integer | `floor(2.5)` | ok | same | `floor(2.5)` | yes |
| math-round-integer | `round(2.5)` | ok | same | `round(2.5)` | yes |
| math-cos | `cos(0)` | ok | same | `cos(0)` | yes |
| math-cosh | `cosh(0)` | ok | same | `cosh(0)` | yes |
| math-exp | `exp(1)` | ok | same | `exp(1)` | yes |
| math-log10 | `log10(1000)` | ok | same | `log10(1000)` | yes |
| math-sin | `sin(0)` | ok | same | `sin(0)` | yes |
| math-sinh | `sinh(0)` | ok | same | `sinh(0)` | yes |
| math-tan | `tan(0)` | ok | same | `tan(0)` | yes |
| math-tanh | `tanh(0)` | ok | same | `tanh(0)` | yes |
| math-random | `random() >= 0 AND random() < 1` | ok | same | `random() >= 0 and random() < 1` | yes |
| text-contains | `contains('Oslo', 'sl')` | ok | same | `contains('Oslo', 'sl')` | yes |
| text-starts-with | `startsWith('Oslo', 'Os')` | ok | same | `startsWith('Oslo', 'Os')` | yes |
| text-ends-with | `endsWith('Oslo', 'lo')` | ok | same | `endsWith('Oslo', 'lo')` | yes |
| text-not-contains | `not contains('Oslo', 'sl')` | ok | same | `not contains('Oslo', 'sl')` | yes |
| text-not-starts-with | `not startsWith('Oslo', 'sl')` | ok | same | `not startsWith('Oslo', 'sl')` | yes |
| text-not-ends-with | `not endsWith('Oslo', 'lo')` | ok | same | `not endsWith('Oslo', 'lo')` | yes |
| cond-string-then | `2 > 1 ? 'yes' : 'no'` | ok | same | `2 > 1 ? 'yes' : 'no'` | yes |
| cond-string-else | `2 < 1 ? 'yes' : 'no'` | ok | same | `2 < 1 ? 'yes' : 'no'` | yes |
| rhs-function | `3 < abs(-5)` | ok | same | `3 < abs(-5)` | yes |
| fn-call | `abs(-2)` | ok | same | `abs(-2)` | yes |
| fn-wrong-arity | `pow(2)` | ok | same | `pow(2)` | yes |
| fn-wrong-type | `pow('a', 2)` | ok | same | `pow('a', 2)` | yes |
| fn-int-to-real | `atan2(1, 1)` | ok | same | `atan2(1, 1)` | yes |
| fn-standard | `max(1, 5)` | ok | same | `max(1, 5)` | yes |
| fn-standard-wrong-arity | `atan2(1, 1, 1)` | ok | same | `atan2(1, 1, 1)` | yes |
| core-literal-string | `'abc'` | ok | same | `'abc'` | yes |
| core-literal-real | `3.25` | ok | same | `3.25` | yes |
| core-literal-boolean | `true` | ok | same | `true` | yes |
| core-array | `a_equals((1, 2, 3), (1, 2, 3))` | ok | same | `A_EQUALS([1, 2, 3], [1, 2, 3])` | yes |
| arith-add | `1 + 2` | ok | - | `1 + 2` | yes |
| arith-sub | `5 - 7` | ok | - | `5 - 7` | yes |
| arith-mul | `3 * 4` | ok | - | `3 * 4` | yes |
| arith-div-reals | `7.0 / 2` | ok | - | `7.0 / 2` | yes |
| arith-div-integers | `7 / 2` | ok | - | `7 / 2` | yes |
| arith-int-div | `7 div 2` | ok | - | `//(7, 2)` | yes |
| arith-int-div-negative | `-7 div 2` | ok | - | `//(-7, 2)` | yes |
| arith-mod | `7 % 3` | ok | - | `%(7, 3)` | yes |
| arith-mod-negative | `-7 % 3` | ok | - | `%(-7, 3)` | yes |
| arith-pow | `2 ^ 10` | ok | same | `2 ^ 10` | yes |
| core-and | `1 < 2 and 3 < 4` | ok | - | `1 < 2 and 3 < 4` | yes |
| core-or | `1 > 2 or 3 < 4` | ok | - | `1 > 2 or 3 < 4` | yes |
| core-not | `not (1 = 2)` | ok | - | `not 1 = 2` | yes |
| core-not-in-and | `(1 < 2) and not (3 = 4)` | ok | - | `1 < 2 and not 3 = 4` | yes |
| core-equal | `2 = 2` | ok | - | `2 = 2` | yes |
| core-not-equal | `2 <> 3` | ok | - | `2 <> 3` | yes |
| core-lesser-equal | `2 <= 2` | ok | - | `2 <= 2` | yes |
| core-between | `5 between 1 and 10` | ok | - | `5 between 1 and 10` | yes |
| core-not-between | `5 not between 6 and 10` | ok | - | `5 not between 6 and 10` | yes |
| core-in | `2 in (1, 2, 3)` | ok | - | `2 in (1, 2, 3)` | yes |
| core-not-in | `4 not in (1, 2, 3)` | ok | - | `4 not in (1, 2, 3)` | yes |
| core-is-null | `null is null` | ok | - | `'None' is null` | /args/0: `null` vs `"None"` |
| core-priority | `(1 + 2) * 3` | ok | - | `(1 + 2) * 3` | yes |
| text-like-percent | `'Oslo' like 'O%'` | ok | same | `'Oslo' like 'O%'` | yes |
| text-like-underscore | `'Oslo' like 'O_lo'` | ok | same | `'Oslo' like 'O_lo'` | yes |
| text-like-no-match | `'Oslo' like 'B%'` | ok | same | `'Oslo' like 'B%'` | yes |
| text-not-like | `'Oslo' not like 'B%'` | ok | - | `'Oslo' not like 'B%'` | yes |
| text-like-escape | `'50%' like '50\%'` | ok | same | `'50%' like '50\%'` | yes |
| cond-true | `1 < 2 ? 10 : 20` | ok | same | `1 < 2 ? 10 : 20` | yes |
| cond-false | `1 > 2 ? 10 : 20` | ok | same | `1 > 2 ? 10 : 20` | yes |
| array-contains | `a_contains((1, 2, 3), (1, 2))` | ok | - | `A_CONTAINS([1, 2, 3], [1, 2])` | yes |
| array-contained-by | `a_containedBy((1, 2), (1, 2, 3))` | ok | - | `A_CONTAINEDBY([1, 2], [1, 2, 3])` | yes |
| array-equals | `a_equals((1, 2), (1, 2))` | ok | - | `A_EQUALS([1, 2], [1, 2])` | yes |
| array-equals-order | `a_equals((1, 2), (2, 1))` | ok | - | `A_EQUALS([1, 2], [2, 1])` | yes |
| array-overlaps | `a_overlaps((1, 2), (2, 3))` | ok | - | `A_OVERLAPS([1, 2], [2, 3])` | yes |
| array-overlaps-none | `a_overlaps((1, 2), (3, 4))` | ok | same | `A_OVERLAPS([1, 2], [3, 4])` | yes |
| textfn-case-insensitize | `caseInsensitize('ABC') = caseInsensitize('abc')` | ok | same | `caseInsensitize('ABC') = caseInsensitize('abc')` | yes |
| textfn-casei | `casei('ABC') = casei('abc')` | ok | same | `CASEI('ABC') = CASEI('abc')` | yes |
| textfn-accent-insensitize | `accentInsensitize('café') = accentInsensitize('cafe')` | ok | same | `accentInsensitize('café') = accentInsensitize('cafe')` | yes |
| textfn-accenti-o-stroke | `accenti('Øre') = accenti('Ore')` | ok | same | `ACCENTI('Øre') = ACCENTI('Ore')` | yes |
| textfn-accenti | `accenti('café') = accenti('cafe')` | ok | same | `ACCENTI('café') = ACCENTI('cafe')` | yes |
| textfn-upper-case | `upperCase('abc')` | ok | same | `UPPERCASE('abc')` | yes |
| textfn-lower-case | `lowerCase('ABC')` | ok | same | `LOWERCASE('ABC')` | yes |
| textfn-concatenate | `concatenate('ab', 'cd')` | ok | same | `CONCATENATE('ab', 'cd')` | yes |
| textfn-substitute | `substitute('a-b-c', '-', '+')` | ok | same | `SUBSTITUTE('a-b-c', '-', '+')` | yes |
| textfn-format | `format('%d items', 3)` | ok | - | `FORMAT('%d items', 3)` | yes |
| math-abs | `abs(-2)` | ok | - | `abs(-2)` | yes |
| math-pow | `pow(2, 3)` | ok | - | `pow(2, 3)` | yes |
| math-min | `min(2, 3)` | ok | - | `min(2, 3)` | yes |
| math-max | `max(2, 3)` | ok | - | `max(2, 3)` | yes |
| math-max-several | `max(1, 5, 3)` | ok | - | `max(1, 5, 3)` | yes |
| math-min-one | `min(7)` | ok | - | `min(7)` | yes |
| math-log | `log(1)` | ok | - | `log(1)` | yes |
| math-round-half | `round(2.5)` | ok | - | `round(2.5)` | yes |
| math-round-negative-half | `round(-2.5)` | ok | - | `round(-2.5)` | yes |
| math-sqrt | `sqrt(16)` | ok | - | `sqrt(16)` | yes |
| math-floor | `floor(-1.5)` | ok | - | `floor(-1.5)` | yes |
| neq-equal-operands | `2 <> 2` | ok | same | `2 <> 2` | yes |
| neq-reversed | `3 <> 2` | ok | same | `3 <> 2` | yes |
| neq-larger-first | `10 <> 2` | ok | same | `10 <> 2` | yes |
| neq-text | `'a' <> 'b'` | ok | same | `'a' <> 'b'` | yes |
| neq-text-equal | `'a' <> 'a'` | ok | same | `'a' <> 'a'` | yes |
| neq-no-spaces | `2<>3` | ok | same | `2 <> 3` | yes |
| neq-arithmetic | `1 + 1 <> 3` | ok | same | `1 + 1 <> 3` | yes |
| neq-and | `1 <> 2 and 3 <> 4` | ok | same | `1 <> 2 and 3 <> 4` | yes |
| neq-compared-to-true | `(2 <> 3) = true` | ok | same | `2 <> 3 = true` | yes |
| neq-not | `not (2 <> 2)` | ok | same | `not 2 <> 2` | yes |
| null-arithmetic | `null + 1` | ok | same | `'None' + 1` | /args/0: `null` vs `"None"` |
| null-equal | `null = 1` | ok | same | `'None' = 1` | /args/0: `null` vs `"None"` |
| null-not-equal | `null <> 1` | ok | same | `'None' <> 1` | /args/0: `null` vs `"None"` |
| null-compare | `null > 1` | ok | same | `'None' > 1` | /args/0: `null` vs `"None"` |
| null-like | `null like 'a%'` | ok | same | `'None' like 'a%'` | /args/0: `null` vs `"None"` |
| null-not | `not (null > 1)` | ok | same | `not 'None' > 1` | /args/0/args/0: `null` vs `"None"` |
| null-and-true | `(null > 1) and true` | ok | same | `'None' > 1 and true` | /args/0/args/0: `null` vs `"None"` |
| null-and-false | `(null > 1) and false` | ok | same | `'None' > 1 and false` | /args/0/args/0: `null` vs `"None"` |
| null-or-true | `(null > 1) or true` | ok | same | `'None' > 1 or true` | /args/0/args/0: `null` vs `"None"` |
| null-or-false | `(null > 1) or false` | ok | same | `'None' > 1 or false` | /args/0/args/0: `null` vs `"None"` |
| null-is-null | `(null + 1) is null` | ok | same | `'None' + 1 is null` | /args/0/args/0: `null` vs `"None"` |

## Styles

### libCartoSym

| Example | CSS to JSON | Same as the example's JSON | CSS → JSON → CSS → JSON stable | Example's JSON → CSS → JSON |
|---|---|---|---|---|
| 1-core | ok | same | yes | yes |
| 2-vector-polygon | ok | /stylingRules/0/nestedRules/0/$comment: missing | yes | /stylingRules/0/nestedRules/0/$comment: missing |
| 3-vector-line | ok | /stylingRules/0/nestedRules/0/nestedRules/0/$comment: missing | yes | /stylingRules/0/nestedRules/0/nestedRules/0/$comment: missing |
| 4-vector-point | ok | /stylingRules/0/nestedRules/0/nestedRules/0/$comment: missing | yes | /stylingRules/0/nestedRules/0/nestedRules/0/$comment: missing |
| 5-coverage-dem | ok | same | yes | yes |
| 6-coverage-sentinel2 | ok | /stylingRules/0/nestedRules/0/symbolizer/colorChannels: missing | yes | /stylingRules/0/nestedRules/0/symbolizer/colorChannels: missing |
| 7-coverage-ndvi | ok | same | yes | yes |
| 8-coverage-hillshading | ok | /stylingRules/0/nestedRules/0/symbolizer/$comment: missing | yes | /stylingRules/0/nestedRules/0/symbolizer/$comment: missing |
| 9-coverage-hillshading-opacity | ok | /stylingRules/0/$comment: missing | yes | /stylingRules/0/$comment: missing |
| 10-natural_earth_economies | ok | /metadata/abstract: `"This style is used to draw the economic status...` vs `"This style is used to draw the economic status...` | yes | to CartoSym-CSS: error: Warning: Value type mismatch (1:306) |
| 11-natural_earth_continents | ok | /stylingRules/5/nestedRules/0/symbolizer/label/elements/2/position/args: added (`[10, 4]`) | yes | /stylingRules/5/nestedRules/0/symbolizer/label/elements/2/position: `{"x": 10.0, "y": -4.0}` vs `[10.0, -4.0]` |

### pycartosym

| Example | CSS to JSON | Same as the example's JSON | CSS → JSON → CSS → JSON stable | Example's JSON → CSS → JSON |
|---|---|---|---|---|
| 1-core | ok | same | yes | yes |
| 2-vector-polygon | ok | same | yes | yes |
| 3-vector-line | ok | same | yes | yes |
| 4-vector-point | ok | same | yes | yes |
| 5-coverage-dem | ok | same | yes | yes |
| 6-coverage-sentinel2 | ok | same | yes | yes |
| 7-coverage-ndvi | ok | same | yes | yes |
| 8-coverage-hillshading | ok | same | yes | yes |
| 9-coverage-hillshading-opacity | ok | same | yes | yes |
| 10-natural_earth_economies | ok | same | yes | yes |
| 11-natural_earth_continents | ok | same | yes | yes |
