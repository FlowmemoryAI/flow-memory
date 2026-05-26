import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cloud_gpu_validate_smoke_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "validation.json"
    result = subprocess.run(
        [sys.executable, "scripts/cloud_gpu_validate.py", "--smoke", "--json-out", str(out)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["mode"] == "smoke"
    assert data["results"]
