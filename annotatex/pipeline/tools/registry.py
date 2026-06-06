"""Detect and report availability of bioinformatics tools."""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    command: str
    category: str
    install_hint: str


TOOLS: list[ToolSpec] = [
    ToolSpec("fastqc", "fastqc", "qc", "conda install -c bioconda fastqc"),
    ToolSpec("samtools", "samtools", "alignment", "conda install -c bioconda samtools"),
    ToolSpec("star", "STAR", "alignment", "conda install -c bioconda star"),
    ToolSpec("bwa", "bwa", "alignment", "conda install -c bioconda bwa"),
    ToolSpec("featurecounts", "featureCounts", "quantification", "conda install -c bioconda subread"),
    ToolSpec("macs2", "macs2", "peak-calling", "conda install -c bioconda macs2"),
    ToolSpec("multiqc", "multiqc", "qc", "conda install -c bioconda multiqc"),
    ToolSpec("pydeseq2", "python -c 'import pydeseq2'", "de-analysis", "pip install pydeseq2"),
    ToolSpec("biopython", "python -c 'import Bio'", "parsing", "pip install biopython"),
    ToolSpec("pysam", "python -c 'import pysam'", "parsing", "pip install pysam"),
]


class ToolRegistry:
    def __init__(self) -> None:
        self._cache: dict[str, bool] = {}

    def is_available(self, name: str) -> bool:
        if name not in self._cache:
            self._cache[name] = _check_tool(name)
        return self._cache[name]

    def available_tools(self) -> list[str]:
        return [spec.name for spec in TOOLS if self.is_available(spec.name)]

    def status_report(self) -> list[dict]:
        return [
            {
                "name": spec.name,
                "category": spec.category,
                "available": self.is_available(spec.name),
                "install_hint": spec.install_hint,
            }
            for spec in TOOLS
        ]


def get_tool_status() -> list[dict]:
    return ToolRegistry().status_report()


def _check_tool(name: str) -> bool:
    spec = next((t for t in TOOLS if t.name == name), None)
    if spec is None:
        return False

    if spec.command.startswith("python "):
        import subprocess

        try:
            subprocess.run(spec.command, shell=True, check=True, capture_output=True, timeout=10)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

    return shutil.which(spec.command) is not None
