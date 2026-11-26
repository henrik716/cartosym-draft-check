# Notes on the expression requirements (independent evaluation)

Evaluator: `evaluator/evaluate.py`. Results: `results.json` (177 cases).
Summary: 177 cases evaluated (159 expressions, 18 styles). Where a case has
`cql2_json`, the JSON was evaluated; the text was parsed separately and the
two agreed on every case that has both. Three cases give an error (minus-10,
css-04, css-06, see section 13); the rest give values or NULL.

Points where the text does not give the result, or allows more than one
reading. Each entry gives the requirement, the words that leave it open, the
readings considered, the reading implemented, and the words relied on.

## 1. Unary minus and `^` (/req/arithmetic/pow)

- Cases: minus-01 (`-2 ^ 2`), minus-02 (`- 2 ^ 2`), minus-03 (`-a ^ 2`),
  minus-09 (`-2 ^ 0.5`). minus-05 (`-(2 ^ 2)`) is not affected.
- Open words: /req/arithmetic/pow says only "the first operand raised to the
  power of the second operand". The text does not say whether a leading
  minus binds tighter than `^`. CQL2 (which the Standard builds on) is not in
  the folder, so I could not check it.
- Readings considered: (a) the sign binds tighter, so `-2 ^ 2` is 4 and
  `-2 ^ 0.5` is (-2)^0.5, which is NULL; (b) the power binds tighter, as in
  ordinary mathematics, so `-2 ^ 2` is -4 and `-2 ^ 0.5` is -1.414.
- Implemented: (a). Results: minus-01 4, minus-02 4, minus-03 9, minus-09 NULL.
- Relied on: schemas/CartoSym-CSS-Grammar.g4 lists `unaryArithmeticOperator
  expression` before `expression arithmeticOperatorExp expression`, and in
  ANTLR the earlier alternative binds tighter. Reading (b) would give -4, -4
  and -1.414 instead.

## 2. A minus after a space before a number (/req/arithmetic/sub, /req/cscss/expressions)

- Cases: minus-10 (`10 -4`), css-02 (`10-4`, subtraction), css-03 (`10 -4`,
  tuple), css-05 (`-10 -4`).
- Open words: /req/arithmetic/sub says "the first operand minus the second
  operand". Clause 16 (line 215) says "A `-` that follows whitespace and comes
  directly before a number is the sign of that number, which then starts a new
  element of the tuple ... `position: 10 -4` is the point (10, -4)."
- Readings considered: (a) `10 -4` is a subtraction, 6; (b) it is a tuple,
  so it is not a number, and the expression is an error.
- Implemented: (b) for a standalone expression (minus-10 is an error). In a
  style value `10 -4` is a tuple (css-03 [10, -4]). `10 - 4` and `10-4` are
  subtractions (css-01, css-02).
- Relied on: clause 16 line 215 and the NEGATIVE_NUMERIC_LITERAL rule in
  schemas/CartoSym-CSS-Lexer.g4. A reader who takes the sub requirement alone
  would get 6 for minus-10. This is the single most likely disagreement
  between implementations.

## 3. Accent folding (/req/text-manipulation/accent-insensitize)

- Cases: textfn-accenti-o-stroke (`Øre` vs `Ore`), textfn-accenti (`café`),
  textfn-accenti-tajik (`Тоҷикистон` vs `Точикистон`), textfn-accenti-cyrillic-seven.
- Open words: rc-text-manipulation NOTE: "CQL2 does not name a folding table,
  so implementations can differ on individual letters. Diacritic folding also
  folds letters that Unicode does not decompose, such as `Ø` to `O` and `Ł` to
  `L`, as libCartoSym does ... The closest published table is
  DiacriticFolding.txt of Unicode Technical Report #30, a withdrawn draft".
  The folding table itself is not in the folder.
- Readings considered: (a) canonical decomposition (NFD) and removal of
  combining marks, plus the non-decomposing Latin letters the NOTE names
  (Ø Ł Đ Ħ Ŧ Ð); (b) the full UTR #30 table, which I could not read (no
  access outside the folder); (c) a table that also folds Cyrillic letters
  such as ҷ to ч.
- Implemented: (a). Japanese dakuten and handakuten are kept, as the NOTE
  says. Results: Øre = Ore true, café = cafe true, Tajik false,
  cyrillic-seven false.
- Relied on: the NOTE quoted above. The two Cyrillic cases depend on the
  unnamed table; under (a) they are false. Results will differ if a reader
  uses the UTR #30 table.
- I did not consult libCartoSym, which the NOTE names as the reference.

## 4. Case folding (/req/text-manipulation/case-insensitize)

- Case: textfn-casei (`ABC` vs `abc`).
- Open words: "as the CQL2 casei function". The definition is not in the
  folder.
- Readings: `casefold()` (implemented) or lower-casing / upper-casing.
- Relied on: rc-text-manipulation line 23 "two strings differing only in
  letter case compare as equal once casei is applied to both". Only the ASCII
  case is tested, so every reading gives true.

## 5. Ordered or unordered arrays (/req/array-relations/a-equals)

