import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gpu_env_check_runs_without_torch_requirement() -> None:
    result = subprocess.run([sys.executable, "scripts/gpu_env_check.py", "--json"], cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "python_version" in data
    assert "recommended_next_command" in data


def test_gpu_env_check_require_flags_are_clear() -> None:
    result = subprocess.run([sys.executable, "scripts/gpu_env_check.py", "--require-torch"], cwd=ROOT, text=True, capture_output=True, check=False)
    data = json.loads(result.stdout)
    if data["torch_import"]:
        assert result.returncode == 0
    else:
        assert result.returncode == 1
        assert any("require-torch" in message for message in data["messages"])
