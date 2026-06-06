"""Lightning DataModule for multi-omics gene annotation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import torch
from lightning.pytorch import LightningDataModule
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset

from annotatex.data.generator import GO_TERMS


FEATURE_COLS = ["baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj"]


class GeneDataset(Dataset):
    def __init__(self, features: torch.Tensor, de_labels: torch.Tensor, go_labels: torch.Tensor):
        self.features = features
        self.de_labels = de_labels
        self.go_labels = go_labels

    def __len__(self) -> int:
        return len(self.features)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        return {
            "features": self.features[idx],
            "de_label": self.de_labels[idx],
            "go_labels": self.go_labels[idx],
        }


class MultiOmicsDataModule(LightningDataModule):
    def __init__(
        self,
        data_dir: str | Path,
        batch_size: int = 64,
        num_workers: int = 0,
        val_split: float = 0.15,
        test_split: float = 0.15,
        seed: int = 42,
    ):
        super().__init__()
        self.data_dir = Path(data_dir)
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.val_split = val_split
        self.test_split = test_split
        self.seed = seed
        self.scaler = StandardScaler()
        self.n_go_terms = len(GO_TERMS)
        self.go_terms = GO_TERMS

    def setup(self, stage: str | None = None) -> None:
        expression = pd.read_csv(self.data_dir / "expression.csv")
        annotations = pd.read_csv(self.data_dir / "annotations.csv")
        merged = expression.merge(annotations, on="gene")

        features = merged[FEATURE_COLS].values.astype("float32")
        de_labels = merged["is_de"].values.astype("float32")
        go_labels = merged[self.go_terms].values.astype("float32")

        features = self.scaler.fit_transform(features).astype("float32")

        idx = merged.index.to_numpy()
        train_idx, test_idx = train_test_split(idx, test_size=self.test_split, random_state=self.seed, stratify=de_labels)
        train_de = de_labels[train_idx]
        val_ratio = self.val_split / (1 - self.test_split)
        train_idx, val_idx = train_test_split(train_idx, test_size=val_ratio, random_state=self.seed, stratify=train_de)

        self.train_dataset = GeneDataset(
            torch.tensor(features[train_idx]),
            torch.tensor(de_labels[train_idx]),
            torch.tensor(go_labels[train_idx]),
        )
        self.val_dataset = GeneDataset(
            torch.tensor(features[val_idx]),
            torch.tensor(de_labels[val_idx]),
            torch.tensor(go_labels[val_idx]),
        )
        self.test_dataset = GeneDataset(
            torch.tensor(features[test_idx]),
            torch.tensor(de_labels[test_idx]),
            torch.tensor(go_labels[test_idx]),
        )
        self._full_features = features
        self._full_genes = merged["gene"].tolist()
        self._full_descriptions = merged["description"].tolist()

    def train_dataloader(self) -> DataLoader:
        return DataLoader(self.train_dataset, batch_size=self.batch_size, shuffle=True, num_workers=self.num_workers)

    def val_dataloader(self) -> DataLoader:
        return DataLoader(self.val_dataset, batch_size=self.batch_size, num_workers=self.num_workers)

    def test_dataloader(self) -> DataLoader:
        return DataLoader(self.test_dataset, batch_size=self.batch_size, num_workers=self.num_workers)

    def transform_features(self, df: pd.DataFrame) -> torch.Tensor:
        features = df[FEATURE_COLS].values.astype("float32")
        return torch.tensor(self.scaler.transform(features))
