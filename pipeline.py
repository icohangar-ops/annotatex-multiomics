#!/usr/bin/env python3
"""Run the AnnotateX multi-omics pipeline."""

from __future__ import annotations

import argparse
import json
import sys

from annotatex.pipeline.orchestrator import PipelineOrchestrator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AnnotateX multi-omics pipeline (PyTorch Lightning)")
    parser.add_argument("--data", required=True, help="Input data path (CSV/TSV/FASTQ)")
    parser.add_argument("--type", dest="data_type", default=None, help="Override detected omics type")
    parser.add_argument("--output-dir", default="results", help="Output directory")
    parser.add_argument("--model", default="checkpoints/annotatex-best.ckpt", help="Lightning checkpoint")
    parser.add_argument("--dry-run", action="store_true", help="Show pipeline plan without executing")
    parser.add_argument("--skip-qc", action="store_true")
    parser.add_argument("--skip-bio", action="store_true", help="Skip bioinformatics tools (ML only)")
    parser.add_argument("--max-genes", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    orchestrator = PipelineOrchestrator(model_path=args.model, output_dir=args.output_dir)

    try:
        result = orchestrator.run(
            data_path=args.data,
            data_type=args.data_type,
            dry_run=args.dry_run,
            skip_qc=args.skip_qc,
            skip_bio=args.skip_bio,
            max_genes=args.max_genes,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))
    if args.verbose and result.get("report_html"):
        print(f"\nReport: {result['report_html']}")


if __name__ == "__main__":
    main()
