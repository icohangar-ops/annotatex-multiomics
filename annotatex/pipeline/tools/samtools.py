"""samtools BAM/VCF processing."""

from __future__ import annotations

from pathlib import Path

from annotatex.pipeline.tools.registry import ToolRegistry
from annotatex.pipeline.tools.runner import ToolRunner, StepResult


def run_samtools_stats(bam_path: Path, output_dir: Path, runner: ToolRunner) -> StepResult:
    registry = ToolRegistry()
    if not registry.is_available("samtools"):
        return runner.skip("samtools", "samtools not installed. Run: conda install -c bioconda samtools")

    stats_file = Path(output_dir).resolve() / "samtools_flagstat.txt"
    bam = Path(bam_path).resolve()
    result = runner.run(
        "samtools",
        ["samtools", "flagstat", str(bam)],
        outputs=[stats_file],
    )

    if result.status == "completed" and result.stdout:
        stats_file.write_text(result.stdout)
        result.outputs = [str(stats_file)]

    return result


def parse_flagstat(stats_text: str) -> dict:
    metrics = {}
    for line in stats_text.splitlines():
        if "+" in line or "in total" in line:
            parts = line.strip().split(" ", 1)
            if len(parts) == 2:
                try:
                    metrics[parts[1]] = int(parts[0].replace(",", ""))
                except ValueError:
                    continue
    return metrics
