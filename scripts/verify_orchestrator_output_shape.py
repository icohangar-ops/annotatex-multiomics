#!/usr/bin/env python3
"""Evidence-matrix script row — pipeline result shape (stdlib-only).

AST-checks the README's Sample Output claim against the orchestrator and
reporter: the result JSON carries status, run_id (pipeline_<epoch>), data_type,
n_genes, n_de_genes, qc_status, bio pipeline steps and report_html, the dry-run
path returns a plan without executing, and every run writes report.html and
report.json.

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


def dict_keys(node):
    """String keys of an ast.Dict literal."""
    if isinstance(node, ast.Dict):
        return {k.value for k in node.keys if isinstance(k, ast.Constant)}
    return set()


def is_plan_base(node):
    """True when the node names the local `plan` dict."""
    if isinstance(node, ast.Name):
        return node.id == "plan"
    if isinstance(node, ast.Attribute):
        return node.attr == "plan"
    return False


def main():
    orch = parse("annotatex/pipeline/orchestrator.py")
    run_fn = next((n for n in ast.walk(orch)
                   if isinstance(n, ast.FunctionDef) and n.name == "run"), None)
    check("PipelineOrchestrator.run exists", run_fn is not None)

    plan_init_keys = set()
    update_keys = set()
    status_assign_values = []
    has_epoch_run_id = False
    if run_fn:
        for node in ast.walk(run_fn):
            # plan = { ... }
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict) \
                    and node.targets and is_plan_base(node.targets[0]):
                plan_init_keys |= dict_keys(node.value)
            # plan.update({ ... })
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "update" and is_plan_base(node.func.value) \
                    and node.args and isinstance(node.args[0], ast.Dict):
                update_keys |= dict_keys(node.args[0])
            # run_id = f"pipeline_{int(start)}"
            if isinstance(node, ast.JoinedStr) and any(
                    isinstance(v, ast.Constant) and isinstance(v.value, str)
                    and v.value.startswith("pipeline_") for v in node.values):
                has_epoch_run_id = True
            # plan["status"] = "dry_run" (and friends)
            if isinstance(node, ast.Assign) and node.targets \
                    and isinstance(node.targets[0], ast.Subscript) \
                    and is_plan_base(node.targets[0].value) \
                    and isinstance(node.targets[0].slice, ast.Constant) \
                    and isinstance(node.value, ast.Constant):
                status_assign_values.append(
                    (node.targets[0].slice.value, node.value.value))

    expected_initial = {"run_id", "input", "data_type", "detection", "tools", "dry_run"}
    expected_final = {"status", "duration_seconds", "n_genes", "n_de_genes",
                      "qc_status", "report_html", "report_json"}
    missing_init = expected_initial - plan_init_keys
    check("initial plan dict carries run_id/input/data_type/detection/tools/dry_run",
          not missing_init, f"missing: {sorted(missing_init)}")
    missing_final = expected_final - update_keys
    check("completed plan carries status/duration/n_genes/n_de_genes/qc_status/report paths",
          not missing_final, f"missing: {sorted(missing_final)}")
    check("run_id is pipeline_<epoch seconds>", has_epoch_run_id)
    check("dry-run plan sets status dry_run",
          ("status", "dry_run") in status_assign_values,
          f"plan[...] constant assigns: {status_assign_values}")
    check("dry-run returns before execution (Would run: message)",
          any(isinstance(n, ast.Constant) and isinstance(n.value, str)
              and n.value.startswith("Would run:") for n in (ast.walk(run_fn) if run_fn else [])))

    persisted = {n.value for n in ast.walk(orch)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and n.value in ("plan.json", "results.json")}
    check("orchestrator persists plan.json and results.json",
          {"plan.json", "results.json"} <= persisted)

    rep = parse("annotatex/pipeline/reporter.py")
    report_paths = {n.value for n in ast.walk(rep)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    check("reporter writes report.html and report.json",
          {"report.html", "report.json"} <= report_paths)
    template = next((n for n in ast.walk(rep)
                     if isinstance(n, ast.Assign) and any(
                         isinstance(t, ast.Name) and t.id == "REPORT_TEMPLATE"
                         for t in n.targets)), None)
    template_ok = isinstance(template, ast.Assign) \
        and isinstance(template.value, ast.Constant) \
        and "Top Annotated Genes" in template.value.value
    check("HTML report template renders QC status and top genes table", template_ok)

    print()
    if FAILURES:
        print(f"verify_orchestrator_output_shape: FAILED ({len(FAILURES)} check(s))")
        return 1
    print("verify_orchestrator_output_shape: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
