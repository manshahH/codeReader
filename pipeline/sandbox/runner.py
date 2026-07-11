"""Sandbox execution runner: runs untrusted Python in an isolated container.

Isolation: --network=none, read-only rootfs, 128MB memory, 0.5 CPU, all
capabilities dropped, non-root user, no host env vars propagated (docker run
does not inherit the caller's environment unless -e/--env-file is passed, and
this module never passes either). Runs as a sibling container over the local
or remote (SANDBOX_HOST) Docker socket -- never in-process, per invariant #7
(sandbox code is hostile).

Code delivery is via stdin (D-57), not a bind mount: `docker run -i ... python
-I -B -` reads the candidate straight from the subprocess pipe. A bind mount
(`-v <tmp_path>:/sandbox/code.py`) only works when <tmp_path> is visible to
the daemon actually running the container; when the caller itself runs inside
a container (a sibling container setup over a mounted docker.sock -- the real
pipeline deployment), the caller's temp path is not host-visible, so the host
daemon silently creates an empty directory at the mount target instead of
failing. Every candidate then "fails" with can't-find-__main__ and empty
captured_stdout, indistinguishable from a real gate rejection. Piping via
stdin has no path to resolve, so it is correct identically whether the caller
is on the host or nested in a container.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
import uuid
from pathlib import Path

from pipeline.config import get_pipeline_settings

IMAGE_NAME = "codereader-sandbox:latest"
DOCKERFILE_DIR = Path(__file__).resolve().parent
DEFAULT_TIMEOUT_S = 5.0
HOST_TIMEOUT_BUFFER_S = 5.0
TIMEOUT_EXIT_CODE = 124
# D-57: proves the delivery mechanism actually reaches the interpreter before
# a batch trusts any real rejection. Unlikely enough not to collide with a
# candidate's own output.
_CANARY_TOKEN = "codereader-sandbox-canary-3f9a21c6"
_sandbox_verified = False


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


def _docker_run_cmd(container_name: str, internal_timeout: int) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-i",
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
        IMAGE_NAME,
        "timeout",
        "-k",
        "1",
        str(internal_timeout),
        "python",
        "-I",
        "-B",
        "-",
    ]


def _run_container(code: str, timeout_s: float) -> SandboxResult:
    container_name = f"codereader-sbx-{uuid.uuid4().hex}"
    internal_timeout = max(1, int(timeout_s))
    cmd = _docker_run_cmd(container_name, internal_timeout)
    try:
        proc = subprocess.run(
            cmd,
            input=code,
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


def run_python(code: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> SandboxResult:
    """Execute `code` as a standalone script inside the sandbox container.

    Returns captured stdout/stderr/exit_code. Never raises on the candidate
    code's own failures (AssertionError, exceptions, timeouts) -- those are
    reported in the result for the gate to interpret.
    """
    ensure_image_built()
    return _run_container(code, timeout_s)


def verify_sandbox_available(*, force: bool = False) -> None:
    """Prove the sandbox actually executes code before a batch trusts it.

    D-57: a bind-mount delivery bug made every candidate "fail" with empty
    captured_stdout whenever the caller ran inside a container -- silently,
    with no error, indistinguishable from a real gate rejection. This canary
    runs the exact same delivery path (`_run_container`) as every real
    candidate and raises loud instead of letting a whole batch silently
    reject everything. Cached per process after the first success (`force`
    re-runs it); call at the top of a batch, not per-candidate.
    """
    global _sandbox_verified
    if _sandbox_verified and not force:
        return
    ensure_image_built()
    result = _run_container(f"print({_CANARY_TOKEN!r})", DEFAULT_TIMEOUT_S)
    if result.stdout.strip() != _CANARY_TOKEN:
        raise SandboxUnavailableError(
            "sandbox canary check failed: the sandbox is not actually executing "
            f"code (expected stdout {_CANARY_TOKEN!r}, got stdout={result.stdout!r} "
            f"stderr={result.stderr!r} exit_code={result.exit_code}). Refusing to "
            "run a batch that would silently reject every candidate."
        )
    _sandbox_verified = True
