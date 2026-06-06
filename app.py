#!/usr/bin/env python3
"""AnnotateX Gradio UI — multi-omics pipeline with real bioinformatics tools + Lightning ML."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import gradio as gr
import pandas as pd

from annotatex.data.generator import generate_synthetic_dataset
from annotatex.pipeline.orchestrator import PipelineOrchestrator
from annotatex.pipeline.tools.registry import get_tool_status

CHECKPOINT = Path("checkpoints/annotatex-best.ckpt")
UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")


def ensure_model() -> str:
    if CHECKPOINT.exists():
        return "Model ready"
    if not Path("data/synthetic/expression.csv").exists():
        generate_synthetic_dataset(n_genes=2000, output_dir="data/synthetic")
    subprocess.run([sys.executable, "train.py", "--epochs", "8", "--data-dir", "data/synthetic"], check=True)
    return "Model trained"


def format_tool_status() -> pd.DataFrame:
    return pd.DataFrame(get_tool_status())


def run_pipeline(
    file_obj,
    data_type: str,
    skip_qc: bool,
    skip_bio: bool,
    max_genes: int,
    progress=gr.Progress(),
) -> tuple[str, str, pd.DataFrame, str | None, str]:
    if file_obj is None:
        return "Upload a file to begin.", "", pd.DataFrame(), None, ""

    progress(0.1, desc="Preparing...")
    ensure_model()

    UPLOAD_DIR.mkdir(exist_ok=True)
    src = Path(file_obj.name if hasattr(file_obj, "name") else file_obj)
    dest = UPLOAD_DIR / src.name
    shutil.copy(src, dest)

    progress(0.3, desc="Running bioinformatics + ML pipeline...")
    resolved_type = None if data_type == "auto" else data_type

    try:
        result = PipelineOrchestrator(model_path=CHECKPOINT, output_dir=RESULTS_DIR).run(
            data_path=dest,
            data_type=resolved_type,
            skip_qc=skip_qc,
            skip_bio=skip_bio,
            max_genes=max_genes if max_genes > 0 else None,
        )
    except Exception as exc:
        return f"Pipeline failed: {exc}", "", pd.DataFrame(), None, ""

    progress(0.9, desc="Building report...")

    summary = _format_summary(result)
    bio_log = _format_bio_log(result.get("bio_pipeline", {}))

    genes_df = pd.DataFrame()
    run_dir = RESULTS_DIR / result["run_id"]
    ann_path = run_dir / "annotations.csv"
    expr_path = run_dir / "expression.csv"
    if ann_path.exists() and expr_path.exists():
        ann = pd.read_csv(ann_path)
        expr = pd.read_csv(expr_path)
        merged = expr.merge(ann, on="gene")
        cols = [c for c in ["gene", "log2FoldChange", "padj", "de_confidence", "top_pathway", "annotation"] if c in merged.columns]
        genes_df = merged[cols].head(20)

    report_path = result.get("report_html")
    progress(1.0, desc="Done")
    return summary, bio_log, genes_df, report_path, json.dumps(result, indent=2, default=str)


def run_dry_run(file_obj, data_type: str) -> str:
    if file_obj is None:
        return "Upload a file first."
    src = Path(file_obj.name if hasattr(file_obj, "name") else file_obj)
    resolved_type = None if data_type == "auto" else data_type
    result = PipelineOrchestrator(output_dir=RESULTS_DIR).run(
        data_path=src, data_type=resolved_type, dry_run=True
    )
    return json.dumps(result, indent=2, default=str)


def load_demo_data() -> str:
    generate_synthetic_dataset(n_genes=1500, output_dir="data/demo")
    return str(Path("data/demo/expression.csv").resolve())


def _format_summary(result: dict) -> str:
    lines = [
        f"**Status:** {result.get('status', 'unknown')}",
        f"**Run ID:** `{result.get('run_id')}`",
        f"**Data type:** {result.get('data_type')}",
        f"**Genes:** {result.get('n_genes', '—')}",
        f"**DE genes (padj < 0.05):** {result.get('n_de_genes', '—')}",
        f"**QC:** {result.get('qc_status', '—')}",
        f"**Duration:** {result.get('duration_seconds', '—')}s",
    ]
    if result.get("report_html"):
        lines.append(f"**Report:** `{result['report_html']}`")
    return "\n\n".join(lines)


def _format_bio_log(bio: dict) -> str:
    if not bio or not bio.get("steps"):
        return "No bioinformatics steps executed."
    lines = [f"Tools available: {', '.join(bio.get('available_tools', []))}", ""]
    for step in bio["steps"]:
        icon = {"completed": "✅", "failed": "❌", "skipped": "⏭️"}.get(step["status"], "•")
        lines.append(f"{icon} **{step['tool']}** ({step['status']}, {step.get('duration_seconds', 0)}s)")
        if step.get("error"):
            lines.append(f"   _{step['error'][:200]}_")
        elif step.get("command"):
            lines.append(f"   `{step['command'][:100]}`")
    return "\n".join(lines)


def build_app() -> gr.Blocks:
    with gr.Blocks(title="AnnotateX — Lightning AI & Graphn AI Hackathon") as app:
        gr.Markdown(
            """
