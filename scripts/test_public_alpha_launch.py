"""Run local public-alpha launch checks and write an evidence report.

This script intentionally does not require GPU evidence, CUDA, real funds, or network
services. GPU-gated releases remain separate and blocked until the real RunPod
artifact is imported.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class LaunchCheck:
    name: str
    command: tuple[str, ...]
    required: bool = True
    timeout: int = 300


@dataclass(frozen=True)
class LaunchCheckResult:
    name: str
    command: tuple[str, ...]
    ok: bool
    required: bool
    returncode: int
    stdout_tail: str
    stderr_tail: str

    def as_record(self) -> Mapping[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "ok": self.ok,
            "required": self.required,
            "returncode": self.returncode,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


def launch_checks() -> tuple[LaunchCheck, ...]:
    py = sys.executable
    return (
        LaunchCheck("cli", (py, "scripts/launch_local_agent.py", "--goal", "Explore and report")),
        LaunchCheck("flowlang", (py, "scripts/launch_flowlang_agent.py", "examples/flowlang_agent.flow", "--goal", "Run the declared agent")),
        LaunchCheck("neural", (py, "scripts/launch_neural_agent.py", "--backend", "tiny_torch", "--goal", "Explore and report")),
        LaunchCheck(
            "local_network",
            (
                py,
                "scripts/run_local_network.py",
                "--scenario",
                "all",
                "--emit-visual-events",
                "--json-out",
                "artifacts/network/local_network_report.json",
            ),
        ),
        LaunchCheck(
            "visual_replay",
            (
                py,
                "scripts/export_visual_replay.py",
                "artifacts/network/local_network_report.json",
                "--out",
                "dashboard/src/mock-data/local-network-replay.json",
            ),
        ),
        LaunchCheck("api_help", (py, "scripts/run_local_api_server.py", "--help")),
        LaunchCheck("release_local", (py, "scripts/release_decision.py", "--target", "local")),
        LaunchCheck("release_local_public_alpha", (py, "scripts/release_decision.py", "--target", "local-public-alpha")),
    )


def run_checks(checks: Iterable[LaunchCheck]) -> tuple[LaunchCheckResult, ...]:
    results: list[LaunchCheckResult] = []
    for check in checks:
        try:
            completed = subprocess.run(check.command, cwd=ROOT, capture_output=True, text=True, timeout=check.timeout)
            results.append(
                LaunchCheckResult(
                    name=check.name,
                    command=check.command,
                    ok=completed.returncode == 0,
                    required=check.required,
                    returncode=completed.returncode,
                    stdout_tail=_tail(completed.stdout),
                    stderr_tail=_tail(completed.stderr),
                )
            )
        except subprocess.TimeoutExpired as exc:
            results.append(
                LaunchCheckResult(
                    name=check.name,
                    command=check.command,
                    ok=False,
                    required=check.required,
                    returncode=124,
                    stdout_tail=_tail(exc.stdout or ""),
                    stderr_tail=_tail(exc.stderr or ""),
                )
            )
    return tuple(results)


def build_report(results: tuple[LaunchCheckResult, ...]) -> Mapping[str, Any]:
    checks = {result.name: result.as_record() for result in results}
    required_ok = all(result.ok for result in results if result.required)
    return {
        "ok": required_ok,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(ROOT),
        "checks": checks,
        "gpu_artifact_required": False,
        "real_funds_used": False,
        "known_blockers": tuple(_known_blockers(results)),
    }


def write_report(report: Mapping[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    out.with_suffix(".md").write_text(_markdown(report), encoding="utf-8")


def _known_blockers(results: tuple[LaunchCheckResult, ...]) -> Iterable[str]:
    for result in results:
        text = f"{result.stdout_tail}\n{result.stderr_tail}".lower()
        if "torch is not installed" in text:
            yield "torch_not_installed_local_skip"
        if "gpu_evidence_verified_run_missing" in text:
            yield "gpu_evidence_verified_run_missing"


def _markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Public Alpha Launch Report",
        "",
        f"OK: `{report['ok']}`",
        "",
        "| Check | OK | Return code |",
        "| --- | --- | --- |",
    ]
    for name, result in dict(report["checks"]).items():
        lines.append(f"| `{name}` | `{result['ok']}` | `{result['returncode']}` |")
    blockers = tuple(report.get("known_blockers", ()))
    if blockers:
        lines.extend(["", "## Known blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    return "\n".join(lines) + "\n"


def _tail(text: str, limit: int = 1600) -> str:
    return text[-limit:] if len(text) > limit else text


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Flow Memory local public-alpha launch checks")
    parser.add_argument("--out", type=Path, default=Path("artifacts/public_alpha_launch/launch_report.json"))
    args = parser.parse_args()
    report = build_report(run_checks(launch_checks()))
    out = args.out if args.out.is_absolute() else ROOT / args.out
    write_report(report, out)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
