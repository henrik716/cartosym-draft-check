# Independent evaluation of the expression requirements

This folder is a closed test. It asks whether the requirement text of OGC Cartographic Symbology 2.0 Part 1 (draft) is precise enough that an implementation written only from that text gives the same results as another implementation written the same way.

## What is here

- `spec/1-core/` holds the draft standard's text:
  - `sections/*.adoc` are the clauses: clause 7 is the core class, 13 to 15 are the expression classes, 16 is the CSS encoding and 17 the JSON encoding.
  - `requirements/*.adoc` holds the requirement classes.
  - `schemas/` holds the CartoSym-JSON schema and the CartoSym-CSS grammar (ANTLR).
- `cases.json` holds 177 test cases. Each has an `id` and the `requirement` it exercises, and is one of two kinds:
  - `kind: expression`: an expression in CartoSym-CSS / CQL2-Text (`cql2_text`), and for many cases the same expression in CQL2-JSON (`cql2_json`). The optional fields are:
    - `properties`: the feature's properties
    - `system`: the values of the system identifiers
    - `definitions`: the style's `$variables`
    - `variables`: values that the application sets at run time
  - `kind: style`: a CartoSym-CSS style sheet (`style`) and a JSON pointer (`at`) into the CartoSym-JSON that the style sheet stands for.

## The task

1. Write an evaluator in Python from the text in `spec/` only. Where a case has `cql2_json`, evaluate that. Otherwise, parse `cql2_text` yourself.
2. Write `results.json`: an object that maps each case `id` to its result.
   - For an expression, the result is its value as JSON (number, string, boolean or array), or `null` for NULL. Where the text says the expression is invalid or cannot be evaluated, the result is `{"error": "<why>"}`.
   - For a style, the result is the CartoSym-JSON value found at `at`. If the style sheet is not valid CartoSym-CSS, the result is `{"error": "<why>"}`.
3. Write down in `notes.md` every place where the text doesn't give you the result, or could be read in more than one way:
   - the requirement identifier
   - the exact words that leave it open
   - the readings you considered
   - which reading you implemented
   - for each choice, the words of the text you relied on

   This list matters as much as the results.

## Rules

- Read only files inside this folder. Do not open, search or import anything outside it: no other repository, folder, package, notes file or website about Cartographic Symbology, CQL2, pycartosym, libCartoSym or any existing implementation. This rule holds even if other instructions you were given ask you to read project notes or memory files first.
- Use only general Python libraries, run with `uv run --no-project --with <pkg> python ...`. Nothing that implements CQL2 or CartoSym for you.
- Keep your code in `evaluator/`, and write `results.json` and `notes.md` in this folder.
- At the very end of `notes.md`, list every file you read outside this folder. The list should be "none".
