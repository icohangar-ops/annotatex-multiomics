"""Real differential expression via PyDESeq2."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from annotatex.pipeline.tools.registry import ToolRegistry
from annotatex.pipeline.tools.runner import ToolRunner, StepResult


def run_deseq2(counts_path: Path, metadata_path: Path | None, output_dir: Path, runner: ToolRunner) -> StepResult:
    registry = ToolRegistry()
    if not registry.is_available("pydeseq2"):
        return runner.skip("pydeseq2", "PyDESeq2 not installed. Run: pip install pydeseq2")

    try:
        from pydeseq2.dds import DeseqDataSet
        from pydeseq2.ds import DeseqStats
    except ImportError:
        return runner.skip("pydeseq2", "PyDESeq2 import failed")

    counts = pd.read_csv(counts_path, index_col=0)
    counts = counts.apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    counts = counts.T  # PyDESeq2 expects samples x genes

    if metadata_path and metadata_path.exists():
        metadata = pd.read_csv(metadata_path, index_col=0)
    else:
        metadata = _default_metadata(counts.index.tolist())

    metadata = metadata.loc[counts.index]
    design = _infer_design(metadata)

    start_msg = f"Running PyDESeq2 on {counts.shape[0]} samples, {counts.shape[1]} genes, design={design}"

    try:
        dds = DeseqDataSet(counts=counts, metadata=metadata, design=design)
        dds.deseq2()

        contrast = _infer_contrast(metadata, design)
        ds = DeseqStats(dds, contrast=contrast)
        ds.summary()

        results = ds.results_df.copy()
        results.index.name = "gene"
        results = results.reset_index()
        results.rename(
            columns={"log2FoldChange": "log2FoldChange", "pvalue": "pvalue", "padj": "padj", "baseMean": "baseMean"},
            inplace=True,
        )
        results["is_de"] = (results["padj"] < 0.05).astype(int)

        out_path = output_dir / "deseq2_results.csv"
        results.to_csv(out_path, index=False)

        result = StepResult(
            tool="pydeseq2",
            command=f"PyDESeq2 design={design} contrast={contrast}",
            status="completed",
            duration_seconds=0,
            outputs=[str(out_path)],
            stdout=f"{start_msg}\nDE genes (padj<0.05): {(results['padj'] < 0.05).sum()}",
        )
    except Exception as exc:
        result = StepResult(
            tool="pydeseq2",
            command="PyDESeq2",
            status="failed",
            duration_seconds=0,
            error=str(exc),
        )

    runner.steps.append(result)
    return result


def generate_demo_counts(output_dir: Path, n_genes: int = 500, n_samples: int = 4) -> tuple[Path, Path]:
    """Generate a count matrix suitable for PyDESeq2 when only FASTQ is provided."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    genes = [f"GENE_{i:04d}" for i in range(n_genes)]
    # Include known genes for meaningful annotations
    known = ["TP53", "BCL2", "CDKN1A", "MYC", "BRCA1", "VEGFA", "IL6", "SOD2", "EGFR", "PTEN"]
    genes[: len(known)] = known

    samples = [f"sample_{i+1}" for i in range(n_samples)]
    conditions = ["control", "control", "treated", "treated"]

    base = rng.negative_binomial(n=10, p=0.3, size=(n_genes, n_samples)).astype(float)
    treated_idx = [i for i, c in enumerate(conditions) if c == "treated"]
    de_genes = rng.choice(n_genes, size=n_genes // 5, replace=False)
    for g in de_genes:
        fold = rng.uniform(1.5, 4.0)
        for s in treated_idx:
            base[g, s] *= fold

    counts = pd.DataFrame(base, index=genes, columns=samples).astype(int)
    metadata = pd.DataFrame({"condition": conditions}, index=samples)

    counts_path = output_dir / "counts.csv"
    meta_path = output_dir / "metadata.csv"
    counts.to_csv(counts_path)
    metadata.to_csv(meta_path)
    return counts_path, meta_path


def _default_metadata(sample_names: list[str]) -> pd.DataFrame:
    conditions = []
    for i, _ in enumerate(sample_names):
        conditions.append("control" if i < len(sample_names) // 2 else "treated")
    return pd.DataFrame({"condition": conditions}, index=sample_names)


def _infer_design(metadata: pd.DataFrame) -> str:
    if "condition" in metadata.columns:
        return "~condition"
    return f"~{metadata.columns[0]}"


def _infer_contrast(metadata: pd.DataFrame, design: str) -> list:
    col = design.replace("~", "")
    levels = metadata[col].unique().tolist()
    if len(levels) >= 2:
        return [col, levels[1], levels[0]]
    return [col, levels[0], levels[0]]
