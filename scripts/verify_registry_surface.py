#!/usr/bin/env python3
"""Evidence-matrix script row — tool registry surface (stdlib-only).

Executes the real registry module (loaded from its file path so the heavy
package import chain is not triggered) and asserts the README's tool-registry
claims: the ten-tool catalog, the six tools named in the README table, and the
install hints reported for installed/missing tools.

Exits 0 when every check passes, 1 otherwise. No network, no third-party
imports.
"""
import importlib.util
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


def load_registry():
    path = ROOT / "annotatex" / "pipeline" / "tools" / "registry.py"
    spec = importlib.util.spec_from_file_location("annotatex_registry_under_test", path)
    module = importlib.util.module_from_spec(spec)
    # register in sys.modules so dataclass annotation resolution works (3.13+)
    sys.modules["annotatex_registry_under_test"] = module
    spec.loader.exec_module(module)
    return module


def main():
    registry = load_registry()

    names = [spec.name for spec in registry.TOOLS]
    check("registry catalog has 10 tools", len(names) == 10, f"got {len(names)}: {names}")

    readme_tools = ["fastqc", "samtools", "pydeseq2", "star", "featurecounts", "multiqc"]
    missing = [t for t in readme_tools if t not in names]
    check("README tool table present in registry", not missing, f"missing: {missing}")

    status = registry.get_tool_status()
    check("get_tool_status() returns one row per tool", len(status) == len(names))
    shape_ok = all(
        isinstance(row, dict)
        and set(row) == {"name", "category", "available", "install_hint"}
        and isinstance(row["available"], bool)
        and isinstance(row["install_hint"], str)
        for row in status
    )
    check("status rows carry name/category/available/install_hint", shape_ok)

    hints = {row["name"]: row["install_hint"] for row in status}
    check("fastqc hint names bioconda", hints.get("fastqc") == "conda install -c bioconda fastqc",
          f"got {hints.get('fastqc')!r}")
    check("pydeseq2 hint names pip", hints.get("pydeseq2") == "pip install pydeseq2",
          f"got {hints.get('pydeseq2')!r}")
    check("every tool has a non-empty install hint",
          all(isinstance(h, str) and h.strip() for h in hints.values()))

    print()
    if FAILURES:
        print(f"verify_registry_surface: FAILED ({len(FAILURES)} check(s))")
        return 1
    print("verify_registry_surface: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
