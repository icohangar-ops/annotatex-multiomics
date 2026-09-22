"""Evidence-matrix tests — FastQC and samtools parsers (README Features).

Imports the real package modules (full requirements are installed for tests).
"""
from annotatex.pipeline.tools.fastqc import parse_fastqc_summary
from annotatex.pipeline.tools.samtools import parse_flagstat


def _write_fastqc_report(output_dir, stem, lines):
    (output_dir / "fastqc" / f"{stem}_fastqc").mkdir(parents=True)
    (output_dir / "fastqc" / f"{stem}_fastqc" / "summary.txt").write_text(
        "\n".join(lines) + "\n"
    )


def test_parse_fastqc_summary_all_pass(tmp_path):
    out = tmp_path / "out"
    _write_fastqc_report(out, "demo", [
        "PASS\tBasic Statistics\tdemo.fastq",
        "PASS\tPer base sequence quality\tdemo.fastq",
        "PASS\tSequence Length Distribution\tdemo.fastq",
    ])
    result = parse_fastqc_summary(tmp_path / "demo.fastq", out)
    assert result["status"] == "pass"
    assert result["summary"] == "FastQC: 3 PASS, 0 WARN, 0 FAIL"
    assert [c["status"] for c in result["checks"]] == ["PASS", "PASS", "PASS"]


def test_parse_fastqc_summary_warn(tmp_path):
    out = tmp_path / "out"
    _write_fastqc_report(out, "demo", [
        "PASS\tBasic Statistics\tdemo.fastq",
        "WARN\tSequence Length Distribution\tdemo.fastq",
    ])
    result = parse_fastqc_summary(tmp_path / "demo.fastq", out)
    assert result["status"] == "warn"
    assert result["summary"] == "FastQC: 1 PASS, 1 WARN, 0 FAIL"


def test_parse_fastqc_summary_missing_report(tmp_path):
    result = parse_fastqc_summary(tmp_path / "demo.fastq", tmp_path / "out")
    assert result["status"] == "no_report"


def test_parse_flagstat(tmp_path):
    flagstat = tmp_path / "flagstat.txt"
    flagstat.write_text(
        "1000 + 0 in total (Primary)\n"
        "950 + 0 mapped\n"
        "50 + 0 unmapped\n"
    )
    metrics = parse_flagstat(flagstat.read_text())
    assert metrics["+ 0 in total (Primary)"] == 1000
    assert metrics["+ 0 mapped"] == 950
    assert metrics["+ 0 unmapped"] == 50
