"""Daytona sandbox backend for bioinformatics tool execution."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any


class DaytonaToolBackend:
    """Run argv commands inside a reusable Daytona sandbox."""

    _daytona: Any | None = None
    _sandbox: Any | None = None
    _remote_root: str | None = None

    @classmethod
    def enabled(cls) -> bool:
        if os.environ.get("DAYTONA_DISABLE", "").lower() in ("1", "true", "yes"):
            return False
        if os.environ.get("DAYTONA_USE_SANDBOX", "").lower() in ("1", "true", "yes"):
            return bool(os.environ.get("DAYTONA_API_KEY"))
        return bool(os.environ.get("DAYTONA_API_KEY"))

    @classmethod
    def get_sandbox(cls):
        if cls._sandbox is not None:
            return cls._sandbox
        from daytona import Daytona

        cls._daytona = Daytona()
        cls._sandbox = cls._daytona.create()
        cls._remote_root = f"{cls._sandbox.get_work_dir().rstrip('/')}/annotatex"
        cls._sandbox.fs.create_folder(cls._remote_root, "755")
        return cls._sandbox

    @classmethod
    def sync_workdir(cls, local_dir: Path) -> str:
        sandbox = cls.get_sandbox()
        remote_root = cls._remote_root or sandbox.get_work_dir()
        uploads: list[tuple[str, bytes]] = []
        for path in Path(local_dir).rglob("*"):
            if path.is_file():
                rel = path.relative_to(local_dir).as_posix()
                uploads.append((f"{remote_root}/{rel}", path.read_bytes()))
        if uploads:
            sandbox.fs.upload_files(uploads)
        return remote_root

    @classmethod
    def run(cls, command: list[str], local_work_dir: Path, timeout: int) -> tuple[int, str, str]:
        sandbox = cls.get_sandbox()
        remote_root = cls.sync_workdir(local_work_dir)
        cmd = " ".join(shlex.quote(part) for part in command)
        response = sandbox.process.exec(cmd, cwd=remote_root, timeout=timeout)
        output = (response.result or "").strip()
        exit_code = int(getattr(response, "exit_code", 1) or 0)
        return exit_code, output, ""

    @classmethod
    def cleanup(cls) -> None:
        if cls._sandbox is not None:
            try:
                cls._sandbox.delete()
            except Exception:
                pass
        cls._sandbox = None
        cls._daytona = None
        cls._remote_root = None
