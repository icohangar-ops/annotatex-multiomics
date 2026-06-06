"""Synthetic multi-omics dataset generator for training and demos."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

GO_TERMS = [
    "apoptosis",
    "cell_cycle",
    "p53_signaling",
    "immune_response",
    "metabolism",
    "DNA_repair",
    "angiogenesis",
    "inflammation",
    "oxidative_stress",
    "transcription_regulation",
]

GENE_FUNCTIONS = {
    "TP53": ("Tumor suppressor regulating cell cycle and apoptosis.", ["apoptosis", "cell_cycle", "p53_signaling"]),
    "BCL2": ("Anti-apoptotic regulator; blocks mitochondrial outer membrane permeabilization.", ["apoptosis"]),
    "CDKN1A": ("Cyclin-dependent kinase inhibitor (p21); mediates p53-dependent cell cycle arrest.", ["cell_cycle", "p53_signaling"]),
    "MYC": ("Oncogenic transcription factor driving proliferation and metabolism.", ["cell_cycle", "metabolism", "transcription_regulation"]),
    "BRCA1": ("DNA repair and homologous recombination.", ["DNA_repair", "cell_cycle"]),
    "VEGFA": ("Vascular endothelial growth factor; promotes angiogenesis.", ["angiogenesis"]),
    "IL6": ("Pro-inflammatory cytokine.", ["inflammation", "immune_response"]),
    "SOD2": ("Mitochondrial antioxidant enzyme.", ["oxidative_stress", "metabolism"]),
    "EGFR": ("Receptor tyrosine kinase; drives proliferation signaling.", ["cell_cycle", "transcription_regulation"]),
    "PTEN": ("Tumor suppressor phosphatase antagonizing PI3K/AKT.", ["apoptosis", "metabolism"]),
}


def _make_gene_name(idx: int) -> str:
    if idx < len(GENE_FUNCTIONS):
        return list(GENE_FUNCTIONS.keys())[idx]
    return f"GENE_{idx:04d}"


def generate_synthetic_dataset(
    n_genes: int = 2000,
    n_significant: int = 400,
    seed: int = 42,
    output_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate synthetic DESeq2-style expression results with GO labels."""
    rng = np.random.default_rng(seed)
    output_dir = Path(output_dir) if output_dir else None

    genes = [_make_gene_name(i) for i in range(n_genes)]
    base_mean = rng.lognormal(mean=6, sigma=1.5, size=n_genes)
    log2fc = rng.normal(0, 0.4, size=n_genes)

    sig_idx = rng.choice(n_genes, size=n_significant, replace=False)
    log2fc[sig_idx] = rng.choice([-1, 1], size=n_significant) * rng.uniform(1.0, 3.5, size=n_significant)

    lfc_se = rng.uniform(0.08, 0.35, size=n_genes)
    stat = log2fc / lfc_se
    pvalue = 2 * (1 - _normal_cdf(np.abs(stat)))
    padj = np.minimum(pvalue * n_genes * 0.05, 1.0)
    padj = np.clip(padj, 1e-300, 1.0)

    expression = pd.DataFrame(
        {
            "gene": genes,
            "baseMean": base_mean,
            "log2FoldChange": log2fc,
            "lfcSE": lfc_se,
            "stat": stat,
            "pvalue": pvalue,
            "padj": padj,
            "is_de": (padj < 0.05).astype(int),
        }
    )

    go_labels = []
    for i, gene in enumerate(genes):
        if gene in GENE_FUNCTIONS:
            desc, terms = GENE_FUNCTIONS[gene]
        else:
            n_terms = rng.integers(0, 3)
            terms = list(rng.choice(GO_TERMS, size=n_terms, replace=False)) if n_terms else []
            desc = f"Predicted function for {gene} based on expression profile."

        label_vec = {term: int(term in terms) for term in GO_TERMS}
        go_labels.append(
            {
                "gene": gene,
                "description": desc,
                **label_vec,
            }
        )

    annotations = pd.DataFrame(go_labels)

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        expression.to_csv(output_dir / "expression.csv", index=False)
        annotations.to_csv(output_dir / "annotations.csv", index=False)
        metadata = {
            "n_genes": n_genes,
            "n_significant": int((expression["padj"] < 0.05).sum()),
            "omics_type": "rna-seq",
            "seed": seed,
        }
        (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    return expression, annotations


def _normal_cdf(x: np.ndarray) -> np.ndarray:
    return 0.5 * (1 + np.vectorize(_erf)(x / np.sqrt(2)))


def _erf(x: float) -> float:
    # Abramowitz and Stegun approximation
    sign = 1 if x >= 0 else -1
    x = abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return sign * y
