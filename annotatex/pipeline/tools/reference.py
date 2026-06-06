"""Reference genome helpers for alignment pipelines."""

from __future__ import annotations

from pathlib import Path

REF_DIR = Path(__file__).resolve().parents[3] / "data" / "reference"

MINI_FASTA = """>TP53
ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT
ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT
>BCL2
GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA
GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA
>MYC
TTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAA
TTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAATTAA
>BRCA1
CGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGAT
CGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGAT
>EGFR
ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGC
ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGC
"""

MINI_GTF = """TP53\tAnnotateX\texon\t1\t128\t.\t+\t.\tgene_id "TP53"; transcript_id "TP53.1";
BCL2\tAnnotateX\texon\t1\t128\t.\t+\t.\tgene_id "BCL2"; transcript_id "BCL2.1";
MYC\tAnnotateX\texon\t1\t128\t.\t+\t.\tgene_id "MYC"; transcript_id "MYC.1";
BRCA1\tAnnotateX\texon\t1\t128\t.\t+\t.\tgene_id "BRCA1"; transcript_id "BRCA1.1";
EGFR\tAnnotateX\texon\t1\t128\t.\t+\t.\tgene_id "EGFR"; transcript_id "EGFR.1";
"""


def ensure_reference(ref_dir: Path | None = None) -> dict[str, Path]:
    ref_dir = Path(ref_dir or REF_DIR)
    ref_dir.mkdir(parents=True, exist_ok=True)

    fasta = ref_dir / "mini_genome.fa"
    gtf = ref_dir / "mini_genes.gtf"
    if not fasta.exists():
        fasta.write_text(MINI_FASTA)
    if not gtf.exists():
        gtf.write_text(MINI_GTF)

    return {"fasta": fasta, "gtf": gtf, "dir": ref_dir}
