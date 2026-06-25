"""Subprocess runner for bioinformatics tools with structured logging."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from cubiczan_resilience import resilient

from annotatex.pipeline.tools.daytona_backend import DaytonaToolBackend


@dataclass
class StepResult:
    tool: str
    command: str
    status: str  # completed | failed | skipped
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    outputs: list[str] = field(default_factory=list)
    error: str | None = None


class ToolRunner:
    def __init__(self, work_dir: Path, timeout: int = 600, per_tool_timeout: int = 300):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        # Per-tool ceiling so a single tool can't consume the whole global budget.
        self.per_tool_timeout = min(per_tool_timeout, timeout)
        self.steps: list[StepResult] = []

    @resilient(timeout=300, max_attempts=3)
    def _invoke(self, command: list[str], timeout: int) -> subprocess.CompletedProcess:
        """Run the subprocess once; raises on timeout so @resilient retries with backoff."""
        if DaytonaToolBackend.enabled():
            exit_code, stdout, stderr = DaytonaToolBackend.run(command, self.work_dir, timeout)
            return subprocess.CompletedProcess(command, exit_code, stdout, stderr)
        return subprocess.run(
            command,
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def run(self, tool: str, command: list[str], outputs: list[Path] | None = None) -> StepResult:
        start = time.time()
        log_path = self.work_dir / f"{tool}.log"
        cmd_str = " ".join(command)

        try:
            proc = self._invoke(command, self.per_tool_timeout)
            log_path.write_text(f"$ {cmd_str}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}")
            status = "completed" if proc.returncode == 0 else "failed"
            result = StepResult(
                tool=tool,
                command=cmd_str,
                status=status,
                duration_seconds=round(time.time() - start, 2),
                stdout=proc.stdout[-4000:],
                stderr=proc.stderr[-4000:],
                outputs=[str(p) for p in (outputs or []) if Path(p).exists()],
                error=None if proc.returncode == 0 else proc.stderr[-500:],
            )
        except subprocess.TimeoutExpired as exc:
            result = StepResult(
                tool=tool,
                command=cmd_str,
                status="failed",
                duration_seconds=round(time.time() - start, 2),
                error=f"Timeout after {self.per_tool_timeout}s (per-tool ceiling): {exc}",
            )
        except FileNotFoundError:
            result = StepResult(
                tool=tool,
                command=cmd_str,
                status="skipped",
                duration_seconds=0,
                error=f"Command not found: {command[0]}",
            )

        self.steps.append(result)
        return result

    def skip(self, tool: str, reason: str) -> StepResult:
        result = StepResult(tool=tool, command="", status="skipped", duration_seconds=0, error=reason)
        self.steps.append(result)
        return result

    def summary(self) -> dict:
        return {
            "total_steps": len(self.steps),
            "completed": sum(1 for s in self.steps if s.status == "completed"),
            "failed": sum(1 for s in self.steps if s.status == "failed"),
            "skipped": sum(1 for s in self.steps if s.status == "skipped"),
            "steps": [
                {
                    "tool": s.tool,
                    "status": s.status,
                    "duration_seconds": s.duration_seconds,
                    "command": s.command,
                    "outputs": s.outputs,
                    "error": s.error,
                }
                for s in self.steps
            ],
        }
