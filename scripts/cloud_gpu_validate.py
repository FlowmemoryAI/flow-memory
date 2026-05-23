"""Run the Flow Memory cloud GPU validation lane."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@dataclass(frozen=True)
class CommandSpec:
    name: str
    command: tuple[str, ...]
    required: bool = True


PY = sys.executable


def build_commands(mode: str, *, skip_benchmarks: bool = False, skip_training: bool = False) -> tuple[CommandSpec, ...]:
    commands: list[CommandSpec] = [CommandSpec("gpu_env_check", (PY, "scripts/gpu_env_check.py", "--json"))]
    if mode == "smoke":
        commands.extend(
            (
                CommandSpec("neural_optional_imports", (PY, "-m", "pytest", "-q", "tests/test_neural_optional_imports.py")),
                CommandSpec("cli_neural_flag_test", (PY, "-m", "pytest", "-q", "tests/test_cli_neural_flag.py")),
                CommandSpec("neural_agent_demo", (PY, "examples/neural_agent_demo.py")),
                CommandSpec("neural_perception_demo", (PY, "examples/neural_perception_demo.py")),
                CommandSpec("cli_neural", (PY, "-m", "flow_memory", "--neural", "tiny_torch", "--json", "Explore and report")),
            )
        )
        return tuple(commands)
    commands.extend(
        (
            CommandSpec("full_pytest", (PY, "-m", "pytest", "-q")),
            CommandSpec("torch_neural_tests", (PY, "-m", "pytest", "-q", "tests/test_tiny_dual_stream_encoder.py", "tests/test_tiny_jepa_world_model.py", "tests/test_cli_neural_flag.py")),
            CommandSpec("neural_agent_demo", (PY, "examples/neural_agent_demo.py")),
            CommandSpec("neural_perception_demo", (PY, "examples/neural_perception_demo.py")),
            CommandSpec("neural_world_model_demo", (PY, "examples/neural_world_model_demo.py")),
            CommandSpec("neural_plan_scoring_demo", (PY, "examples/neural_plan_scoring_demo.py")),
            CommandSpec("cli_neural", (PY, "-m", "flow_memory", "--neural", "tiny_torch", "--json", "Explore and report")),
        )
    )
    if not skip_benchmarks:
        commands.extend(
            (
                CommandSpec("appearance_free_benchmark", (PY, "benchmarks/neural_appearance_free_motion_benchmark.py")),
                CommandSpec("world_model_benchmark", (PY, "benchmarks/neural_world_model_prediction_benchmark.py")),
                CommandSpec("plan_scoring_benchmark", (PY, "benchmarks/neural_plan_scoring_benchmark.py")),
                CommandSpec("memory_retrieval_benchmark", (PY, "benchmarks/neural_memory_retrieval_benchmark.py")),
                CommandSpec("agent_policy_benchmark", (PY, "benchmarks/neural_agent_policy_benchmark.py")),
            )
        )
    if not skip_training:
        commands.extend(
            (
                CommandSpec("train_tiny_dual_stream", (PY, "-m", "flow_memory.neural.training.train_tiny_dual_stream")),
                CommandSpec("train_world_model", (PY, "-m", "flow_memory.neural.training.train_world_model")),
                CommandSpec("train_agent_policy", (PY, "-m", "flow_memory.neural.training.train_agent_policy")),
                CommandSpec("evaluate_neural_stack", (PY, "-m", "flow_memory.neural.training.evaluate_neural_stack")),
            )
        )
    commands.extend(
        (
            CommandSpec("export_dependency_inventory", (PY, "scripts/export_dependency_inventory.py")),
            CommandSpec("export_release_evidence", (PY, "scripts/export_release_evidence.py")),
            CommandSpec("release_decision_local", (PY, "scripts/release_decision.py", "--target", "local")),
        )
    )
    return tuple(commands)


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:] if len(text) > limit else text


def run_command(spec: CommandSpec, *, cwd: Path = ROOT) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    result = subprocess.run(spec.command, cwd=cwd, text=True, capture_output=True, env=env, check=False)
    return {
        "name": spec.name,
        "command": list(spec.command),
        "required": spec.required,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout_tail": _tail(result.stdout),
        "stderr_tail": _tail(result.stderr),
    }


def run_validation(*, mode: str, run_dir: Path, skip_benchmarks: bool = False, skip_training: bool = False, fail_fast: bool = False) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for spec in build_commands(mode, skip_benchmarks=skip_benchmarks, skip_training=skip_training):
        record = run_command(spec)
        results.append(record)
        if fail_fast and not record["ok"] and record["required"]:
            break
    summary = {
        "ok": all(result["ok"] or not result["required"] for result in results),
        "mode": mode,
        "run_dir": str(run_dir),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "next_command": "python scripts/train_neural_smoke.py --out artifacts/neural/smoke",
    }
    (run_dir / "validation.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _default_run_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / "artifacts" / "cloud_gpu" / stamp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Flow Memory cloud GPU validation lane")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--smoke", action="store_true", help="Run fast smoke validation")
    group.add_argument("--full", action="store_true", help="Run full validation lane")
    parser.add_argument("--json-out", type=Path, help="Write validation JSON to this path")
    parser.add_argument("--skip-benchmarks", action="store_true")
    parser.add_argument("--skip-training", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args(argv)
    mode = "full" if args.full else "smoke"
    run_dir = args.json_out.parent if args.json_out else _default_run_dir()
    summary = run_validation(mode=mode, run_dir=run_dir, skip_benchmarks=args.skip_benchmarks, skip_training=args.skip_training, fail_fast=args.fail_fast)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
