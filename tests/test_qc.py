"""Evidence-matrix tests — statistical QC checks (README Overview QC row).

Loads the real qc module from its file path so the tests need only
pandas/numpy, not the heavy package import chain.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_qc():
    path = ROOT / "annotatex" / "pipeline" / "qc.py"
    spec = importlib.util.spec_from_file_location("annotatex_qc_under_test", path)
    module = importlib.util.module_from_spec(spec)
    # register in sys.modules so dataclass annotation resolution works (3.13+)
    sys.modules["annotatex_qc_under_test"] = module
    spec.loader.exec_module(module)
    return module


qc = _load_qc()


def _expression_csv(tmp_path, n_genes=250):
    lines = ["gene,baseMean,log2FoldChange,lfcSE,stat,pvalue,padj,is_de"]
    for i in range(n_genes):
        lines.append(
            f"G{i},{100 + (i % 50) * 7.5:.2f},{(1 if i % 2 else -1) * (1 + i % 3):.3f},"
            f"0.25,{(1 if i % 2 else -1) * (1 + i % 3) / 0.25:.2f},"
            f"{0.0001 * (i + 1):.6f},{0.01 + (i % 20) * 0.005:.4f},{1 if i % 10 == 0 else 0}"
        )
    p = tmp_path / "expression.csv"
    p.write_text("\n".join(lines) + "\n")
    return p


def test_expression_qc_pass(tmp_path):
    p = _expression_csv(tmp_path)
    result = qc.run_qc(p, "rna-seq")
    assert result["status"] == "pass"
    check_names = {c["name"] for c in result["checks"]}
    assert {"required_columns", "min_genes", "padj_range"} <= check_names
    assert all(c["passed"] for c in result["checks"])
    assert result["n_genes"] == 250


def test_expression_qc_required_columns_fail(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("gene,foo\nG1,1\nG2,2\n")
    result = qc.run_qc(p, "rna-seq")
    assert result["status"] == "fail"
    failed = {c["name"] for c in result["checks"] if not c["passed"]}
    assert "required_columns" in failed


def test_fastq_qc_reads(tmp_path):
    p = tmp_path / "sample.fastq"
    read = "@read_1\n" + "ACGT" * 20 + "\n+\n" + "I" * 80 + "\n"
    p.write_text(read * 10)
    result = qc.run_qc(p, "rna-seq")
    assert result["status"] == "pass"
    check_names = {c["name"] for c in result["checks"]}
    assert {"fastq_readable", "read_length"} <= check_names
