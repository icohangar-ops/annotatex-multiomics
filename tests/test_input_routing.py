"""Evidence-matrix tests — input-type routing (README Features).

Checks that BioPipeline routes counts matrices to PyDESeq2 and pre-scored
expression CSVs straight to interpretation without re-running DE.
"""
from annotatex.pipeline.tools.bio_pipeline import BioPipeline


def test_counts_matrix_routes_to_deseq2(tmp_path):
    counts = tmp_path / "counts.csv"
    counts.write_text(
        "gene,sample_1,sample_2,sample_3,sample_4\n"
        "TP53,120,135,890,920\n"
        "BCL2,450,420,1100,1050\n"
    )
    assert BioPipeline._is_counts(counts) is True
    assert BioPipeline._is_expression(counts) is False


def test_expression_csv_routes_without_rerunning_de(tmp_path):
    expr = tmp_path / "deseq2_results.csv"
    expr.write_text("gene,baseMean,log2FoldChange,padj\nTP53,100,-2.3,0.001\n")
    assert BioPipeline._is_expression(expr) is True
    assert BioPipeline._is_counts(expr) is False


def test_fastq_and_bam_routing(tmp_path):
    fastq = tmp_path / "reads.fastq"
    fastq.write_text("@r\nACGT\n+\nIIII\n")
    assert BioPipeline._is_fastq(fastq) is True

    gz = tmp_path / "reads.fastq.gz"
    gz.write_text("@r\nACGT\n+\nIIII\n")
    assert BioPipeline._is_fastq(gz) is True

    bam = tmp_path / "alignments.bam"
    bam.write_bytes(b"\x1f\x8b\x00\x00")
    assert BioPipeline._is_bam(bam) is True
