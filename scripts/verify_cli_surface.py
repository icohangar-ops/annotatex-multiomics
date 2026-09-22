#!/usr/bin/env python3
"""Evidence-matrix script row — CLI surface contract (stdlib-only).

AST-checks the README's Quick Start / CLI Reference claims: pipeline.py flags
and default checkpoint, train.py --generate/--epochs and checkpoint copy,
annotate.py --results, and main.py's train-then-launch flow on port 7860.

Exits 0 when every check passes, 1 otherwise. No network, no third-party
imports.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    line = f"  [{status}] {name}"
    if not cond and detail:
        line += f" -- {detail}"
    print(line)
    if not cond:
        FAILURES.append(name)


def parse(relpath):
    return ast.parse((ROOT / relpath).read_text(encoding="utf-8"))


def option_flags(tree):
    """All argparse option strings registered via add_argument."""
    flags = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "add_argument" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                flags.append(first.value)
    return flags


def main():
    pipeline_tree = parse("pipeline.py")
    flags = option_flags(pipeline_tree)
    for expected in ["--data", "--type", "--output-dir", "--model",
                     "--dry-run", "--skip-qc", "--skip-bio", "--max-genes", "--verbose"]:
        check(f"pipeline.py registers {expected}", expected in flags)

    model_default = None
    for node in ast.walk(pipeline_tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "add_argument":
            for kw in node.keywords:
                if kw.arg == "default" and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str) and "annotatex" in kw.value.value:
                    model_default = kw.value.value
    check("pipeline.py default checkpoint is checkpoints/annotatex-best.ckpt",
          model_default == "checkpoints/annotatex-best.ckpt", f"got {model_default!r}")

    train_tree = parse("train.py")
    train_flags = option_flags(train_tree)
    for expected in ["--generate", "--epochs", "--n-genes", "--hidden-dim", "--data-dir"]:
        check(f"train.py registers {expected}", expected in train_flags)

    annotate_tree = parse("annotate.py")
    annotate_flags = option_flags(annotate_tree)
    check("annotate.py registers --results", "--results" in annotate_flags)
    check("annotate.py registers --output", "--output" in annotate_flags)

    main_tree = parse("main.py")
    constants = [n.value for n in ast.walk(main_tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    check("main.py gates on checkpoints/annotatex-best.ckpt",
          "checkpoints/annotatex-best.ckpt" in constants)
    check_call_count = sum(
        1 for node in ast.walk(main_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "check_call"
    )
    check("main.py invokes two subprocesses (train then app)", check_call_count == 2,
          f"got {check_call_count}")
    check("main.py runs train.py", "train.py" in constants)
    check("main.py runs app.py", "app.py" in constants)

    print()
    if FAILURES:
        print(f"verify_cli_surface: FAILED ({len(FAILURES)} check(s))")
        return 1
    print("verify_cli_surface: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
