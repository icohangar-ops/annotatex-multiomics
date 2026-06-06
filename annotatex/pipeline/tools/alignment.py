"""BWA and STAR alignment execution."""

from __future__ import annotations

from pathlib import Path

from annotatex.pipeline.tools.reference import ensure_reference
from annotatex.pipeline.tools.registry import ToolRegistry
from annotatex.pipeline.tools.runner import ToolRunner, StepResult


def index_reference(ref_dir: Path, runner: ToolRunner, aligner: str = "bwa") -> StepResult:
    refs = ensure_reference(ref_dir)
    fasta = refs["fasta"]

    if aligner == "bwa":
        registry = ToolRegistry()
        if not registry.is_available("bwa"):
            return runner.skip("bwa-index", "bwa not installed")
        if (ref_dir / "mini_genome.fa.bwt").exists():
            return StepResult("bwa-index", "existing index", "completed", 0, outputs=[str(fasta)])
        return runner.run("bwa-index", ["bwa", "index", str(fasta.resolve())], outputs=[ref_dir / "mini_genome.fa.bwt"])

    if aligner == "star":
        registry = ToolRegistry()
        if not registry.is_available("star"):
            return runner.skip("star-index", "STAR not installed")
        index_dir = ref_dir / "star_index"
        index_dir.mkdir(exist_ok=True)
        if (index_dir / "Genome").exists():
            return StepResult("star-index", "existing index", "completed", 0, outputs=[str(index_dir)])
        return runner.run(
            "star-index",
            [
                "STAR",
                "--runMode", "genomeGenerate",
                "--genomeDir", str(index_dir.resolve()),
                "--genomeFastaFiles", str(fasta.resolve()),
                "--genomeSAindexNbases", "4",
                "--runThreadN", "2",
            ],
            outputs=[index_dir / "Genome"],
        )

    return runner.skip(aligner, "Unknown aligner")


def align_fastq(fastq_path: Path, ref_dir: Path, output_dir: Path, runner: ToolRunner, aligner: str = "auto") -> StepResult:
    refs = ensure_reference(ref_dir)
    fastq = Path(fastq_path).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    registry = ToolRegistry()

    use_star = aligner == "star" or (aligner == "auto" and registry.is_available("star"))
    use_bwa = aligner == "bwa" or (aligner == "auto" and not use_star and registry.is_available("bwa"))

    if use_star:
        index_reference(ref_dir, runner, "star")
        bam = out_dir / "aligned.bam"
        result = runner.run(
            "star",
            [
                "STAR",
                "--genomeDir", str((ref_dir / "star_index").resolve()),
                "--readFilesIn", str(fastq),
                "--runThreadN", "2",
                "--outSAMtype", "BAM", "SortedByCoordinate",
                "--outFileNamePrefix", str(out_dir / "star_"),
                "--outStd", "Log",
            ],
            outputs=[out_dir / "star_Aligned.sortedByCoord.out.bam"],
        )
        star_bam = out_dir / "star_Aligned.sortedByCoord.out.bam"
        if result.status == "completed" and star_bam.exists() and star_bam.stat().st_size > 0:
            result.outputs = [str(star_bam)]
            return result
        # Fallback to BWA if STAR fails or produces empty output
        if registry.is_available("bwa"):
            use_bwa = True
        else:
            return result

    if use_bwa:
        index_reference(ref_dir, runner, "bwa")
        sam = out_dir / "aligned.sam"
        bam = out_dir / "aligned.bam"
        import subprocess
        import time

        cmd = ["bwa", "mem", "-t", "2", str(refs["fasta"].resolve()), str(fastq)]
        start = time.time()
        try:
            with open(sam, "w") as fh:
                proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, text=True, timeout=600)
            status = "completed" if proc.returncode == 0 else "failed"
            result = StepResult(
                tool="bwa",
                command=" ".join(cmd),
                status=status,
                duration_seconds=round(time.time() - start, 2),
                stderr=proc.stderr[-4000:] if proc.stderr else "",
                outputs=[str(sam)] if sam.exists() else [],
                error=None if proc.returncode == 0 else proc.stderr[-500:],
            )
        except Exception as exc:
            result = StepResult("bwa", " ".join(cmd), "failed", round(time.time() - start, 2), error=str(exc))
        runner.steps.append(result)
        if result.status != "completed":
            return result

        if registry.is_available("samtools"):
            sort_result = runner.run(
                "samtools-sort",
                ["samtools", "sort", "-@", "2", "-o", str(bam), str(sam)],
                outputs=[bam],
            )
            return sort_result
        return result

    return runner.skip("aligner", "No aligner available (install STAR or BWA)")
