#!/usr/bin/env python3
"""Evidence-matrix script row — Gradio UI contract (stdlib-only).

AST-checks the README's Gradio UI claims against app.py: the three tabs
(Pipeline / Tool Status / Train Model), the supported upload types, the HTML
report download component, and the launch on port 7860.

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


def main():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    constants = [n.value for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)]

    tab_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "Tab" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                tab_names.append(first.value)
    for expected in ["Pipeline", "Tool Status", "Train Model"]:
        check(f"UI defines tab {expected!r}", expected in tab_names, f"tabs: {tab_names}")

    file_types = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "File":
            for kw in node.keywords:
                if kw.arg == "file_types" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    file_types = [e.value for e in kw.value.elts
                                  if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    for expected in [".csv", ".tsv", ".fastq", ".fq", ".gz", ".bam"]:
        check(f"upload accepts {expected}", expected in file_types, f"got {file_types}")

    check("report download component labeled 'Download HTML report'",
          "Download HTML report" in constants)
    check("results JSON component present", "Full results JSON" in constants)
    check("tool status tab calls get_tool_status",
          "get_tool_status" in constants or any(
              isinstance(n, ast.ImportFrom) and n.module == "annotatex.pipeline.tools.registry"
              for n in ast.walk(tree)))

    launch = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr == "launch"), None)
    port = None
    host = None
    if launch:
        for kw in launch.keywords:
            if kw.arg == "server_port" and isinstance(kw.value, ast.Constant):
                port = kw.value.value
            if kw.arg == "server_name" and isinstance(kw.value, ast.Constant):
                host = kw.value.value
    check("app launches on port 7860", port == 7860, f"got {port!r}")
    check("app binds 0.0.0.0", host == "0.0.0.0", f"got {host!r}")

    print()
    if FAILURES:
        print(f"verify_ui_contract: FAILED ({len(FAILURES)} check(s))")
        return 1
    print("verify_ui_contract: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
