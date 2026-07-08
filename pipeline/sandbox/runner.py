"""Sandbox execution runner: runs untrusted Python in an isolated container.

Isolation: --network=none, read-only rootfs, 128MB memory, 0.5 CPU, all
capabilities dropped, non-root user, no host env vars propagated (docker run
does not inherit the caller's environment unless -e/--env-file is passed, and
this module never passes either). Runs as a sibling container over the local
or remote (SANDBOX_HOST) Docker socket -- never in-process, per invariant #7
(sandbox code is hostile).
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from pipeline.config import get_pipeline_settings

IMAGE_NAME = "codereader-sandbox:latest"
DOCKERFILE_DIR = Path(__file__).resolve().parent
DEFAULT_TIMEOUT_S = 5.0
HOST_TIMEOUT_BUFFER_S = 5.0
TIMEOUT_EXIT_CODE = 124


@dataclasses.dataclass(frozen=True)
class SandboxResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool


class SandboxUnavailableError(RuntimeError):
    """Raised when the docker CLI or the sandbox image is unusable."""


def _docker_env() -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", "")}
    sandbox_host = get_pipeline_settings().SANDBOX_HOST
    if sandbox_host:
        env["DOCKER_HOST"] = sandbox_host
    return env


def ensure_image_built(*, force: bool = False) -> None:
    if not force:
        probe = subprocess.run(
            ["docker", "image", "inspect", IMAGE_NAME],
            capture_output=True,
            text=True,
            env=_docker_env(),
            check=False,
        )
        if probe.returncode == 0:
            return
    build = subprocess.run(
        ["docker", "build", "-t", IMAGE_NAME, str(DOCKERFILE_DIR)],
        capture_output=True,
        text=True,
        env=_docker_env(),
        check=False,
    )
    if build.returncode != 0:
        raise SandboxUnavailableError(f"failed to build sandbox image:\n{build.stderr}")


def run_python(code: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> SandboxResult:
    """Execute `code` as a standalone script inside the sandbox container.

    Returns captured stdout/stderr/exit_code. Never raises on the candidate
    code's own failures (AssertionError, exceptions, timeouts) -- those are
    reported in the result for the gate to interpret.
    """
    ensure_image_built()
    container_name = f"codereader-sbx-{uuid.uuid4().hex}"
    with tempfile.TemporaryDirectory() as tmp_dir:
        code_path = Path(tmp_dir) / "code.py"
        code_path.write_text(code, encoding="utf-8", newline="\n")
        code_path.chmod(0o644)

        internal_timeout = max(1, int(timeout_s))
        cmd = [
            "docker",
            "run",
            "--rm",
            f"--name={container_name}",
            "--network=none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,size=16m",
            "--memory=128m",
            "--memory-swap=128m",
            "--cpus=0.5",
            "--pids-limit=64",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "-v",
            f"{code_path}:/sandbox/code.py:ro",
            IMAGE_NAME,
            "timeout",
            "-k",
            "1",
            str(internal_timeout),
            "python",
            "-I",
            "-B",
            "/sandbox/code.py",
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=_docker_env(),
                timeout=timeout_s + HOST_TIMEOUT_BUFFER_S,
                check=False,
            )
            return SandboxResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                timed_out=proc.returncode == TIMEOUT_EXIT_CODE,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return SandboxResult(exit_code=None, stdout=stdout, stderr=stderr, timed_out=True)
        finally:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                text=True,
                env=_docker_env(),
                check=False,
            )
