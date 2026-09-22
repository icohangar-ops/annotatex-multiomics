#!/usr/bin/env python3
"""Evidence-matrix script row — project layout and installer (stdlib-only).

Verifies the README's Project Structure claim: every file listed in the
documented structure exists in the tree, and scripts/install_bioinfo.sh is a
syntactically valid bash script that installs the README's tools and prints
the registry tool status when it finishes.

Exits 0 when every check passes, 1 otherwise. No network, no third-party
imports.
"""
import subprocess
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


README_STRUCTURE_FILES = [
    "annotatex/data/generator.py",
    "annotatex/data/datamodule.py",
    "annotatex/models/annotatex.py",
    "annotatex/pipeline/detector.py",
    "annotatex/pipeline/qc.py",
    "annotatex/pipeline/orchestrator.py",
    "annotatex/pipeline/reporter.py",
    "annotatex/pipeline/tools/registry.py",
    "annotatex/pipeline/tools/runner.py",
    "annotatex/pipeline/tools/fastqc.py",
    "annotatex/pipeline/tools/samtools.py",
    "annotatex/pipeline/tools/deseq2.py",
    "annotatex/pipeline/tools/bio_pipeline.py",
    "app.py",
    "train.py",
    "pipeline.py",
    "main.py",
    "scripts/install_bioinfo.sh",
]


def main():
    for relpath in README_STRUCTURE_FILES:
        check(f"documented file exists: {relpath}", (ROOT / relpath).is_file())

    installer = ROOT / "scripts" / "install_bioinfo.sh"
    text = installer.read_text(encoding="utf-8") if installer.is_file() else ""
    bash_n = subprocess.run(["bash", "-n", str(installer)], capture_output=True, text=True)
    check("install_bioinfo.sh passes bash -n (syntax valid)", bash_n.returncode == 0,
          bash_n.stderr.strip())
    for tool in ["fastqc", "samtools", "multiqc", "pydeseq2"]:
        check(f"install_bioinfo.sh installs {tool}", tool in text)
    check("install_bioinfo.sh prints registry tool status at the end",
          "get_tool_status" in text)

    print()
    if FAILURES:
        print(f"verify_project_layout: FAILED ({len(FAILURES)} check(s))")
        return 1
    print("verify_project_layout: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
