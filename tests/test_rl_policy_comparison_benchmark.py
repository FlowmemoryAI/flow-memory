import json
import subprocess
import sys
from pathlib import Path

from benchmarks.rl_policy_comparison_benchmark import compare_policies

ROOT = Path(__file__).resolve().parents[1]


def test_compare_policies_includes_random_heuristic_and_tabular_q():
    result = compare_policies("safety_gate", episodes=6)
    assert result["ok"] is True
    assert set(("random", "heuristic", "tabular_q")).issubset(result)
    assert result["tabular_q_improved"] is True


def test_policy_comparison_benchmark_script_writes_artifact():
    completed = subprocess.run(
        [sys.executable, "benchmarks/rl_policy_comparison_benchmark.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert (ROOT / "artifacts" / "rl" / "rl_policy_comparison_benchmark.json").exists()
