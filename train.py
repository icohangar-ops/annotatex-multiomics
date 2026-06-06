#!/usr/bin/env python3
"""Train the AnnotateX PyTorch Lightning model."""

from __future__ import annotations

import argparse
from pathlib import Path

import lightning as L
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint

from annotatex.data.datamodule import MultiOmicsDataModule
from annotatex.data.generator import generate_synthetic_dataset
from annotatex.models.annotatex import AnnotateXModule


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train AnnotateX multi-omics annotation model")
    parser.add_argument("--data-dir", type=str, default="data/synthetic", help="Training data directory")
    parser.add_argument("--generate", action="store_true", help="Generate synthetic training data")
    parser.add_argument("--n-genes", type=int, default=3000, help="Genes for synthetic dataset")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--accelerator", type=str, default="auto")
    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)

    if args.generate or not (data_dir / "expression.csv").exists():
        print(f"Generating synthetic dataset ({args.n_genes} genes)...")
        generate_synthetic_dataset(n_genes=args.n_genes, output_dir=data_dir)

    dm = MultiOmicsDataModule(data_dir=data_dir, batch_size=args.batch_size)
    model = AnnotateXModule(hidden_dim=args.hidden_dim, lr=args.lr)

    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_cb = ModelCheckpoint(
        dirpath=checkpoint_dir,
        filename="annotatex-{epoch:02d}-{val/de_f1:.3f}",
        monitor="val/de_f1",
        mode="max",
        save_top_k=1,
    )
    early_stop = EarlyStopping(monitor="val/loss", patience=5, mode="min")

    trainer = L.Trainer(
        max_epochs=args.epochs,
        accelerator=args.accelerator,
        callbacks=[checkpoint_cb, early_stop],
        log_every_n_steps=10,
        enable_progress_bar=True,
    )

    trainer.fit(model, dm)
    trainer.test(model, dm)

    best = checkpoint_cb.best_model_path
    if best:
        import shutil

        dest = checkpoint_dir / "annotatex-best.ckpt"
        shutil.copy(best, dest)
        print(f"\nBest checkpoint saved to {dest}")


if __name__ == "__main__":
    main()
