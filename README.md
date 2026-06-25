# AnnotateX Multi-Omics — Lightning AI & Graphn AI Hackathon

**Submission for the [Lightning AI](https://lightning.ai/) & Graphn AI Hackathon**

> Autonomous multi-omics pipeline: FastQC → PyDESeq2 → PyTorch Lightning gene annotation with confidence scores.

[![Lightning.AI](https://img.shields.io/badge/Lightning-AI-792EE5)](https://lightning.ai/)
[![Graphn AI](https://img.shields.io/badge/Graphn-AI-2563EB)](https://graphn.ai/)
[![PyTorch Lightning](https://img.shields.io/badge/PyTorch-Lightning-EE4C2C)](https://lightning.ai/docs/pytorch/stable/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Quick Start](#quick-start)
- [Gradio UI](#gradio-ui)
- [Bioinformatics Tools](#bioinformatics-tools)
- [ML Model](#ml-model)
- [CLI Reference](#cli-reference)
- [Input Formats](#input-formats)
- [Sample Output](#sample-output)
- [Project Structure](#project-structure)
- [Lightning Studio Setup](#lightning-studio-setup)
- [Troubleshooting](#troubleshooting)

---

## Overview

AnnotateX accepts raw or processed omics data, runs **real bioinformatics tools** where available, performs **differential expression** via PyDESeq2, then applies a **PyTorch Lightning** model for gene-level annotation and confidence scoring.

| Stage | Technology | What it does |
|-------|-----------|--------------|
| Data detection | Rule-based + column signatures | Auto-identify RNA-seq, ChIP-seq, WGS, scRNA-seq |
| QC | **FastQC** (real) + statistical checks | Per-sample quality metrics |
| Alignment stats | **samtools flagstat** (real) | BAM read mapping statistics |
| DE analysis | **PyDESeq2** (real) | Wald test differential expression |
| Annotation | **PyTorch Lightning** MLP | GO pathway prediction + MC dropout confidence |
| UI | **Gradio** | Drag-and-drop pipeline runner |

---

## Architecture

```
                         ┌─────────────────────────────────┐
  Upload (FASTQ/CSV/BAM) │         Gradio UI (app.py)       │
                         └──────────────┬──────────────────┘
                                        │
                         ┌──────────────▼──────────────────┐
                         │     Pipeline Orchestrator        │
                         │  detect → bio tools → ML → report│
                         └──────────────┬──────────────────┘
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
             ┌────────────┐    ┌────────────┐    ┌────────────┐
             │  FastQC     │    │  PyDESeq2  │    │ AnnotateX  │
             │  samtools   │    │  (real DE) │    │ Lightning  │
             │  (subprocess│    │            │    │ Module     │
             │   CLI)      │    │            │    │ + MC drop  │
             └──────┬──────┘    └──────┬──────┘    └──────┬─────┘
                    │                  │                  │
                    └──────────────────┼──────────────────┘
                                       ▼
                         ┌─────────────────────────────────┐
                         │  HTML + JSON Report              │
                         │  • Tool execution log            │
                         │  • QC pass/fail                  │
                         │  • Top genes + confidence        │
                         └─────────────────────────────────┘
```

---

## Features

| Capability | Implementation |
|-----------|----------------|
| **Gradio UI** | Drag-and-drop upload, live tool log, gene table, HTML report download |
| **Real FastQC** | Subprocess execution with summary.txt parsing |
| **Real samtools** | `flagstat` on BAM files |
| **Real PyDESeq2** | Full Wald-test DE from count matrices |
| **Lightning ML** | Multi-task DE + GO annotation with MC dropout confidence |
| **Auto detection** | FASTQ, BAM, count matrix, DESeq2 results CSV |
| **Tool registry** | Reports installed/missing tools with install hints |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
bash scripts/install_bioinfo.sh

# 2. Train the Lightning model (or skip — UI auto-trains)
python train.py --generate --epochs 10

# 3. Launch Gradio UI
python app.py

# 4. Or run CLI pipeline
python pipeline.py --data data/synthetic/expression.csv --verbose
```

---

## Gradio UI

Launch the web interface:

```bash
python app.py
# → http://0.0.0.0:7860
```

### Tabs

| Tab | Purpose |
|-----|---------|
| **Pipeline** | Upload data, run full analysis, view genes + download report |
| **Tool Status** | See which bioinformatics tools are installed |
| **Train Model** | Retrain AnnotateX on synthetic data |

### Supported uploads

- `.csv` / `.tsv` — expression results or count matrices
- `.fastq` / `.fq` / `.fastq.gz` — runs FastQC + PyDESeq2 pipeline
- `.bam` — runs samtools flagstat + expression pipeline

---

## Bioinformatics Tools

### Daytona sandbox (optional)

Export `DAYTONA_API_KEY` to run bioinformatics CLI commands inside an isolated Daytona VM. The pipeline uploads the work directory before each tool step. Bio tools must be present in the sandbox image or commands will be skipped as today.

Install all tools:

```bash
bash scripts/install_bioinfo.sh
```

| Tool | Type | Role | Install |
|------|------|------|---------|
| **FastQC** | CLI (bioconda) | Read quality control | `conda install -c bioconda fastqc` |
| **samtools** | CLI (bioconda) | BAM statistics | `conda install -c bioconda samtools` |
| **PyDESeq2** | Python | Differential expression | `pip install pydeseq2` |
| **STAR** | CLI (optional) | Read alignment | `conda install -c bioconda star` |
| **featureCounts** | CLI (optional) | Gene quantification | `conda install -c bioconda subread` |
| **multiqc** | CLI (optional) | Aggregate QC reports | `conda install -c bioconda multiqc` |

Check status programmatically:

```python
from annotatex.pipeline.tools.registry import get_tool_status
print(get_tool_status())
```

### Pipeline flows by input type

| Input | Tools executed | Output |
|-------|---------------|--------|
| FASTQ | FastQC → demo counts → PyDESeq2 | DE results CSV |
| Count matrix + metadata | PyDESeq2 | DE results CSV |
| DESeq2 results CSV | (skip DE) | Direct to ML |
| BAM | samtools flagstat → PyDESeq2 | DE results CSV |

---

## ML Model

**AnnotateXModule** — PyTorch Lightning multi-task classifier:

```
Input (6 features)          Shared MLP encoder          Task heads
─────────────────          ──────────────────          ──────────
baseMean                 ┌─ Linear(6→128) ─┐         DE: sigmoid (binary)
log2FoldChange           │  BatchNorm+ReLU  │         GO: sigmoid × 10 (multi-label)
lfcSE                    │  Linear(128→128) │
stat                     │  BatchNorm+ReLU  │
pvalue                   └──────────────────┘
padj
```

- **Training**: AdamW + ReduceLROnPlateau, early stopping on val loss
- **Confidence**: 20-pass Monte Carlo dropout at inference
- **Metrics**: DE accuracy/F1, GO macro-F1

```bash
python train.py --generate --n-genes 3000 --epochs 15 --hidden-dim 128
# Checkpoint → checkpoints/annotatex-best.ckpt
```

---

## CLI Reference

```bash
# Full pipeline with bioinformatics tools
python pipeline.py --data sample.fastq.gz --type rna-seq --verbose

# Skip bio tools (ML annotation only)
python pipeline.py --data expression.csv --skip-bio

# Dry run — preview tool plan
python pipeline.py --data sample.csv --dry-run

# Regenerate HTML report
python annotate.py --results results/pipeline_1234567890

# Train model
python train.py --generate --epochs 15
```

---

## Input Formats

### DESeq2 results CSV (direct to ML)

```csv
gene,baseMean,log2FoldChange,lfcSE,stat,pvalue,padj,is_de
TP53,1523.4,-2.30,0.31,-7.42,1.2e-13,3.4e-12,1
BCL2,892.1,1.85,0.28,6.61,3.4e-9,4.1e-8,1
```

### Count matrix (runs PyDESeq2)

`counts.csv`:
```csv
gene,sample_1,sample_2,sample_3,sample_4
TP53,120,135,890,920
BCL2,450,420,1100,1050
```

`metadata.csv`:
```csv
sample,condition
sample_1,control
sample_2,control
sample_3,treated
sample_4,treated
```

### FASTQ

Standard FASTQ — triggers FastQC, then count generation + PyDESeq2.

---

## Sample Output

```json
{
  "status": "completed",
  "run_id": "pipeline_1780760089",
  "data_type": "rna-seq",
  "n_genes": 500,
  "n_de_genes": 87,
  "qc_status": "pass",
  "bio_pipeline": {
    "completed": 2,
    "total_steps": 2,
    "steps": [
      {"tool": "fastqc", "status": "completed", "duration_seconds": 3.2},
      {"tool": "pydeseq2", "status": "completed", "duration_seconds": 1.8}
    ]
  },
  "report_html": "results/pipeline_1780760089/report.html"
}
```

---

## Project Structure

```
annotatex/
├── data/
│   ├── generator.py          # Synthetic DESeq2 + GO labels
│   └── datamodule.py         # Lightning DataModule
├── models/
│   └── annotatex.py          # LightningModule (DE + GO heads)
└── pipeline/
    ├── detector.py           # Auto data-type detection
    ├── qc.py                 # Statistical QC checks
    ├── orchestrator.py       # End-to-end orchestration
    ├── reporter.py           # HTML/JSON reports
    └── tools/
        ├── registry.py       # Tool availability detection
        ├── runner.py         # Subprocess execution + logging
        ├── fastqc.py         # FastQC integration
        ├── samtools.py       # samtools flagstat
        ├── deseq2.py         # PyDESeq2 DE analysis
        └── bio_pipeline.py   # Bioinformatics stage orchestrator
app.py                        # Gradio UI
train.py                      # Model training CLI
pipeline.py                   # Pipeline CLI
main.py                       # Lightning Studio entry point
scripts/install_bioinfo.sh    # Tool installer
```

---

## Lightning Studio Setup

This project is configured for [Lightning Studio](https://lightning.ai/):

1. **Auto-start**: `.lightning_studio/on_start.sh` installs tools and launches Gradio
2. **Entry point**: `python main.py` trains (if needed) then opens UI on port 7860
3. **GPU training**: Lightning Trainer auto-detects CUDA
4. **Checkpoints**: Persist in `checkpoints/` across sessions

Manual launch:

```bash
python app.py
```

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `FastQC not found` | Missing bioconda package | `conda install -c bioconda fastqc` |
| `PyDESeq2 import failed` | Missing pip package | `pip install pydeseq2` |
| `Model checkpoint not found` | Model not trained | `python train.py --generate` |
| Empty GO predictions | Sparse training labels | Train longer or lower threshold in orchestrator |
| Gradio port in use | Another process on 7860 | `app.launch(server_port=7861)` |
| Pipeline timeout on large FASTQ | FastQC slow on big files | Subsample reads or use pre-computed counts |

---

## Hackathon Submission

Built for the **Lightning AI & Graphn AI Hackathon**.

| Track focus | How AnnotateX addresses it |
|---|---|
| **Lightning AI** | Full PyTorch Lightning training, GPU inference, Lightning Studio deployment |
| **Graphn AI** | Multi-step pipeline orchestration with tool selection and structured outputs |
| **Impact** | Democratizes multi-omics analysis for researchers without bioinformatics expertise |

---

*Lightning AI & Graphn AI Hackathon · [Lightning.AI](https://lightning.ai/)*
