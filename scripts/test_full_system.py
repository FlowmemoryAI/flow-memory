"""Run Flow Memory full-system public-alpha checks and write reports.

The script is intentionally dependency-light. It reports pass/fail/skip for each
subcheck and keeps known optional blockers (Torch/CUDA/GPU evidence) explicit.
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
class SystemCheck:
    name: str
    command: tuple[str, ...]
    required: bool = True
    allow_failure: bool = False
    cwd: Path | None = None

    @property
    def command_cwd(self) -> Path:
        return ROOT if self.cwd is None else self.cwd


@dataclass(frozen=True)
class SystemCheckResult:
    name: str
    command: tuple[str, ...]
    ok: bool
    required: bool
    skipped: bool
    returncode: int
    stdout_tail: str
    stderr_tail: str
    cwd: str

    def as_record(self) -> Mapping[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "ok": self.ok,
            "required": self.required,
            "skipped": self.skipped,
            "returncode": self.returncode,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "cwd": self.cwd,
        }

def quick_checks() -> tuple[SystemCheck, ...]:
    py = sys.executable
    return (
        SystemCheck("import", (py, "-c", "import flow_memory; print('ok')")),
        SystemCheck("cli_agent", (py, "scripts/launch_local_agent.py", "--goal", "Explore and report")),
        SystemCheck("flowlang_agent", (py, "scripts/launch_flowlang_agent.py", "examples/flowlang_agent.flow", "--goal", "Run the declared agent")),
        SystemCheck("neural_agent", (py, "scripts/launch_neural_agent.py", "--backend", "tiny_torch", "--goal", "Explore and report")),
        SystemCheck("local_network", (py, "scripts/run_local_network.py", "--scenario", "all", "--json-out", "artifacts/network/local_network_report.json")),
        SystemCheck("learning_loop", (py, "scripts/run_agent_learning_loop.py", "--json-out", "artifacts/learning/learning_report.json")),
        SystemCheck("rl_arena", (py, "examples/rl_safety_gate_demo.py")),
        SystemCheck("api_help", (py, "scripts/run_local_api_server.py", "--help")),
        SystemCheck("release_local", (py, "scripts/release_decision.py", "--target", "local")),
    )


def full_checks() -> tuple[SystemCheck, ...]:
    py = sys.executable
    return quick_checks() + (
        SystemCheck("pytest", (py, "-m", "pytest", "-q")),
        SystemCheck("verify", ("bash", "scripts/verify.sh")),
        SystemCheck("flow_memory_cli", (py, "-m", "flow_memory", "--json", "Explore and report")),
        SystemCheck("flow_memory_neural_cli", (py, "-m", "flow_memory", "--neural", "tiny_torch", "--json", "Explore and report")),
        SystemCheck("rl_economy_demo", (py, "examples/rl_economy_market_demo.py")),
        SystemCheck("rl_training_benchmark", (py, "benchmarks/rl_training_smoke_benchmark.py")),
        SystemCheck("neural_plan_benchmark", (py, "benchmarks/neural_plan_scoring_benchmark.py"), required=False, allow_failure=True),
        SystemCheck("export_release_evidence", (py, "scripts/export_release_evidence.py")),
        SystemCheck("verify_release_evidence", (py, "scripts/verify_release_evidence.py")),
        SystemCheck("release_neural_gpu_smoke", (py, "scripts/release_decision.py", "--target", "neural-gpu-smoke"), required=False, allow_failure=True),
        SystemCheck("release_public_alpha_neural", (py, "scripts/release_decision.py", "--target", "public-alpha-neural"), required=False, allow_failure=True),
        SystemCheck("release_public_alpha_launch", (py, "scripts/release_decision.py", "--target", "public-alpha-launch"), required=False, allow_failure=True),
        SystemCheck("docker_compose_config", ("docker", "compose", "config")),
        SystemCheck("forge_build", ("forge", "build")),
        SystemCheck("forge_test", ("forge", "test")),
        SystemCheck("cargo_test", ("cargo", "test"), cwd=ROOT / "rust" / "flow-memory-core"),
        SystemCheck("git_diff_check", ("git", "diff", "--check")),
    )


def run_checks(checks: Iterable[SystemCheck]) -> tuple[SystemCheckResult, ...]:
    results: list[SystemCheckResult] = []
    for check in checks:
        try:
            completed = subprocess.run(check.command, cwd=check.command_cwd, capture_output=True, text=True, timeout=600)
            ok = completed.returncode == 0 or check.allow_failure
            results.append(
                SystemCheckResult(
                    check.name,
                    check.command,
                    ok,
                    check.required,
                    False,
                    completed.returncode,
                    _tail(completed.stdout),
                    _tail(completed.stderr),
                    str(check.command_cwd),
                )
            )
        except FileNotFoundError as exc:
            results.append(SystemCheckResult(check.name, check.command, not check.required, check.required, True, 127, "", str(exc), str(check.command_cwd)))
        except subprocess.TimeoutExpired as exc:
            results.append(SystemCheckResult(check.name, check.command, False, check.required, False, 124, _tail(exc.stdout or ""), _tail(exc.stderr or ""), str(check.command_cwd)))
    return tuple(results)


def build_report(mode: str, results: tuple[SystemCheckResult, ...]) -> Mapping[str, Any]:
    required_ok = all(result.ok for result in results if result.required)
    return {
        "ok": required_ok,
        "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(ROOT),
        "results": tuple(result.as_record() for result in results),
        "known_blockers": tuple(_known_blockers(results)),
    }


def write_reports(record: Mapping[str, Any], json_out: Path | None) -> None:
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        md_out = json_out.with_suffix(".md")
        md_out.write_text(_markdown(record), encoding="utf-8")


def _known_blockers(results: tuple[SystemCheckResult, ...]) -> Iterable[str]:
    for result in results:
        text = f"{result.stdout_tail}\n{result.stderr_tail}"
        if "gpu_evidence_verified_run_missing" in text:
            yield "gpu_evidence_verified_run_missing"
        if "torch is not installed" in text.lower():
            yield "torch_not_installed_local_skip"


def _markdown(record: Mapping[str, Any]) -> str:
    lines = ["# Flow Memory Full System Report", "", f"Mode: `{record['mode']}`", f"OK: `{record['ok']}`", "", "| Check | OK | Required | Return code |", "| --- | --- | --- | --- |"]
    for result in record["results"]:
        lines.append(f"| `{result['name']}` | `{result['ok']}` | `{result['required']}` | `{result['returncode']}` |")
    blockers = record.get("known_blockers", ())
    if blockers:
        lines.extend(["", "## Known blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    return "\n".join(lines) + "\n"


def _tail(text: str, limit: int = 1600) -> str:
    return text[-limit:] if len(text) > limit else text


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Flow Memory full-system checks")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--include-api", action="store_true", help="Reserved compatibility flag; API help runs in quick mode")
    parser.add_argument("--include-rl", action="store_true", help="Reserved compatibility flag; RL runs in quick mode")
    parser.add_argument("--include-neural", action="store_true", help="Reserved compatibility flag; neural CLI runs in quick mode")
    parser.add_argument("--include-economy", action="store_true", help="Reserved compatibility flag; local network includes economy")
    parser.add_argument("--include-gpu-evidence", action="store_true", help="Reserved compatibility flag; full mode checks GPU evidence gates")
    args = parser.parse_args()
    selected_mode = "full" if args.full else "quick"
    results = run_checks(full_checks() if selected_mode == "full" else quick_checks())
    record = build_report(selected_mode, results)
    write_reports(record, args.json_out)
    print(json.dumps(record, indent=2, sort_keys=True, default=str))
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
