#!/usr/bin/env bash
# Install bioinformatics tools for AnnotateX pipeline
set -euo pipefail

echo "=== AnnotateX Bioinformatics Tool Installer ==="

if command -v conda &>/dev/null; then
  echo "Installing core bioconda tools..."
  conda install -y -c bioconda -c conda-forge fastqc samtools multiqc 2>/dev/null || true

  echo "Installing aligners (BWA, STAR, subread)..."
  conda install -y -c bioconda bwa star subread 2>/dev/null || true

  echo "Installing macs2 (optional, may fail on some platforms)..."
  conda install -y -c bioconda macs2 2>/dev/null || echo "  macs2 skipped (optional)"
fi

echo "Installing Python bio packages..."
pip install -q pydeseq2 biopython pysam gradio "pandas>=2.1,<3"

# Fix numpy/pandas ABI mismatch after conda updates
pip install -q "numpy>=1.26,<2.4" "pandas>=2.1,<3" 2>/dev/null || true

echo ""
echo "=== Tool Status ==="
python -c "
from annotatex.pipeline.tools.registry import get_tool_status
for t in get_tool_status():
    icon = '✓' if t['available'] else '✗'
    print(f'  [{icon}] {t[\"name\"]:15s} ({t[\"category\"]})')
"

echo ""
echo "Done. Launch UI with: python app.py"
