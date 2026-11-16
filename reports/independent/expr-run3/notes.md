# Notes: where the draft text leaves results open

Source: spec/1-core only (clauses 7, 13, 14, 15, 17, requirements rc-*.adoc, schemas/CartoSym-CSS-Lexer.g4, CartoSym-CSS-Grammar.g4, CartoSym-JSON.schema.json). CQL2 itself is not in spec/, although several requirements defer to it.

Implementation: evaluator/cql2_eval.py (semantics), evaluator/cscss_parse.py (CartoSym-CSS tokenizer, expression parser, style checker), evaluator/run.py (driver). Where a case has cql2_json the JSON form is evaluated; otherwise cql2_text is parsed. For the 82 cases that have both forms, the text parse and the JSON evaluation give the same result for 81; the exception is math-random (see N4), whose text form the grammar rejects.

Result: all 123 cases produced a result (120 expression cases, 3 style cases). No case produced {"error": ...}.

---

## A. Functions

**N1. /req/functions/call-expressions, /per/functions/type-casts**
Words: "A Renderer SHALL evaluate a FunctionCallExpression whose arguments do not match the parameters of the Function, in number or type, after these conversions, to NULL." and "A Renderer MAY convert arguments of other types to the type of the parameter ... How such arguments are converted is not specified."
Readings: (a) a text argument may be converted to a number by the optional permission, so pow('a', 2) could be a number; (b) no conversion from text, so the call is NULL. A NULL argument: the text does not say what a function returns.
Implemented: (b) for text to number, so pow('a', 2) is NULL. A NULL argument gives NULL. Arity mismatch gives NULL.
Cases: fn-wrong-arity (pow(2)) = null; fn-wrong-type (pow('a', 2)) = null.

**N2. /req/functions/standard-functions with rc-math (max, min)**
Words: "max(x : double, y : double)" and "/req/math/max: taking two numeric arguments".
Readings: exactly two arguments (the text), or a variadic max as in CQL2 (not in the text).
Implemented: exactly two arguments, so max(1, 5, 3) is NULL under N1.
Cases: fn-standard = null.

**N3. Function names: caseInsensitize / accentInsensitize versus casei / accenti**
Words: rc-text-manipulation: "caseInsensitize ... (equivalent to the CQL2 CASEI function)" and "accentInsensitize ... as the CQL2 accenti function". The TODO in the text: "align the names with the CQL2 casei and accenti used by the JSON schema ... (see #140)". The JSON schema uses op "casei" and "accenti".
Readings: (a) only caseInsensitize and accentInsensitize exist; casei and accenti are unknown functions (error); (b) both names are accepted in both encodings.
Implemented: (b), as aliases. Cases: textfn-casei (JSON op casei) = true.

**N4. /req/math/random and /req/functions/call-expressions (zero arguments)**
Words: "An Encoding SHALL support defining a call to the random standard function taking no argument." CartoSym-CSS grammar: "expCall: IDENTIFIER LPAR arguments RPAR ;" with "arguments: expression | arguments COMMA expression;", so at least one argument.
Readings: the text form random() is valid CartoSym-CSS (the requirement), or it is not (the grammar).
Implemented: the case's JSON form (op random, args []) is evaluated, giving true. The text form random() is rejected by the parser, as the grammar says. The predicate is deterministic even though random() is not.
Cases: math-random = true.

**N5. Unknown function names**
Words: none. The text does not say what an unknown function name evaluates to.
Implemented: error "unknown function" (no case uses one).

**N6. Call versus instance expression**
Words: the grammar allows IDENTIFIER LPAR ... RPAR both as expCall (arguments) and as expInstance (propertyAssignmentInferredList).
Implemented: a call, unless the first item has the form name ':' (instance). No case depends on this.

## B. Arithmetic and operators

**N7. /req/arithmetic/div versus /req/arithmetic/intDiv (names and tokens)**
Words: "div" is "real-valued quotient ... including when both operands are integers"; "intDiv" is "integer quotient ... truncated toward zero". The CartoSym-CSS lexer has DIV '/' and IDIV 'div' (the keyword).
Readings: the CQL2-text keyword div is intDiv (CartoSym-CSS sense), or div is the real quotient. Also the JSON schema arithmetic op list is "+", "-", "*", "/", "^" only; there is no intDiv or mod in JSON.
Implemented: '/' is the real quotient; the keyword div is intDiv. JSON encodings of intDiv and mod are not defined in the schema, so they are only evaluated from text (no case uses JSON for them).
Cases: arith-div-reals 3.5, arith-div-integers 3.5, arith-int-div 3, arith-int-div-negative -3.

