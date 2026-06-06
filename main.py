#!/usr/bin/env python3
"""AnnotateX Multi-Omics — Lightning Studio entry point."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    checkpoint = Path("checkpoints/annotatex-best.ckpt")

    if not checkpoint.exists():
        print("Training AnnotateX model...")
        subprocess.check_call([sys.executable, "train.py", "--generate", "--epochs", "8"])

    print("Launching Gradio UI on port 7860...")
    subprocess.check_call([sys.executable, "app.py"])


if __name__ == "__main__":
    main()
