import json
import subprocess
import sys
from pathlib import Path

from benchmarks.rl_adversarial_env_benchmark import ADVERSARIAL_ENVS, run_adversarial_benchmark

ROOT = Path(__file__).resolve().parents[1]


def test_adversarial_benchmark_covers_all_adversarial_envs():
    result = run_adversarial_benchmark(episodes=4)
    assert result["ok"] is True
    assert tuple(result["envs"]) == ADVERSARIAL_ENVS
    for env_id in ADVERSARIAL_ENVS:
        env_result = result["results"][env_id]
        assert "random" in env_result
        assert "heuristic" in env_result
        assert "heuristic_reward_delta" in env_result


def test_adversarial_benchmark_script_writes_artifact():
    completed = subprocess.run(
        [sys.executable, "benchmarks/rl_adversarial_env_benchmark.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert (ROOT / "artifacts" / "rl" / "rl_adversarial_env_benchmark.json").exists()
