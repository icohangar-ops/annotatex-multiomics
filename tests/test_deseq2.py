"""Evidence-matrix tests — PyDESeq2 on demo counts (README Features).

Exercises the real end-to-end path: generate_demo_counts -> pydeseq2 Wald ->
results CSV on disk, through the actual ToolRunner.
"""
import pandas as pd
import pytest
from annotatex.pipeline.tools.deseq2 import generate_demo_counts, run_deseq2
from annotatex.pipeline.tools.registry import get_tool_status
from annotatex.pipeline.tools.runner import ToolRunner


def _pydeseq2_available() -> bool:
    return any(row["name"] == "pydeseq2" and row["available"] for row in get_tool_status())


@pytest.mark.skipif(
    not _pydeseq2_available(),
    reason="pydeseq2 not installed in this environment",
)
def test_pydeseq2_wald_on_demo_counts(tmp_path):
    counts, meta = generate_demo_counts(tmp_path, n_genes=60, n_samples=4)
    out = tmp_path / "de"
    out.mkdir()
    result = run_deseq2(counts, meta, out, ToolRunner(tmp_path))
    assert result.status == "completed", result.error
    results_csv = out / "deseq2_results.csv"
    assert results_csv.exists()
    df = pd.read_csv(results_csv)
    assert {"gene", "baseMean", "log2FoldChange", "pvalue", "padj", "is_de"} <= set(df.columns)
    assert len(df) == 60
    assert set(df["is_de"].unique()) <= {0, 1}


def test_generate_demo_counts_shape(tmp_path):
    counts, meta = generate_demo_counts(tmp_path, n_genes=30, n_samples=4)
    df = pd.read_csv(counts, index_col=0)
    md = pd.read_csv(meta)
    assert df.shape == (30, 4)  # 4 samples; genes are the row index
    assert df.index.is_unique
    assert list(df.index[:10]) == [
        "TP53", "BCL2", "CDKN1A", "MYC", "BRCA1", "VEGFA", "IL6", "SOD2", "EGFR", "PTEN",
    ]
    assert list(md["condition"]) == ["control", "control", "treated", "treated"]
