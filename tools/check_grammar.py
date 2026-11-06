"""Check the spec's CartoSym-CSS grammar: generate a parser and run inputs through it.

Usage: uv run --with antlr4-tools python tools/check_grammar.py [--ref REF] [path to cartographic-symbology]

The test harness runs the implementations, which have parsers of their own, so
it says nothing about the .g4 files. This generates a parser from them with
ANTLR and checks it on cases/grammar/css-grammar.yaml and on every .cscss file
in 1-core/examples. Without --ref it reads the working tree of the checkout;
with --ref it reads that commit, for instance a pull request after
`git fetch origin pull/124/head`, then `--ref FETCH_HEAD`.

ANTLR needs Java. Without it, antlr4-tools offers to install a JRE in ~/.jre.
Exits with 1 if an input is not handled as expected.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "cases" / "grammar" / "css-grammar.yaml"
SCHEMAS = "1-core/schemas"
EXAMPLES = "1-core/examples"
# ANTLR requires a file to be named after its grammar, which the spec's files are not.
GRAMMARS = {"CartoSym-CSS-Lexer.g4": "CartoSymCSSLexer.g4", "CartoSym-CSS-Grammar.g4": "CartoSymCSSGrammar.g4"}


def read(spec: Path, ref: str | None, path: str) -> str:
    if ref is None:
        return (spec / path).read_text(encoding="utf-8")
    return subprocess.run(["git", "-C", str(spec), "show", f"{ref}:{path}"], capture_output=True, check=True,
                          text=True, encoding="utf-8").stdout


def examples(spec: Path, ref: str | None) -> list[str]:
    if ref is None:
        return sorted(p.relative_to(spec).as_posix() for p in (spec / EXAMPLES).glob("*.cscss"))
    tree = subprocess.run(["git", "-C", str(spec), "ls-tree", "-r", "--name-only", ref, EXAMPLES],
                          capture_output=True, check=True, text=True).stdout
    return sorted(line for line in tree.splitlines() if line.endswith(".cscss"))


def generate(spec: Path, ref: str | None, out: Path) -> None:
    for source, target in GRAMMARS.items():
        (out / target).write_text(read(spec, ref, f"{SCHEMAS}/{source}"), encoding="utf-8")
    # The generated parser must match the ANTLR runtime pycartosym brings in.
    antlr = ["antlr4", "-v", version("antlr4-python3-runtime"), "-Dlanguage=Python3"]
    for target in GRAMMARS.values():
        proc = subprocess.run([*antlr, target], cwd=out, capture_output=True, text=True, encoding="utf-8")
        output = (proc.stdout + proc.stderr).strip()
        if proc.returncode != 0 or "error(" in output or "warning(" in output:
            raise SystemExit(f"ANTLR on {target}:\n{output}")


def load_parser(out: Path):
    from antlr4 import CommonTokenStream, InputStream
    from antlr4.error.ErrorListener import ErrorListener
    from antlr4.tree.Tree import TerminalNode

    sys.path.insert(0, str(out))
    from CartoSymCSSGrammar import CartoSymCSSGrammar
    from CartoSymCSSLexer import CartoSymCSSLexer

    class Errors(ErrorListener):
        def __init__(self):
            self.messages = []

        def syntaxError(self, recognizer, symbol, line, column, message, e):  # noqa: N802 - ANTLR's name
            self.messages.append(f"{line}:{column} {message}")

    def text(node) -> str:
        """The parse with brackets around each node of more than one child."""
        if isinstance(node, TerminalNode):
            return node.getText()
        children = [text(c) for c in node.children or []]
        return children[0] if len(children) == 1 else "(" + " ".join(children) + ")"

    def first_selector(node):
        if isinstance(node, CartoSymCSSGrammar.SelectorContext):
            return node
        for child in node.getChildren():
            if not isinstance(child, TerminalNode) and (found := first_selector(child)) is not None:
                return found
        return None

    def parse(source: str) -> tuple[list[str], str | None]:
        """Syntax errors, and the parse of the first selector."""
        errors = Errors()
        lexer = CartoSymCSSLexer(InputStream(source))
        lexer.removeErrorListeners()
        lexer.addErrorListener(errors)
        tokens = CommonTokenStream(lexer)
        parser = CartoSymCSSGrammar(tokens)
        parser.removeErrorListeners()
        parser.addErrorListener(errors)
        tree = parser.styleSheet()
        # styleSheet does not end in EOF, so the parser can stop early without an error.
        if tokens.LT(1).type != -1:
            errors.messages.append(f"stopped at {tokens.LT(1).text!r}")
        selector = first_selector(tree)
        expression = selector.expression() if selector is not None and not errors.messages else None
        return errors.messages, text(expression) if expression is not None else None

    return parse


def check(parse, case: dict) -> str | None:
    """What is wrong with an input's result, or None."""
    source = case.get("style", f"[{case.get('selector')}] {{ opacity: 0.5; }}\n")
    errors, tree = parse(source)
    expected = case["expect"]
    if expected == "rejected":
        return "accepted" if not errors else None
    if errors:
        return f"rejected: {errors[0]}"
    return None if expected == "accepted" or tree == expected else f"parsed as {tree}, expected {expected}"


def main() -> int:
    args = argparse.ArgumentParser()
    args.add_argument("spec", nargs="?", type=Path, default=ROOT.parent / "cartographic-symbology")
    args.add_argument("--ref")
    opts = args.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        generate(opts.spec, opts.ref, Path(tmp))
        parse = load_parser(Path(tmp))
        failures = 0
        cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))
        for case in cases:
            problem = check(parse, case)
            if problem:
                failures += 1
                note = f"  ({case['note']})" if "note" in case else ""
                print(f"FAIL {case.get('selector', case.get('style')).strip()!r}: {problem}{note}")
        files = examples(opts.spec, opts.ref)
        for path in files:
            errors, _ = parse(read(opts.spec, opts.ref, path))
            if errors:
                failures += 1
                print(f"FAIL {path}: {len(errors)} errors, the first at {errors[0]}")
    print(f"{opts.ref or 'working tree'}: {len(cases) + len(files) - failures} of {len(cases) + len(files)} pass "
          f"({len(cases)} inputs, {len(files)} examples)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
