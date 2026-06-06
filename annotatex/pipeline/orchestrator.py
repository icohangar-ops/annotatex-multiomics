"""End-to-end pipeline orchestrator using PyTorch Lightning inference."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from annotatex.data.datamodule import MultiOmicsDataModule
from annotatex.data.generator import GO_TERMS
from annotatex.models.annotatex import AnnotateXModule
from annotatex.pipeline.detector import detect_data_type
from annotatex.pipeline.qc import run_qc
from annotatex.pipeline.reporter import generate_report
from annotatex.pipeline.tools.bio_pipeline import BioPipeline

TOOL_MATRIX = {
    "rna-seq": ["fastqc", "pydeseq2", "annotatex-lightning"],
    "chip-seq": ["fastqc", "bwa", "macs2", "annotatex-lightning"],
    "wgs": ["fastqc", "samtools", "annotatex-lightning"],
    "scrna-seq": ["fastqc", "annotatex-lightning"],
}


class PipelineOrchestrator:
    def __init__(self, model_path: str | Path | None = None, output_dir: str | Path = "results"):
        self.model_path = Path(model_path) if model_path else Path("checkpoints/annotatex-best.ckpt")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        data_path: str | Path,
        data_type: str | None = None,
        dry_run: bool = False,
        skip_qc: bool = False,
        skip_bio: bool = False,
        max_genes: int | None = None,
    ) -> dict:
        start = time.time()
        data_path = Path(data_path)
        run_id = f"pipeline_{int(start)}"
        run_dir = self.output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        detection = detect_data_type(data_path)
        resolved_type = data_type or detection["data_type"]
        tools = TOOL_MATRIX.get(resolved_type, TOOL_MATRIX["rna-seq"])

        plan = {
            "run_id": run_id,
            "input": str(data_path),
            "data_type": resolved_type,
            "detection": detection,
            "tools": tools,
            "dry_run": dry_run,
        }

        if dry_run:
            plan["status"] = "dry_run"
            plan["message"] = f"Would run: {' → '.join(tools)}"
            self._save_json(run_dir / "plan.json", plan)
            return plan

        bio_result = {"status": "skipped", "steps": []}
        if not skip_bio:
            bio = BioPipeline(run_dir / "bio")
            bio_result = bio.execute(data_path, resolved_type)

        expression_path = bio_result.get("expression_path")
        if expression_path and Path(expression_path).exists():
            expression = pd.read_csv(expression_path)
        else:
            raise RuntimeError("Bioinformatics pipeline did not produce an expression matrix.")

        if max_genes:
            expression = expression.head(max_genes)

        qc_result = {"status": "skipped"} if skip_qc else run_qc(expression_path, resolved_type)
        tool_qc = bio_result.get("tool_qc", {})
        if tool_qc.get("checks"):
            qc_result["tool_qc"] = tool_qc

        plan["bio_pipeline"] = bio_result
        plan["qc"] = qc_result

        annotations = self._run_ml_inference(expression, run_dir)
        expression.to_csv(run_dir / "expression.csv", index=False)
        annotations_export = annotations.copy()
        annotations_export["go_terms"] = annotations_export["go_terms"].apply(json.dumps)
        annotations_export.to_csv(run_dir / "annotations.csv", index=False)

        report_paths = generate_report(
            expression=expression,
            annotations=annotations,
            qc=qc_result,
            detection=detection,
            bio_pipeline=bio_result,
            output_dir=run_dir,
        )

        de_count = int((expression["padj"] < 0.05).sum()) if "padj" in expression.columns else 0
        plan.update(
            {
                "status": "completed",
                "duration_seconds": round(time.time() - start, 2),
                "n_genes": len(expression),
                "n_de_genes": de_count,
                "qc_status": qc_result.get("status"),
                "report_html": str(report_paths["html"]),
                "report_json": str(report_paths["json"]),
            }
        )
        self._save_json(run_dir / "results.json", plan)
        return plan

    def _run_ml_inference(self, expression: pd.DataFrame, run_dir: Path) -> pd.DataFrame:
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model checkpoint not found at {self.model_path}. Run `python train.py` first."
            )

        tmp_dir = run_dir / "_inference"
        tmp_dir.mkdir(exist_ok=True)
        expression.to_csv(tmp_dir / "expression.csv", index=False)

        placeholder = pd.DataFrame({"gene": expression["gene"], "description": "", **{t: 0 for t in GO_TERMS}})
        placeholder.to_csv(tmp_dir / "annotations.csv", index=False)

        dm = MultiOmicsDataModule(data_dir=tmp_dir, batch_size=256)
        dm.setup("predict")

        model = AnnotateXModule.load_from_checkpoint(self.model_path)
        model.eval()
        device = next(model.parameters()).device

        features = dm.transform_features(expression).to(device)
        preds = model.predict_with_confidence(features)

        rows = []
        for i, gene in enumerate(expression["gene"].tolist()):
            go_hits = [
                {
                    "term": term,
                    "probability": float(preds["go_probs"][i, j].cpu()),
                    "confidence": float(preds["go_confidence"][i, j].cpu()),
                }
                for j, term in enumerate(GO_TERMS)
                if float(preds["go_probs"][i, j].cpu()) >= 0.3
            ]
            go_hits.sort(key=lambda x: x["confidence"], reverse=True)

            rows.append(
                {
                    "gene": gene,
                    "de_probability": float(preds["de_prob"][i].cpu()),
                    "de_confidence": float(preds["de_confidence"][i].cpu()),
                    "predicted_de": bool(preds["de_prob"][i].cpu() >= 0.5),
                    "go_terms": go_hits,
                    "top_pathway": go_hits[0]["term"] if go_hits else "unknown",
                    "human_review": float(preds["de_confidence"][i].cpu()) < 0.6,
                    "annotation": _build_annotation(gene, go_hits, expression.iloc[i]),
                }
            )

        return pd.DataFrame(rows)

    @staticmethod
    def _save_json(path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2, default=str))


def _build_annotation(gene: str, go_hits: list[dict], row: pd.Series) -> str:
    lfc = row.get("log2FoldChange", row.get("log2foldchange", 0))
    padj = row.get("padj", 1.0)
    direction = "upregulated" if lfc > 0 else "downregulated"

    if go_hits:
        pathways = ", ".join(h["term"].replace("_", " ") for h in go_hits[:3])
        return (
            f"{gene} is {direction} (log2FC={lfc:.2f}, padj={padj:.2e}). "
            f"ML model associates it with {pathways}."
        )
    return f"{gene}: {direction} (log2FC={lfc:.2f}, padj={padj:.2e}). No strong pathway association."
