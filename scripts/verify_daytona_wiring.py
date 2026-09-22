#!/usr/bin/env python3
"""Evidence-matrix script row — Daytona wiring contract (stdlib-only).

AST-checks the README's Daytona sandbox and tool-execution claims: ToolRunner
routes commands through DaytonaToolBackend when enabled, the backend uploads
(syncs) the work directory before executing, the FastQC and samtools wrappers
skip (rather than fail) when the tool is not installed locally, and samtools
invokes flagstat.

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


def find_class(tree, name):
    return next((n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == name), None)


def find_method(cls, name):
    return next((n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name == name), None)


def has_call(node, attr_name, value_name=None):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr == attr_name:
            if value_name is None:
                return True
            base = sub.func.value
            if isinstance(base, ast.Name) and base.id == value_name:
                return True
            if isinstance(base, ast.Attribute) and base.attr == value_name:
                return True
    return False


def main():
    runner_tree = parse("annotatex/pipeline/tools/runner.py")
    runner_cls = find_class(runner_tree, "ToolRunner")
    invoke = find_method(runner_cls, "_invoke") if runner_cls else None
    check("ToolRunner._invoke exists", invoke is not None)
    check("ToolRunner routes through DaytonaToolBackend.enabled()",
          invoke is not None and has_call(invoke, "enabled", "DaytonaToolBackend"))
    routes = False
    if invoke:
        for sub in ast.walk(invoke):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr == "run":
                base = sub.func.value
                named_backend = (isinstance(base, ast.Attribute)
                                 and base.attr == "DaytonaToolBackend") or \
                                (isinstance(base, ast.Name) and base.id == "DaytonaToolBackend")
                uses_workdir = any(isinstance(a, ast.Attribute) and a.attr == "work_dir"
                                   for a in sub.args)
                if named_backend and uses_workdir:
                    routes = True
    check("ToolRunner passes work_dir to DaytonaToolBackend.run", routes)

    backend_tree = parse("annotatex/pipeline/tools/daytona_backend.py")
    backend_cls = find_class(backend_tree, "DaytonaToolBackend")
    backend_run = find_method(backend_cls, "run") if backend_cls else None
    check("DaytonaToolBackend.run exists", backend_run is not None)
    check("DaytonaToolBackend.run syncs (uploads) the work dir before exec",
          backend_run is not None and has_call(backend_run, "sync_workdir"))
    execs = False
    if backend_run:
        for sub in ast.walk(backend_run):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr == "exec":
                execs = True
    check("DaytonaToolBackend.run executes the command in the sandbox", execs)

    fastqc_tree = parse("annotatex/pipeline/tools/fastqc.py")
    fastqc_fn = next((n for n in ast.walk(fastqc_tree)
                      if isinstance(n, ast.FunctionDef) and n.name == "run_fastqc"), None)
    check("run_fastqc skips when fastqc not installed",
          fastqc_fn is not None and has_call(fastqc_fn, "is_available")
          and has_call(fastqc_fn, "skip"))

    samtools_tree = parse("annotatex/pipeline/tools/samtools.py")
    sam_fn = next((n for n in ast.walk(samtools_tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "run_samtools_stats"), None)
    check("run_samtools_stats skips when samtools not installed",
          sam_fn is not None and has_call(sam_fn, "is_available")
          and has_call(sam_fn, "skip"))
    flagstat = False
    if sam_fn:
        for sub in ast.walk(sam_fn):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                    and sub.value == "samtools":
                flagstat = True
    flagstat = flagstat and any(
        isinstance(sub, ast.Constant) and isinstance(sub.value, str) and sub.value == "flagstat"
        for sub in ast.walk(sam_fn)) if sam_fn else False
    check("samtools command invokes flagstat", flagstat)

    print()
    if FAILURES:
        print(f"verify_daytona_wiring: FAILED ({len(FAILURES)} check(s))")
        return 1
    print("verify_daytona_wiring: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
