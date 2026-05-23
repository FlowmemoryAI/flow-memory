"""Optional Docker sandbox backend.

This is a public-alpha isolation seam. It only runs when explicitly enabled and
Docker is available; local sandboxing remains the default.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from flow_memory.action.sandbox_profiles import SandboxProfile
from flow_memory.action.sandbox_receipts import SandboxReceipt
from flow_memory.crypto.hashes import content_hash


class DockerSandboxUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class DockerSandboxConfig:
    image: str = "python:3.12-alpine"
    enabled: bool = False


def docker_available() -> bool:
    return shutil.which("docker") is not None


class DockerSandbox:
    def __init__(self, config: DockerSandboxConfig | None = None) -> None:
        self.config = config or DockerSandboxConfig()

    def run(self, command: tuple[str, ...], profile: SandboxProfile) -> SandboxReceipt:
        if not self.config.enabled:
            raise DockerSandboxUnavailable("Docker sandbox is disabled by default")
        if not docker_available():
            raise DockerSandboxUnavailable("Docker executable is not available")
        errors = profile.validate()
        if errors:
            raise ValueError("invalid sandbox profile: " + "; ".join(errors))
        if profile.requires_approval:
            raise PermissionError("sandbox profile requires approval")
        if not command:
            raise ValueError("command required")

        with tempfile.TemporaryDirectory(prefix="flow-memory-docker-sandbox-") as tmp:
            workdir = Path(tmp)
            docker_command = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none" if profile.network == "deny" else "bridge",
                "--memory",
                f"{profile.memory_limit_mb}m",
                "--cpus",
                str(profile.cpu_limit),
                "--read-only",
                "-v",
                f"{workdir}:/workspace:rw",
                "-w",
                "/workspace",
            ]
            for name in profile.env_allowlist:
                docker_command.extend(["-e", name])
            docker_command.append(self.config.image)
            docker_command.extend(command)
            started = perf_counter()
            completed = subprocess.run(
                docker_command,
                capture_output=True,
                text=True,
                timeout=profile.timeout_seconds,
            )
            output = (completed.stdout + completed.stderr)[: profile.output_size_limit]
            status = "ok" if completed.returncode == 0 else "failed"
            return SandboxReceipt(
                status=status,
                profile_hash=content_hash({"command": command, "profile": profile.as_record()}),
                output_size=len(output),
                metadata={
                    "backend": "docker",
                    "returncode": completed.returncode,
                    "elapsed_seconds": round(perf_counter() - started, 3),
                    "network": profile.network,
                    "read_only_root": True,
                },
            )
