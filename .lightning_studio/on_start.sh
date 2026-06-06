#!/bin/bash
# Launch AnnotateX Gradio UI on Studio start
pip install -q -r requirements.txt 2>/dev/null || true
bash scripts/install_bioinfo.sh 2>/dev/null || true
python main.py
