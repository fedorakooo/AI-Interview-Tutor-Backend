from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

from shared_models.question_bank.models import CodingRunRequest, CodingRunResult

SUPPORTED = {"python", "javascript"}


async def run_code(request: CodingRunRequest) -> CodingRunResult:
    language = request.language.lower().strip()
    if language not in SUPPORTED:
        return CodingRunResult(
            status="unsupported",
            message=f"Language '{language}' is not supported in the local sandbox. Use python or javascript.",
        )

    suffix = ".py" if language == "python" else ".js"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"main{suffix}"
        path.write_text(request.source_code, encoding="utf-8")
        cmd = ["python3", str(path)] if language == "python" else ["node", str(path)]
        started = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(input=request.stdin.encode("utf-8")),
                timeout=max(request.time_limit_ms / 1000.0, 0.5),
            )
        except TimeoutError:
            return CodingRunResult(status="timeout", message="Execution timed out", exit_code=-1)
        except FileNotFoundError:
            return CodingRunResult(status="error", message=f"Runtime for {language} is not installed")
        runtime_ms = int((time.perf_counter() - started) * 1000)
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        exit_code = proc.returncode or 0
        passed = None
        if request.expected_stdout is not None:
            passed = stdout.strip() == request.expected_stdout.strip()
        return CodingRunResult(
            status="ok" if exit_code == 0 else "runtime_error",
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            passed=passed,
            runtime_ms=runtime_ms,
        )
