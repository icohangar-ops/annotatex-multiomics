"""Evidence-matrix tests — data-type detection (README Overview/Features).

Loads the real detector module from its file path (the repo's established
test idiom) so the tests need only pandas, not the heavy package import chain.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_detector():
    path = ROOT / "annotatex" / "pipeline" / "detector.py"
    spec = importlib.util.spec_from_file_location("annotatex_detector_under_test", path)
    module = importlib.util.module_from_spec(spec)
    # register in sys.modules so dataclass annotation resolution works (3.13+)
    sys.modules["annotatex_detector_under_test"] = module
    spec.loader.exec_module(module)
    return module


detector = _load_detector()


def test_detects_deseq2_expression_csv(tmp_path):
    p = tmp_path / "deseq2_results.csv"
    p.write_text(
        "gene,baseMean,log2FoldChange,lfcSE,stat,pvalue,padj,is_de\n"
        "TP53,1523.4,-2.30,0.31,-7.42,1.2e-13,3.4e-12,1\n"
        "BCL2,892.1,1.85,0.28,6.61,3.4e-9,4.1e-8,1\n"
    )
    result = detector.detect_data_type(p)
    assert result["data_type"] == "rna-seq"
    assert result["confidence"] >= 0.9


def test_detects_count_matrix(tmp_path):
    p = tmp_path / "counts.csv"
    p.write_text(
        "gene,sample_1,sample_2,sample_3,sample_4\n"
        "TP53,120,135,890,920\n"
        "BCL2,450,420,1100,1050\n"
    )
    result = detector.detect_data_type(p)
    assert result["data_type"] == "rna-seq"


def test_detects_chip_seq_peak_table(tmp_path):
    p = tmp_path / "peaks.csv"
    p.write_text("gene,peak_intensity,region\nX,10.5,chr1:100-200\nY,3.2,chr2:1-50\n")
    result = detector.detect_data_type(p)
    assert result["data_type"] == "chip-seq"


def test_detects_wgs_variant_table(tmp_path):
    p = tmp_path / "variants.csv"
    p.write_text("variant,chrom,pos,ref,alt\nrs1,1,100,A,G\nrs2,2,250,C,T\n")
    result = detector.detect_data_type(p)
    assert result["data_type"] == "wgs"


def test_detects_scrna_10x_directory(tmp_path):
    (tmp_path / "matrix.mtx").write_text("%%matrixmarket\n")
    result = detector.detect_data_type(tmp_path)
    assert result["data_type"] == "scrna-seq"


def test_detects_fastq(tmp_path):
    p = tmp_path / "sample.fastq"
    p.write_text("@read_1\nACGTACGTAC\n+\nIIIIIIIIII\n")
    result = detector.detect_data_type(p)
    assert result["data_type"] == "rna-seq"
    assert result["confidence"] >= 0.9


def test_detects_bam_file(tmp_path):
    p = tmp_path / "alignments.bam"
    p.write_bytes(b"\x1f\x8b\x00\x00")
    result = detector.detect_data_type(p)
    assert result["data_type"] == "wgs"