**N8. /req/arithmetic/mod and the % token**
Words: "mod ... consistent with the intDiv operator (i.e., the result has the sign of the first operand)". The grammar uses '%' (MOD). In CQL2 % is the LIKE wildcard, but in the text it appears only inside literals.
Implemented: '%' is mod with the sign of the first operand (-7 % 3 = -1). No JSON encoding (see N7).
Cases: arith-mod 1, arith-mod-negative -1.

**N9. Operator precedence and associativity**
Words: "/req/core/operations: An Encoding SHALL support defining the priority of expressions using multiple operators (e.g., using parentheses)" and "A Renderer SHALL support evaluating operation expressions while respecting the priority of operations." The text gives no table of precedence.
Readings: (a) conventional mathematics, where -2 ^ 2 = -4 and ^ is right-associative (2 ^ 3 ^ 2 = 512); (b) the order of alternatives in CartoSym-CSS-Grammar.g4 (ANTLR gives earlier alternatives higher precedence): unary +/- binds tighter than ^, ^ is left-associative, and NOT binds looser than comparisons but tighter than AND.
Implemented: (b). Results: -2 ^ 2 = 4; 2 ^ 3 ^ 2 = 64; not 1 = 2 and true = true. Precedence used: ?: < or < and < not < relational (=, <>, <, <=, >, >=, in, like, is, between, all at one level, left-associative) < + - < * / div % < ^ < unary + -.
Cases: none depend on this directly.

**N10. /req/core/operations, null operands ("as specified by CQL2")**
Words: "A Renderer SHALL support evaluating operation expressions with a null operand as specified by CQL2." CQL2 is not in spec/. /req/core/selector NOTE says only that a selector evaluating to null does not select.
Readings: (a) three-valued logic as in CQL2: NULL propagates through arithmetic, comparisons, LIKE, BETWEEN and IN; AND and OR are Kleene; NOT NULL is NULL; "is null" is true only for NULL; (b) NULL compares as false; (c) error.
Implemented: (a). Results: null + 1 = null; null = 1 = null; null <> 1 = null; null > 1 = null; null like 'a%' = null; not (null > 1) = null; (null > 1) and true = null; (null > 1) and false = false; (null > 1) or true = true; (null > 1) or false = null; (null + 1) is null = true; null is null = true.
Cases: null-arithmetic, null-equal, null-not-equal, null-compare, null-like, null-not, null-and-true, null-and-false, null-or-true, null-or-false, null-is-null.

**N11. Operations on incompatible types, and NULL inside IN or BETWEEN**
Words: none. The text does not say what happens for text + number, boolean < boolean, not on a number, is with a non-null right operand (the table says "only used with null"), or NULL elements in an array of IN.
Implemented: NULL for incompatible types (boolean only supports = and <>). "x is 1" is an error. IN: NULL if x is NULL or the array is not an array; true if x equals an element; NULL if no match and some comparison was NULL; otherwise false. BETWEEN: NULL if any operand is NULL.
Cases: none directly.

**N12. Undefined arithmetic results (domain and zero)**
Words: none. Division by zero, intDiv or mod by zero, sqrt(-1), log(0), acos(2), pow(-8, 1/3), overflow and non-finite results are not mentioned.
Implemented: NULL for the function domain and zero divisors; a non-finite result is an error.
Cases: none in the suite; probed only.

**N13. Result types of +, -, *, ^ and of round, ceil and floor**
Words: rc-arithmetic gives "Numeric" only. rc-math gives "round(x : double) long", while ceil and floor return double.
Implemented: integer when both operands are integers (for ^ with a non-negative integer exponent), otherwise real. round returns an integer; ceil, floor, pow and the other math functions return reals. Values compare equal numerically; this only affects JSON output (8.0 versus 8).
Cases: arith-pow 1024, math-pow 8.0, math-round-half 3, math-ceil-integer 3.0 (values agree numerically).

