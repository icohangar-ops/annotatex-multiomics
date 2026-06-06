"""Auto-detect omics data type from file format and column signatures."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RNA_SEQ_COLS = {"gene", "baseMean", "log2FoldChange", "padj"}
VCF_EXTENSIONS = {".vcf", ".vcf.gz"}
FASTQ_EXTENSIONS = {".fastq", ".fq", ".fastq.gz", ".fq.gz"}
BAM_EXTENSIONS = {".bam", ".cram"}


def detect_data_type(path: str | Path) -> dict:
    path = Path(path)

    if path.is_dir():
        files = list(path.glob("*"))
        if any(f.suffix in {".h5", ".h5ad"} or "matrix" in f.name.lower() for f in files):
            return _result("scrna-seq", "10X matrix directory detected", confidence=0.85)
        return _result("unknown", "Directory without recognized omics signature", confidence=0.3)

    suffixes = "".join(path.suffixes) if path.suffixes else path.suffix
    name = path.name.lower()

    if any(name.endswith(ext) for ext in FASTQ_EXTENSIONS):
        return _detect_fastq(path)
    if any(name.endswith(ext.lstrip(".")) for ext in BAM_EXTENSIONS) or path.suffix in BAM_EXTENSIONS:
        return _result("wgs", f"BAM/CRAM alignment file: {path.name}", confidence=0.8)
    if any(name.endswith(ext.lstrip(".")) for ext in VCF_EXTENSIONS) or ".vcf" in name:
        return _result("wgs", f"VCF variant file: {path.name}", confidence=0.85)

    if path.suffix in {".csv", ".tsv", ".txt"}:
        return _detect_tabular(path)

    metadata_path = path.parent / "metadata.json"
    if metadata_path.exists():
        meta = json.loads(metadata_path.read_text())
        return _result(meta.get("omics_type", "rna-seq"), "metadata.json", confidence=0.95)

    return _result("unknown", f"Unrecognized file type: {path.suffix}", confidence=0.2)


def _detect_fastq(path: Path) -> dict:
    try:
        opener = open
        if str(path).endswith(".gz"):
            import gzip

            opener = gzip.open
        with opener(path, "rt") as fh:
            header = fh.readline().strip()
        if header.startswith("@"):
            paired_hint = "_R1" in path.name or "_R2" in path.name
            return _result(
                "rna-seq",
                f"FASTQ detected ({'paired-end' if paired_hint else 'single-end'})",
                confidence=0.9,
                extra={"format": "fastq", "paired": paired_hint},
            )
    except OSError:
        pass
    return _result("rna-seq", "FASTQ-like extension", confidence=0.6)


def _detect_tabular(path: Path) -> dict:
    sep = "\t" if path.suffix == ".tsv" else ","
    try:
        df = pd.read_csv(path, sep=sep, nrows=5)
    except Exception as exc:
        return _result("unknown", f"Failed to parse tabular file: {exc}", confidence=0.1)

    cols = {c.lower() for c in df.columns.str.lower()}
    normalized = {c.lower(): c for c in df.columns}

    if RNA_SEQ_COLS.issubset(cols) or {"gene", "log2foldchange", "padj"}.issubset(cols):
        return _result(
            "rna-seq",
            "DESeq2-style expression matrix",
            confidence=0.95,
            extra={"columns": list(df.columns)},
        )

    col_names_lower = [c.lower() for c in df.columns]
    if any("peak" in c for c in col_names_lower):
        return _result("chip-seq", "ChIP-seq peak table detected", confidence=0.8)
    if any(c in col_names_lower for c in ["variant", "chrom", "pos", "ref", "alt"]):
        return _result("wgs", "Variant table detected", confidence=0.85)

    return _result("rna-seq", "Generic expression/count table (defaulting to RNA-seq)", confidence=0.5)


def _result(data_type: str, reason: str, confidence: float, extra: dict | None = None) -> dict:
    out = {"data_type": data_type, "reason": reason, "confidence": confidence}
    if extra:
        out.update(extra)
    return out
