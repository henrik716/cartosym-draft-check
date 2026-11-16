# Independent evaluation of the expression requirements

This folder is a closed test. Its question is whether the requirement text of OGC Cartographic Symbology 2.0 Part 1 (draft) is precise enough that an implementation written only from that text gives the same results as another one.

## What is here

- `spec/1-core/` holds the draft standard's text: `sections/*.adoc` (clause 7 is the core class, clauses 13 to 15 the expression classes, 17 the CSS encoding with its grammar in `schemas/`) and `requirements/*.adoc`.
- `cases.json` holds 123 test cases. Each has an `id`, the `requirement` it exercises, and either:
  - `kind: expression`: an expression as CartoSym-CSS / CQL2-Text (`cql2_text`) and, for most cases, the same expression as CQL2-JSON (`cql2_json`). Optional `properties` are the feature's properties, `system` the system identifiers' values, `definitions` the style's `$variables`, and `variables` values the application sets at run time.
  - `kind: style`: a CartoSym-CSS style sheet (`style`) to be checked against the grammar.

## The task

1. Write an evaluator in Python from the text in `spec/` only. Where a case has `cql2_json`, evaluate that; otherwise parse `cql2_text` yourself. For `style` cases, decide whether the style is valid CartoSym-CSS.
2. Write `results.json`: an object mapping each case `id` to its result as JSON (number, string, boolean, array, or `null` for NULL), or to `{"error": "<why>"}` where the text says the expression is invalid or cannot be evaluated, or `"valid"`/`"invalid"` for style cases.
3. Every time the text does not tell you the result, or could be read in more than one way, write it down in `notes.md`: the requirement identifier, the exact words that leave it open, the readings you considered, and which one you implemented. This list matters as much as the results.

## Rules

- Read only files inside this folder. Do not open, search or import anything outside it: no other repository, package or website about Cartographic Symbology, CQL2, pycartosym, libCartoSym or any existing implementation.
- Use only general Python libraries (run with `uv run --no-project --with <pkg> python ...`); nothing that implements CQL2 or CartoSym for you.
- Keep your code in `evaluator/`, and write `results.json` and `notes.md` in this folder.
