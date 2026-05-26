import json
import subprocess
import sys
from pathlib import Path

from flow_memory.neural.gpu_evidence import summarize_gpu_run

ROOT = Path(__file__).resolve().parents[1]


def test_gpu_artifact_summary_is_human_readable(tmp_path: Path) -> None:

    input_dir = tmp_path / "run"
    input_dir.mkdir()
    (input_dir / "validation.json").write_text(json.dumps({"ok": True, "mode": "smoke", "results": [1, 2]}), encoding="utf-8")
    subprocess.run([sys.executable, "scripts/package_gpu_artifacts.py", "--input", str(input_dir), "--out", str(tmp_path / "run.tar.gz")], cwd=ROOT, text=True, capture_output=True, check=False)
    result = subprocess.run([sys.executable, "scripts/summarize_gpu_artifacts.py", str(input_dir)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0
    assert "validation ok: True" in result.stdout


def test_gpu_summary_parses_run_metadata(tmp_path: Path) -> None:
    (tmp_path / "gpu_info.txt").write_text("python: 3.12\ntorch: 2.12.0\ncuda available: True\ncuda version: 13.0\ngpu: NVIDIA GeForce RTX 4090\n")
    (tmp_path / "git_commit.txt").write_text("abc123\n")
    (tmp_path / "validation_summary.txt").write_text("339 passed, 3 skipped")
    (tmp_path / "cli_neural.json").write_text(json.dumps({"neural": {"backend": "tiny_torch", "status": "available"}}))
    summary = summarize_gpu_run(tmp_path, run_id="run")
    assert summary.pytest_summary == "339 passed, 3 skipped"
    assert summary.git_commit == "abc123"
    assert summary.cli_neural_status == "available"