- Case: array-equals-order (`a_equals((1, 2), (2, 1))`).
- Open words: clause 15 says "True if `a` and `b` have the same elements in
  the same order", and rc-array-relations.adoc has a TODO(review): "this
  compares in order, as libCartoSym does, while CQL2 Requirement 16 B
  evaluates arrays as sets ... which one CartoSym follows is not settled (see
  #154)".
- Readings: ordered (implemented: false) or as sets (true).
- Relied on: the clause 15 table. The TODO says the question is open.

## 6. NULL in comparisons and arithmetic (/req/core/operations)

- Cases: null-arithmetic, null-equal, null-not-equal, null-compare, null-like,
  null-not, null-and-true/false, null-or-true/false, null-property-missing-compare,
  null-in-null-element, and others in the null group.
- Open words: /req/core/operations: "A Renderer SHALL support evaluating
  operation expressions with a null operand as specified by CQL2." The
  folder states only the logical cases (clause 7, line 973: "`false and null`
  is false, `true or null` is true, and `not null`, `true and null`, `false or
  null` and `null and null` are NULL").
- Readings: (a) SQL/CQL2-style NULL for any comparison or arithmetic with a
  NULL operand (implemented); (b) an error.
- Relied on: the NOTE at line 1031 ("An operation whose result is not defined
  for its operands ... also evaluates to NULL") and the logical table.

## 7. Absent properties (/req/core/expressions-field-identifiers)

- Cases: null-property-missing-is-null (true), null-property-missing-compare
  (NULL).
- Open words: "resolving an Identifier Expression to the value of the named
  feature property". The text does not say what an absent property gives.
- Implemented: NULL, so `is null` is true.

## 8. NULL in `in` lists (/req/core/relational)

- Explicit in the text: an empty list gives false even for NULL
  (null-null-in-empty-list false, null-in-empty-list false). An element that
  is NULL gives NULL unless the first operand is found (null-in-null-element
  NULL, null-in-found-with-null-element true).
- Open: a NULL first operand with a non-empty list that has no NULL element.
  Not tested. Implemented: NULL.

## 9. Function calls that do not match (/req/functions/call-expressions)

- Cases: fn-wrong-arity, fn-wrong-type, fn-standard-wrong-arity: NULL.
- Explicit: rc-functions "A Renderer SHALL evaluate a FunctionCallExpression
  whose arguments do not match the parameters of the Function, in number or
  type, after these conversions, to NULL." Not an error, though the README
  asks for errors where the text says the expression cannot be evaluated. I
  followed the text and gave NULL.
- Open: a NULL argument to a function. Not tested. Implemented: NULL.
  Mixed types in comparisons (for example `'a' = 1`) are NULL. Not tested.

## 10. Style values that are expressions or wrong types (/req/cscss/expressions, /req/vector/image)

- css-01 and css-02 (`10 - 4`, `10-4` as a position): the value is an
  expression, and I give its CQL2-JSON form {"op": "-", "args": [10, 4]}. The
  folder does not say how an unevaluated expression appears in CartoSym-JSON;
  the schema's `isExpressionObject` branch was the basis.
- css-04 (`Dot { size: 10 -4 }`): a tuple where the schema's Dot.size is a
  single unitValue. I give an error. Open: whether a schema type mismatch is
  "not valid CartoSym-CSS" (the README's wording). A reader who reads it as a
  shape only would give [10, -4].
- css-06 (`10 (-4)`): not valid as an expression, so an error.
- Units: {"pt": 12}, {"mm": 6} follow the unitValue definition in the schema;
  a bare number is a number. Not open.

## 11. Style cases without `at` (neq-selector, neq-selector-no-spaces, neq-selector-and)

- These three style cases have no JSON pointer. The README says the result is
  the value at `at`. I returned the whole CartoSym-JSON document of the
  sheet (stylingRules with the selector expression and symbolizer). The
  selectors came out as {"op": "<>", "args": [{"property": "a"}, 1]}, the same
  form as the CQL2-JSON cases.

## 12. Smaller readings

- Keywords are case-insensitive (`AND` in math-random): the lexer marks
  `and`, `or`, `not`, `in`, `is`, `between` and `like` as caseInsensitive.
- Unary minus of a NUM binds before `div`, `%`, `*` (minus-07, minus-08,
  arith-int-div-negative, arith-mod-negative): from the grammar order.
- `mod` keeps the sign of the first operand (arith-mod-negative -1.0): explicit
  in rc-arithmetic.
- `format` uses Python's `%` (printf-style); `%d` with 3 gives "3 items".
  The text says ANSI C printf; I assume the same for these specifiers.
- Equality of numbers, text and booleans: only same-type comparisons are
  defined; `(2 <> 3) = true` is true (the NOTE on boolean operands, line 1068).
- `round`, `ceil`, `floor` return integers, and NULL when out of range or not
  finite (clause 7 line 852).
- Conditional with a NULL condition gives the else branch: explicit ("does
  not evaluate to true"). Not tested.
- `between` with a NULL bound: three-valued, NULL unless another result is
  decided. Not tested.
- `contains`, `startsWith`, `endsWith` and `like` are case-sensitive: implied
  by "occurs as a substring". Only case-matching data is tested.

## 13. Results that are errors

- minus-10 (`10 -4`): error (point 2).
- css-04 (`Dot { size: 10 -4 }`): error (point 10).
- css-06 (`10 (-4)`): error (point 10).
- Every other case is a value or NULL.

## Files read outside this folder

none
