"""PyTorch Lightning module for gene DE classification and GO annotation."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from lightning.pytorch import LightningModule
from torchmetrics.classification import (
    BinaryAccuracy,
    BinaryF1Score,
    MultilabelF1Score,
)

from annotatex.data.generator import GO_TERMS


class AnnotateXNetwork(nn.Module):
    def __init__(self, input_dim: int = 6, hidden_dim: int = 128, n_go_terms: int = len(GO_TERMS), dropout: float = 0.2):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.de_head = nn.Linear(hidden_dim, 1)
        self.go_head = nn.Linear(hidden_dim, n_go_terms)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.encoder(x)
        return self.de_head(h).squeeze(-1), self.go_head(h)


class AnnotateXModule(LightningModule):
    def __init__(
        self,
        input_dim: int = 6,
        hidden_dim: int = 128,
        n_go_terms: int = len(GO_TERMS),
        lr: float = 1e-3,
        de_weight: float = 1.0,
        go_weight: float = 2.0,
        dropout: float = 0.2,
        mc_samples: int = 20,
    ):
        super().__init__()
        self.save_hyperparameters()
        self.network = AnnotateXNetwork(input_dim, hidden_dim, n_go_terms, dropout)
        self.de_acc = BinaryAccuracy()
        self.de_f1 = BinaryF1Score()
        self.go_f1 = MultilabelF1Score(num_labels=n_go_terms, average="macro")
        self.go_terms = GO_TERMS

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.network(x)

    def _shared_step(self, batch: dict[str, torch.Tensor], stage: str) -> torch.Tensor:
        features = batch["features"]
        de_logits, go_logits = self(features)

        de_loss = F.binary_cross_entropy_with_logits(de_logits, batch["de_label"])
        go_loss = F.binary_cross_entropy_with_logits(go_logits, batch["go_labels"])
        loss = self.hparams.de_weight * de_loss + self.hparams.go_weight * go_loss

        de_probs = torch.sigmoid(de_logits)
        go_probs = torch.sigmoid(go_logits)
        de_preds = (de_probs >= 0.5).int()
        go_preds = (go_probs >= 0.5).int()

        self.de_acc(de_preds, batch["de_label"].int())
        self.de_f1(de_preds, batch["de_label"].int())
        self.go_f1(go_preds, batch["go_labels"].int())

        self.log(f"{stage}/loss", loss, prog_bar=True, on_step=False, on_epoch=True)
        self.log(f"{stage}/de_loss", de_loss, on_step=False, on_epoch=True)
        self.log(f"{stage}/go_loss", go_loss, on_step=False, on_epoch=True)
        self.log(f"{stage}/de_acc", self.de_acc, prog_bar=True, on_step=False, on_epoch=True)
        self.log(f"{stage}/de_f1", self.de_f1, on_step=False, on_epoch=True)
        self.log(f"{stage}/go_f1", self.go_f1, on_step=False, on_epoch=True)
        return loss

    def training_step(self, batch: dict[str, torch.Tensor], batch_idx: int) -> torch.Tensor:
        return self._shared_step(batch, "train")

    def validation_step(self, batch: dict[str, torch.Tensor], batch_idx: int) -> torch.Tensor:
        return self._shared_step(batch, "val")

    def test_step(self, batch: dict[str, torch.Tensor], batch_idx: int) -> torch.Tensor:
        return self._shared_step(batch, "test")

    def configure_optimizers(self):
        optimizer = torch.optim.AdamW(self.parameters(), lr=self.hparams.lr, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=3)
        return {"optimizer": optimizer, "lr_scheduler": {"scheduler": scheduler, "monitor": "val/loss"}}

    @torch.no_grad()
    def predict_with_confidence(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        """Monte Carlo dropout inference for calibrated confidence scores."""
        self.train()  # enable dropout
        de_samples, go_samples = [], []
        for _ in range(self.hparams.mc_samples):
            de_logits, go_logits = self(features)
            de_samples.append(torch.sigmoid(de_logits))
            go_samples.append(torch.sigmoid(go_logits))

        de_stack = torch.stack(de_samples)
        go_stack = torch.stack(go_samples)
        de_mean = de_stack.mean(0)
        go_mean = go_stack.mean(0)
        de_std = de_stack.std(0)
        go_std = go_stack.std(0)

        # Higher confidence when prediction is decisive and stable across MC samples
        de_confidence = (1 - de_std) * torch.where(de_mean > 0.5, de_mean, 1 - de_mean)
        go_confidence = (1 - go_std.clamp(max=0.5)) * go_mean

        self.eval()
        return {
            "de_prob": de_mean,
            "de_confidence": de_confidence.clamp(0, 1),
            "go_probs": go_mean,
            "go_confidence": go_confidence.clamp(0, 1),
        }
