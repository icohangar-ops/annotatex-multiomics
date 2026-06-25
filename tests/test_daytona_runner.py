"""Tests for Daytona tool backend (no heavy pipeline imports)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(rel_path: str, name: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


daytona_backend = _load_module("annotatex/pipeline/tools/daytona_backend.py", "daytona_backend")
DaytonaToolBackend = daytona_backend.DaytonaToolBackend


class TestDaytonaBackend:
    def setup_method(self):
        DaytonaToolBackend.cleanup()

    def teardown_method(self):
        DaytonaToolBackend.cleanup()

    def test_disabled_without_key(self, monkeypatch):
        monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
        assert DaytonaToolBackend.enabled() is False

    def test_enabled_with_key(self, monkeypatch):
        monkeypatch.setenv("DAYTONA_API_KEY", "test-key")
        assert DaytonaToolBackend.enabled() is True

    def test_disable_flag(self, monkeypatch):
        monkeypatch.setenv("DAYTONA_API_KEY", "test-key")
        monkeypatch.setenv("DAYTONA_DISABLE", "1")
        assert DaytonaToolBackend.enabled() is False