## C. Text

**N14. /req/text-relation/like: escape characters and case**
Words: "% matches any sequence of zero or more characters and _ matches exactly one character." No escape character is defined. No statement on case sensitivity.
Readings for '50%' like '50\%': (a) the backslash is an ordinary character, so the pattern is "50\" followed by anything, and '50%' does not match (false); (b) the backslash escapes %, so the match is literal (true).
Implemented: (a) (no escape mechanism; the backslash is ordinary). LIKE is case-sensitive: 'Oslo' like 'oslo' is false.
Cases: text-like-escape = false. The JSON schema has no escape either.

**N15. /req/text-relation/not-like**
Words: "A Renderer SHALL support evaluating a notLike operation expression to the logical negation of the equivalent like operation expression." TODO in the text: "the JSON schema has no notLike: add it, or state that it is encoded as not applied to like (see #140)."
Implemented: not(like), including for NULL (NULL stays NULL).
Cases: text-not-like = true.

**N16. /req/text-manipulation/caseInsensitize: folding method**
Words: "s made suitable for case-insensitive comparison" and "two strings differing only in letter case compare as equal once both are case-insensitized".
Readings: lowercase, uppercase, or full Unicode case folding.
Implemented: Python str.casefold(). The cases hold under every reading.
Cases: textfn-case-insensitize = true, textfn-casei = true.

