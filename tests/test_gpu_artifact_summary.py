import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gpu_artifact_summary_is_human_readable(tmp_path: Path):
    input_dir = tmp_path / "run"
    input_dir.mkdir()
    (input_dir / "validation.json").write_text(json.dumps({"ok": True, "mode": "smoke", "results": [1, 2]}), encoding="utf-8")
    subprocess.run([sys.executable, "scripts/package_gpu_artifacts.py", "--input", str(input_dir), "--out", str(tmp_path / "run.tar.gz")], cwd=ROOT, text=True, capture_output=True, check=False)
    result = subprocess.run([sys.executable, "scripts/summarize_gpu_artifacts.py", str(input_dir)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0
    assert "validation ok: True" in result.stdout
