"""FastQC quality control execution."""

from __future__ import annotations

from pathlib import Path

from annotatex.pipeline.tools.registry import ToolRegistry
from annotatex.pipeline.tools.runner import ToolRunner, StepResult


def run_fastqc(fastq_path: Path, output_dir: Path, runner: ToolRunner) -> StepResult:
    registry = ToolRegistry()
    if not registry.is_available("fastqc"):
        return runner.skip("fastqc", "FastQC not installed. Run: conda install -c bioconda fastqc")

    out_dir = Path(output_dir).resolve() / "fastqc"
    out_dir.mkdir(parents=True, exist_ok=True)
    fastq = Path(fastq_path).resolve()
    return runner.run(
        "fastqc",
        ["fastqc", "-o", str(out_dir), "-t", "2", "--extract", str(fastq)],
        outputs=list(out_dir.glob("*")),
    )


def parse_fastqc_summary(fastq_path: Path, output_dir: Path) -> dict:
    """Parse FastQC summary.txt if available."""
    stem = fastq_path.name.replace(".gz", "").replace(".fastq", "").replace(".fq", "")
    summary_dirs = list((output_dir / "fastqc").glob(f"{stem}*_fastqc"))
    if not summary_dirs:
        summary_dirs = list((output_dir / "fastqc").glob("*_fastqc"))

    if not summary_dirs:
        return {"status": "no_report", "checks": []}

    summary_file = summary_dirs[0] / "summary.txt"
    if not summary_file.exists():
        return {"status": "no_report", "checks": []}

    checks = []
    for line in summary_file.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            status, module, detail = parts[0], parts[1], parts[2]
            checks.append({"module": module, "status": status, "detail": detail})

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    warn_count = sum(1 for c in checks if c["status"] == "WARN")
    overall = "pass" if warn_count == 0 else ("warn" if pass_count > 0 else "fail")

    return {
        "status": overall,
        "checks": checks,
        "summary": f"FastQC: {pass_count} PASS, {warn_count} WARN, {len(checks) - pass_count - warn_count} FAIL",
        "report_dir": str(summary_dirs[0]),
    }
