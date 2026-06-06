"""Quality control checks for expression and sequencing inputs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def run_qc(data_path: str | Path, data_type: str) -> dict:
    path = Path(data_path)

    if data_type == "rna-seq" and path.suffix in {".csv", ".tsv", ".txt"}:
        return _qc_expression_matrix(path)
    if str(path).endswith((".fastq", ".fq", ".fastq.gz", ".fq.gz")):
        return _qc_fastq(path)

    return {
        "status": "skipped",
        "checks": [],
        "summary": f"QC not implemented for {data_type} file type; proceeding with ML analysis.",
    }


def _qc_expression_matrix(path: Path) -> dict:
    sep = "\t" if path.suffix == ".tsv" else ","
    df = pd.read_csv(path, sep=sep)
    checks = []

    required = ["gene", "padj"]
    missing = [c for c in required if c not in df.columns and c.lower() not in [x.lower() for x in df.columns]]
    checks.append(_check("required_columns", len(missing) == 0, f"Missing: {missing}" if missing else "All required columns present"))

    n_genes = len(df)
    checks.append(_check("min_genes", n_genes >= 100, f"{n_genes} genes detected"))

    padj_col = _find_col(df, "padj")
    if padj_col:
        valid_padj = df[padj_col].between(0, 1).mean()
        checks.append(_check("padj_range", valid_padj > 0.95, f"{valid_padj:.1%} padj values in [0,1]"))

    lfc_col = _find_col(df, "log2FoldChange")
    if lfc_col:
        extreme = (df[lfc_col].abs() > 10).sum()
        checks.append(_check("fold_change_sanity", extreme < n_genes * 0.01, f"{extreme} extreme log2FC values"))

    base_col = _find_col(df, "baseMean")
    if base_col:
        low_expr = (df[base_col] < 1).mean()
        checks.append(_check("expression_depth", low_expr < 0.8, f"{low_expr:.1%} low-expression genes"))

    passed = sum(1 for c in checks if c["passed"])
    status = "pass" if passed == len(checks) else ("warn" if passed >= len(checks) - 1 else "fail")

    return {
        "status": status,
        "checks": checks,
        "summary": f"QC {status}: {passed}/{len(checks)} checks passed for {n_genes} genes",
        "n_genes": n_genes,
    }


def _qc_fastq(path: Path) -> dict:
    checks = []
    try:
        import gzip

        opener = gzip.open if str(path).endswith(".gz") else open
        mode = "rt"
        n_reads = 0
        read_lengths = []
        with opener(path, mode) as fh:
            while True:
                header = fh.readline()
                if not header:
                    break
                seq = fh.readline()
                fh.readline()
                fh.readline()
                if not seq:
                    break
                n_reads += 1
                read_lengths.append(len(seq.strip()))
                if n_reads >= 1000:
                    break

        checks.append(_check("fastq_readable", n_reads > 0, f"Sampled {n_reads} reads"))
        if read_lengths:
            mean_len = np.mean(read_lengths)
            checks.append(_check("read_length", 50 <= mean_len <= 300, f"Mean read length: {mean_len:.0f} bp"))
    except OSError as exc:
        checks.append(_check("fastq_readable", False, str(exc)))

    passed = sum(1 for c in checks if c["passed"])
    status = "pass" if passed == len(checks) else "warn"
    return {"status": status, "checks": checks, "summary": f"FASTQ QC: {passed}/{len(checks)} checks passed"}


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _find_col(df: pd.DataFrame, name: str) -> str | None:
    for col in df.columns:
        if col.lower() == name.lower():
            return col
    return None