# AnnotateX Multi-Omics
**Lightning AI & Graphn AI Hackathon**

Real bioinformatics tools (FastQC, samtools, PyDESeq2) + **PyTorch Lightning** gene annotation with confidence scores.

Built on [Lightning.AI](https://lightning.ai/)
            """
        )

        with gr.Tab("Pipeline"):
            with gr.Row():
                with gr.Column(scale=1):
                    file_input = gr.File(label="Upload data", file_types=[".csv", ".tsv", ".fastq", ".fq", ".gz", ".bam"])
                    data_type = gr.Dropdown(
                        choices=["auto", "rna-seq", "chip-seq", "wgs", "scrna-seq"],
                        value="auto",
                        label="Omics type",
                    )
                    skip_qc = gr.Checkbox(label="Skip QC checks", value=False)
                    skip_bio = gr.Checkbox(label="Skip bioinformatics tools (ML only)", value=False)
                    max_genes = gr.Slider(100, 5000, value=0, step=100, label="Max genes (0 = all)")
                    demo_btn = gr.Button("Load demo expression data", variant="secondary")
                    run_btn = gr.Button("Run Pipeline", variant="primary")
                    dry_btn = gr.Button("Dry Run (preview tools)")

                with gr.Column(scale=2):
                    summary_out = gr.Markdown(label="Summary")
                    bio_log_out = gr.Markdown(label="Tool execution log")
                    genes_out = gr.Dataframe(label="Top annotated genes", interactive=False)
                    report_out = gr.File(label="Download HTML report")
                    json_out = gr.Code(label="Full results JSON", language="json")

            demo_path = gr.Textbox(visible=False)
            demo_btn.click(fn=load_demo_data, outputs=demo_path)

            run_btn.click(
                fn=run_pipeline,
                inputs=[file_input, data_type, skip_qc, skip_bio, max_genes],
                outputs=[summary_out, bio_log_out, genes_out, report_out, json_out],
            )
            dry_btn.click(fn=run_dry_run, inputs=[file_input, data_type], outputs=json_out)

        with gr.Tab("Tool Status"):
            gr.Markdown("### Installed bioinformatics tools")
            tools_table = gr.Dataframe(value=format_tool_status(), interactive=False)
            refresh_btn = gr.Button("Refresh")
            refresh_btn.click(fn=format_tool_status, outputs=tools_table)
            gr.Markdown(
                """
Install missing tools:
```bash
bash scripts/install_bioinfo.sh
# or manually:
conda install -c bioconda fastqc samtools star subread
pip install pydeseq2 biopython pysam
```
                """
            )

        with gr.Tab("Train Model"):
            gr.Markdown("### Train AnnotateX Lightning model on synthetic data")
            epochs = gr.Slider(5, 30, value=10, step=1, label="Epochs")
            n_genes = gr.Slider(500, 5000, value=2000, step=500, label="Synthetic genes")
            train_btn = gr.Button("Train", variant="primary")
            train_log = gr.Textbox(label="Training output", lines=15)

            def train_model(ep: int, ng: int) -> str:
                proc = subprocess.run(
                    [sys.executable, "train.py", "--generate", "--epochs", str(int(ep)), "--n-genes", str(int(ng))],
                    capture_output=True,
                    text=True,
                )
                return proc.stdout + proc.stderr

            train_btn.click(fn=train_model, inputs=[epochs, n_genes], outputs=train_log)

    return app


if __name__ == "__main__":
    ensure_model()
    app = build_app()
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
