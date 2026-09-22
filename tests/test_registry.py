"""Evidence-matrix tests — tool registry (README Tool Status).

Loads the registry module from its file path (stdlib-only module) so the
registry contract is checkable in any environment.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_registry():
    path = ROOT / "annotatex" / "pipeline" / "tools" / "registry.py"
    spec = importlib.util.spec_from_file_location("annotatex_registry_under_test", path)
    module = importlib.util.module_from_spec(spec)
    # register in sys.modules so dataclass annotation resolution works (3.13+)
    sys.modules["annotatex_registry_under_test"] = module
    spec.loader.exec_module(module)
    return module


registry = _load_registry()


def test_status_report_shape():
    status = registry.get_tool_status()
    assert len(status) == 10
    for row in status:
        assert set(row) == {"name", "category", "available", "install_hint"}


def test_install_hints_present():
    hints = {row["name"]: row["install_hint"] for row in registry.get_tool_status()}
    assert hints["fastqc"] == "conda install -c bioconda fastqc"
    assert hints["samtools"] == "conda install -c bioconda samtools"
    assert hints["featurecounts"] == "conda install -c bioconda subread"
    assert hints["pydeseq2"] == "pip install pydeseq2"
    assert all(hints.values())
