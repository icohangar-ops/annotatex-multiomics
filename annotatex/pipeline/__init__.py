"""Pipeline components: detection, QC, orchestration, reporting."""

from annotatex.pipeline.detector import detect_data_type
from annotatex.pipeline.orchestrator import PipelineOrchestrator
from annotatex.pipeline.qc import run_qc
from annotatex.pipeline.reporter import generate_report

__all__ = ["detect_data_type", "run_qc", "PipelineOrchestrator", "generate_report"]
