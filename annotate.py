#!/usr/bin/env python3
"""Generate annotated report from existing pipeline results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from annotatex.pipeline.reporter import generate_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate AnnotateX HTML/JSON report")
    parser.add_argument("--results", required=True, help="Pipeline results directory")
    parser.add_argument("--output", default=None, help="Output directory (defaults to --results)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results_dir = Path(args.results)
    output_dir = Path(args.output) if args.output else results_dir

    expression = pd.read_csv(results_dir / "expression.csv")
    annotations = pd.read_csv(results_dir / "annotations.csv")

    results_json = results_dir / "results.json"
    detection = {"data_type": "rna-seq", "reason": "from results"}
    qc = {"status": "unknown", "checks": []}
    if results_json.exists():
        meta = json.loads(results_json.read_text())
        detection = meta.get("detection", detection)
        qc = meta.get("qc", qc)

    paths = generate_report(expression, annotations, qc, detection, output_dir)
    print(json.dumps({k: str(v) for k, v in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
