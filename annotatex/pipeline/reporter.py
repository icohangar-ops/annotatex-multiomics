"""HTML and JSON report generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from jinja2 import Template

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>AnnotateX Report — {{ run_id }}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1a1a2e; }
    h1 { color: #6B46C1; }
    h2 { color: #4338ca; margin-top: 2rem; }
    .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.85rem; }
    .pass, .completed { background: #d1fae5; color: #065f46; }
    .warn { background: #fef3c7; color: #92400e; }
    .fail, .failed { background: #fee2e2; color: #991b1b; }
    .skipped { background: #e5e7eb; color: #374151; }
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
    th, td { border: 1px solid #e5e7eb; padding: 0.5rem 0.75rem; text-align: left; font-size: 0.9rem; }
    th { background: #f3f4f6; }
    .conf-high { color: #059669; font-weight: 600; }
    .conf-low { color: #dc2626; }
    .meta { color: #6b7280; font-size: 0.9rem; }
    code { background: #f3f4f6; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.85rem; }
  </style>
</head>
<body>
  <h1>AnnotateX Multi-Omics Report</h1>
  <p class="meta">Generated {{ timestamp }} · PyTorch Lightning + real bioinformatics tools</p>

  <h2>Summary</h2>
  <ul>
    <li><strong>Data type:</strong> {{ detection.data_type }} — {{ detection.reason }}</li>
    <li><strong>Genes analyzed:</strong> {{ n_genes }}</li>
    <li><strong>DE genes (padj &lt; 0.05):</strong> {{ n_de }}</li>
    <li><strong>QC status:</strong> <span class="badge {{ qc.status }}">{{ qc.status }}</span></li>
    {% if bio_pipeline %}
    <li><strong>Tool steps:</strong> {{ bio_pipeline.completed }}/{{ bio_pipeline.total_steps }} completed</li>
    {% endif %}
  </ul>

  {% if bio_pipeline and bio_pipeline.steps %}
  <h2>Bioinformatics Pipeline</h2>
  <table>
    <tr><th>Tool</th><th>Status</th><th>Duration</th><th>Details</th></tr>
    {% for step in bio_pipeline.steps %}
    <tr>
      <td><code>{{ step.tool }}</code></td>
      <td><span class="badge {{ step.status }}">{{ step.status }}</span></td>
      <td>{{ step.duration_seconds }}s</td>
      <td>{{ step.error or step.command[:120] }}</td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}

  <h2>QC Checks</h2>
  <table>
    <tr><th>Check</th><th>Status</th><th>Detail</th></tr>
    {% for check in qc.checks %}
    <tr>
      <td>{{ check.name }}</td>
      <td>{{ "✓" if check.passed else "✗" }}</td>
      <td>{{ check.detail }}</td>
    </tr>
    {% endfor %}
  </table>

  <h2>Top Annotated Genes</h2>
  <table>
    <tr>
      <th>Gene</th><th>log2FC</th><th>padj</th><th>DE Conf.</th><th>Pathway</th><th>Annotation</th>
    </tr>
    {% for row in top_genes %}
    <tr>
      <td>{{ row.gene }}</td>
      <td>{{ "%.2f"|format(row.log2FoldChange) }}</td>
      <td>{{ "%.2e"|format(row.padj) }}</td>
      <td class="{{ 'conf-high' if row.de_confidence >= 0.7 else 'conf-low' }}">{{ "%.2f"|format(row.de_confidence) }}</td>
      <td>{{ row.top_pathway }}</td>
      <td>{{ row.annotation }}</td>
    </tr>
    {% endfor %}
  </table>

  <p class="meta">AnnotateX v0.3 · Lightning AI & Graphn AI Hackathon</p>
</body>
</html>
"""


def generate_report(
    expression: pd.DataFrame,
    annotations: pd.DataFrame,
    qc: dict,
    detection: dict,
    output_dir: str | Path,
    bio_pipeline: dict | None = None,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    merged = expression.merge(annotations, on="gene", how="left")

    if "padj" in merged.columns:
        top = merged.nsmallest(10, "padj")
    else:
        top = merged.head(10)

    context = {
        "run_id": output_dir.name,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "detection": detection,
        "n_genes": len(expression),
        "n_de": int((expression["padj"] < 0.05).sum()) if "padj" in expression.columns else 0,
        "qc": qc,
        "bio_pipeline": bio_pipeline,
        "top_genes": top.to_dict(orient="records"),
    }

    html_path = output_dir / "report.html"
    html_path.write_text(Template(REPORT_TEMPLATE).render(**context))

    json_path = output_dir / "report.json"
    json_path.write_text(json.dumps(context, indent=2, default=str))

    return {"html": html_path, "json": json_path}
