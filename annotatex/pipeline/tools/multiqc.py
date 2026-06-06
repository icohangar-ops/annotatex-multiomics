"""MultiQC aggregate QC report."""

from __future__ import annotations

from pathlib import Path

from annotatex.pipeline.tools.registry import ToolRegistry
from annotatex.pipeline.tools.runner import ToolRunner, StepResult


def run_multiqc(input_dir: Path, output_dir: Path, runner: ToolRunner) -> StepResult:
    registry = ToolRegistry()
    if not registry.is_available("multiqc"):
        return runner.skip("multiqc", "multiqc not installed. Run: conda install -c bioconda multiqc")

    inp = Path(input_dir).resolve()
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    return runner.run(
        "multiqc",
        ["multiqc", str(inp), "-o", str(out), "--force"],
        outputs=list(out.glob("multiqc_report.html")),
    )
