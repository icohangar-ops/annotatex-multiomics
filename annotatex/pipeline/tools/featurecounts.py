"""featureCounts gene quantification."""

from __future__ import annotations

from pathlib import Path

from annotatex.pipeline.tools.reference import ensure_reference
from annotatex.pipeline.tools.registry import ToolRegistry
from annotatex.pipeline.tools.runner import ToolRunner, StepResult


def run_featurecounts(bam_path: Path, ref_dir: Path, output_dir: Path, runner: ToolRunner) -> StepResult:
    registry = ToolRegistry()
    if not registry.is_available("featurecounts"):
        return runner.skip("featurecounts", "featureCounts not installed. Run: conda install -c bioconda subread")

    refs = ensure_reference(ref_dir)
    bam = Path(bam_path).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    counts_file = out_dir / "featurecounts.txt"

    return runner.run(
        "featurecounts",
        [
            "featureCounts",
            "-a", str(refs["gtf"].resolve()),
            "-o", str(counts_file),
            "-t", "exon",
            "-g", "gene_id",
            str(bam),
        ],
        outputs=[counts_file],
    )


def parse_featurecounts(counts_file: Path) -> Path | None:
    """Convert featureCounts output to AnnotateX counts.csv format."""
    import pandas as pd

    df = pd.read_csv(counts_file, sep="\t", comment="#")
    gene_col = "Geneid" if "Geneid" in df.columns else df.columns[0]
    sample_cols = [c for c in df.columns if c.startswith("/") or "bam" in c.lower() or c.endswith(".sam")]
    if not sample_cols:
        sample_cols = [c for c in df.columns if c not in {gene_col, "Chr", "Start", "End", "Strand", "Length"}][-1:]
    if not sample_cols:
        return None

    counts = df[[gene_col] + sample_cols].copy()
    counts.columns = ["gene"] + [f"sample_{i+1}" for i in range(len(sample_cols))]
    out = counts_file.parent / "counts.csv"
    counts.to_csv(out, index=False)
    return out