**N17. /req/text-manipulation/accentInsensitize (accent and diacritic folding table)**
Words: "CQL2 does not name a folding table, so implementations can differ on individual letters. Diacritic folding also folds letters that Unicode does not decompose, such as Ø to O and Ł to L, as libCartoSym does, while letters that would need a one-to-many folding, such as ß and Æ, stay as they are. As CQL2 recommends, the Japanese dakuten and handakuten are not removed. The closest published table is DiacriticFolding.txt of Unicode Technical Report #30, a withdrawn draft with a few known errors."
Readings: (a) only the letters named in the NOTE, plus removal of combining marks after canonical decomposition; (b) a full folding table (the UTR #30 table, which is outside spec/ and has known errors). The text gives no complete list, so letters such as Đ, Ħ or dotless ı are undefined.
Implemented: (a). Canonical decomposition (NFD), removal of combining marks (category Mn) except U+3099 and U+309A, then Ø/ø to O/o and Ł/ł to L/l, then NFC. Letters not named are left alone; ß and Æ are unchanged. Case is preserved (Ø to O, not o).
Cases: textfn-accent-insensitize (café = cafe) = true, textfn-accenti = true, textfn-accenti-o-stroke (Øre = Ore) = true.

**N18. /req/text-manipulation/substitute**
Words: the requirement says "replaces a substring with another string"; the table says "s with occurrences of a replaced by b".
Readings: replace the first occurrence, or all occurrences. An empty search string is not addressed.
Implemented: all occurrences. An empty search string leaves s unchanged.
Cases: textfn-substitute 'a-b-c' gives "a+b+c" (first-occurrence reading would give "a+b-c").

**N19. /req/text-manipulation/concatenate arity**
Words: table "concatenate(string a, string b)". The JSON schema: "concatenate" with "minItems": 2, no maximum.
Implemented: exactly two arguments, so three arguments are NULL under N1. No case uses three.

**N20. /req/text-manipulation/format**
Words: "whose format string uses the conversion specifiers of the C printf function (ANSI C)". No list of specifiers, length modifiers or type rules is given.
Implemented: the printf conversions d i u o x X c e E f F g G s, with type checks (for example %d needs an integer, otherwise NULL), argument-count checks (NULL on mismatch), and %a/%A, %n and %p treated as NULL. Python's % formatting is used for the output.
Cases: textfn-format = "3 items" (identical under any reading).

**N21. /req/text-manipulation/upperCase, lowerCase**
Words: "converts a string to uppercase/lowercase". Full Unicode mapping (for example ß to SS) is not stated.
Implemented: Python str.upper and str.lower (full Unicode mapping). No case uses non-ASCII.

**N22. /req/text-relation/contains, startsWith, endsWith: case**
Words: "b occurs as a substring of a" etc. No statement on case sensitivity.
Implemented: case-sensitive. No case distinguishes this.

## D. Arrays

**N23. /req/array-relations/a-equals (ordered or set)**
Words: "True if and only if arrays a and b have the same number of elements and each element of a is equal to the element of b at the same position." The text then has: "// TODO(review): this compares in order, as libCartoSym does, while CQL2 Requirement 16 B evaluates arrays as sets. ... which one CartoSym follows is not settled (see #154)."
Readings: ordered (the requirement sentence) or set (CQL2 Requirement 16 B, outside spec/).
Implemented: ordered. a_equals((1, 2), (2, 1)) = false.
Cases: array-equals-order = false.

**N24. Array element equality**
Words: "a_containedBy ... every element of a is also an element of b"; none of the text defines element equality for mixed types or NULL.
Implemented: integers and reals compare numerically; text with text; boolean with boolean; any other pair, or any NULL element, is not equal.
Cases: none directly.

## E. Variables, values and names

**N25. /req/core/expressions-system-identifiers, /req/core/scale: viz.sd**
Words: the examples in clause 7 and clause 17 use viz.sd throughout (for example "[viz.sd < 200000]", "(123.0, viz.sd)"), and the JSON schema sysId enum has viz.sd. The Visualization System Identifiers table lists only visualization.scaleDenominator, visualization.dateTime, visualization.date, visualization.timeOfDay, visualization.timeInterval and visualization.pass. The schema enum has no visualization.* names at all.
Readings: (a) viz.sd is an alias of visualization.scaleDenominator; (b) viz.sd and visualization.scaleDenominator are different identifiers, each read from the system state under its own name; (c) viz.sd is undefined in CartoSym-CSS.
Implemented: (b). Each name is looked up by exact name in the system values supplied with the case; no alias. So core-system-identifier (viz.sd < 50000 with viz.sd = 25000) is true.
Cases: core-system-identifier = true, core-scale = 25000 (the value of visualization.scaleDenominator).

**N26. Consistency of the JSON form of system identifiers**
Words: the case core-scale has the JSON form {"sysId": "visualization.scaleDenominator"}. In the JSON schema, the sysId enum has no visualization.scaleDenominator (only viz.sd, viz.date, viz.dateTime, viz.timeOfDay, viz.timeInterval, ...). /req/json/schema: "A Producer SHALL generate CartoSym-JSON which validates against the CartoSym-JSON JSON Schema".
Implemented: the case's JSON is evaluated as given. The name is not in the schema enum, so this case's JSON is not schema-valid under the text. This is a contradiction between the JSON schema and the CSCSS table.
Cases: core-scale.

**N27. Dotted names: member access or one identifier**
Words: grammar: "expression DOT IDENTIFIER // Member access". The text uses dotted names as identifiers (viz.sd, dataLayer.type, visualization.scaleDenominator) and also for symbolizer members (stroke.width).
Readings: (a) a dotted chain is member access on a property or identifier; (b) a dotted chain is one name, a system identifier if its full name is one, otherwise a property with that dotted name.
Implemented: (b). Names in the JSON schema enum or in the clause 7 table (plus any capabilities.*) are system identifiers; all others are properties.
Cases: core-system-identifier, core-scale.

**N28. Literals true, false, null in CartoSym-CSS**
Words: lexer: IDENTIFIER and expConstant (NUMERIC_LITERAL UNIT? | HEX_LITERAL) have no token for true, false or null, so these lex as identifiers. Clause 7: "A null literal represents an unset value (CSCSS example: null)" and "Boolean literals ... (CSCSS example: false)".
Implemented: the exact lowercase words true, false, null are literals. TRUE, Null and similar spellings are identifiers (properties), so TRUE is NULL when no such property exists. Whether keywords are case-insensitive is not stated for these names (the lexer makes and, or, in, is, like, between, div case-insensitive).
Cases: core-literal-boolean = true, core-is-null, null-*.

**N29. Undefined names: variables, properties, system values**
Words: "/req/variables/expression: ... resolving to the current value of the referenced variable". Nothing says what an undefined variable, a missing feature property or a missing system value is.
Implemented: an undefined variable, or a cyclic definition, is an error. A missing property or system value is NULL.
Cases: none use these.

**N30. Variable override values**
Words: "A Renderer SHALL support allowing an application to override the value of a defined variable at run time". No statement on whether the value is an expression or must have a type.
Implemented: the application value is used as given (not evaluated).
Cases: var-override = 10.

**N31. Enumeration and unit tokens as identifiers (lexer)**
Words: the lexer defines UNIT tokens px, m, ft, pc, pt, em, inch, cm and mm as exact-match literals, which come before IDENTIFIER. Clause 17: "Enumeration values must conform to the CQL2 identifier grammar production rule".
Implemented: an unquoted identifier spelled exactly as a unit cannot be used as a property name in an expression (for example [pt > 1] is a syntax error). Writing the name in double quotes ("pt") makes it an identifier, which the text allows.
Cases: none use these names.

**N32. Units, colours and tuples in expressions**
Words: clause 17 defines units (5 m, 2.0 px), hex colours (#FF6432) and tuples (50 pc 50 pc) for symbolizer values. It does not say what they evaluate to inside an expression (a number with the unit dropped, a colour, a tuple value).
Implemented: these are errors ("not evaluable") in expressions. Styles containing them are accepted by the style checker.
Cases: none in the suite.

**N33. Adjacent text literals**
Words: lexer CHARACTER_LITERAL: "PART (WS+ PART)*", so 'a' 'b' is one token. The text gives no value for it.
Implemented: a syntax error (the two literals are not joined into one value).
Cases: none.

## F. Conditionals

**N34. Conditional with a non-boolean or NULL condition**
Words: "/req/conditional/else-exp: ... when its condition does not evaluate to true".
Implemented: the elseExp branch, as the words say. Stated here only because "does not evaluate to true" is the only rule (a NULL or non-boolean condition is not an error).
Cases: none.

## G. Style sheets (CartoSym-CSS grammar)

**N35. What "valid CartoSym-CSS" means for a style sheet**
Words: "/req/cscss/grammar: A Producer SHALL generate CartoSym-CSS conforming to the BNF grammar definition ... A Consumer SHALL support parsing styles encoded as CartoSym-CSS." The grammar is the only definition of the syntax.
Readings: (a) the grammar alone decides validity; (b) also semantic checks (known property names, valid selectors, .include targets).
Implemented: (a). The checker is a hand-written parser over the lexer tokens, following the grammar rules: metadata, then variable definitions, then rules; each rule has selectors, a '{', an optional '.name', property assignments (each ending in ';'), nested rules, and '}'. Expressions use the same parser as the expression cases. Semantic checks are not done, and .include targets are not read.
Cases: neq-selector, neq-selector-no-spaces, neq-selector-and = valid.

**N36. Lexer and grammar ambiguities relevant to style sheets**
Words: a rule such as "Roads Railways[viz.sd < 10000][level < 4] {" and a property such as "stroke[0]: ..." both start with an identifier and can be followed by '['.
Implemented: a statement is a property assignment only if the identifier chain (with . and [number]) is followed by ':'; otherwise it is a rule.
Cases: none of the three style cases needed this.

**N37. JSON isNull operand shape**
Words: the JSON schema (isNullPredicate) has "args": { "$ref": "#/$defs/isNullOperand" }, a single operand, not an array. CQL2 writes args as an array. (The JSON schema also has no notLike, see N15.)
Implemented: both shapes are accepted for isNull (a single operand or a one-element array). The case null-is-null uses the one-element array form.
Cases: null-is-null = true.

---

## Summary of cases where the result follows only from one reading

- Read as ordered arrays (N23): array-equals-order = false.
- Read as no LIKE escape (N14): text-like-escape = false.
- Read as the grammar's precedence and NULL logic (N9, N10): null-and-false = false, null-or-true = true, null-or-false = null, null-not = null.
- Read as the exact function names with aliases (N3): textfn-casei = true.
- Read as all-occurrence substitute (N18): textfn-substitute = "a+b+c".
- Read as exactly two arguments for max, min, concatenate (N2, N19): fn-standard = null.
- Read as the JSON form of math-random (N4): math-random = true, though the text form is not valid CartoSym-CSS.
- Read as separate names viz.sd and visualization.scaleDenominator (N25): core-system-identifier = true.
