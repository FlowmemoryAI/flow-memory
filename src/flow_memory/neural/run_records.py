"""Cloud GPU run records for Neural Agent Layer evidence."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping

@dataclass(frozen=True)
class GpuRunSummary:
    run_id: str
    source_artifact_sha256: str = ""
    gpu_name: str = ""
    python_version: str = ""
    torch_version: str = ""
    cuda_version: str = ""
    cuda_available: bool = False
    git_commit: str = ""
    cli_neural_backend: str = ""
    cli_neural_status: str = ""
    pytest_summary: str = ""
    benchmarks: Mapping[str, Any] = field(default_factory=dict)
    skipped: bool = False
    reason: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.skipped or (self.cuda_available and self.gpu_name and self.git_commit))

    def as_record(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "run_id": self.run_id,
            "source_artifact_sha256": self.source_artifact_sha256,
            "gpu_name": self.gpu_name,
            "python_version": self.python_version,
            "torch_version": self.torch_version,
            "cuda_version": self.cuda_version,
            "cuda_available": self.cuda_available,
            "git_commit": self.git_commit,
            "cli_neural_backend": self.cli_neural_backend,
            "cli_neural_status": self.cli_neural_status,
            "pytest_summary": self.pytest_summary,
            "benchmarks": dict(self.benchmarks),
            "skipped": self.skipped,
            "reason": self.reason,
        }
