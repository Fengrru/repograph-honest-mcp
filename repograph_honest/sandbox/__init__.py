"""
Sandboxed code execution for RepoGraph-Honest.

Executes untrusted code in a fresh Python subprocess with resource limits on
POSIX systems. On Windows, resource limits are not enforced by the OS in this
implementation; execution still runs in an isolated temporary directory and is
bounded by a strict timeout.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    output: str = ""
    error: str = ""
    error_type: str = ""
    runtime_seconds: float = 0.0
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "output": self.output or self.stdout,
            "error": self.error or self.stderr,
            "error_type": self.error_type,
            "runtime_seconds": self.runtime_seconds,
            **self.details,
        }


class SandboxExecutor:
    """Execute Python code snippets in a restricted subprocess."""

    def __init__(self, timeout: int = 10, memory_mb: Optional[int] = None):
        self.timeout = timeout
        self.memory_mb = memory_mb

    def execute(
        self,
        code: str,
        prelude: str = "",
        known_names: Optional[set[str]] = None,
    ) -> ExecutionResult:
        """Run *code* in a fresh Python interpreter and return the result."""
        known_names = known_names or set()
        start = time.perf_counter()

        with tempfile.TemporaryDirectory(prefix="repograph_sandbox_") as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            full_code = f"{prelude}\n{code}\n"
            script_path.write_text(full_code, encoding="utf-8")

            env = os.environ.copy()
            env["PYTHONPATH"] = ""
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            try:
                proc = subprocess.run(
                    [sys.executable, "-u", str(script_path)],
                    cwd=tmpdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    preexec_fn=self._get_preexec_fn(),
                )
                runtime = time.perf_counter() - start
                stdout = proc.stdout or ""
                stderr = proc.stderr or ""
                success = proc.returncode == 0
                err_text = stderr[:50_000] if not success else ""
                error_type = ""
                if not success and err_text:
                    m = re.search(r"^(\w+Error|\w+Exception)", err_text, re.MULTILINE)
                    if m:
                        error_type = m.group(1)
                return ExecutionResult(
                    success=success,
                    stdout=stdout[:50_000],
                    stderr=stderr[:50_000],
                    output=stdout[:50_000],
                    error=err_text,
                    error_type=error_type,
                    runtime_seconds=round(runtime, 3),
                    details={"returncode": proc.returncode, "known_names": sorted(known_names)},
                )
            except subprocess.TimeoutExpired as e:
                runtime = time.perf_counter() - start
                return ExecutionResult(
                    success=False,
                    error=f"Execution timed out after {self.timeout}s",
                    stderr=e.stderr or "",
                    runtime_seconds=round(runtime, 3),
                    details={"timeout": True},
                )
            except Exception as e:  # noqa: BLE001
                runtime = time.perf_counter() - start
                return ExecutionResult(
                    success=False,
                    error=f"Sandbox failed: {e}",
                    runtime_seconds=round(runtime, 3),
                )

    def _get_preexec_fn(self):
        """Return a POSIX preexec_fn that sets resource limits, if available."""
        if sys.platform == "win32" or self.memory_mb is None:
            return None
        try:
            import resource

            def limit_resources():
                max_bytes = self.memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))

            return limit_resources
        except Exception:  # noqa: BLE001
            return None

    def validate_snippet(self, code: str, known_names: set[str]) -> ExecutionResult:
        """Quickly run a snippet to see if it raises a NameError for unknown symbols."""
        return self.execute(code=code, known_names=known_names)
