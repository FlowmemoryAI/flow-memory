import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_train_rl_torch_smoke_script_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "torch_smoke.json"
    completed = subprocess.run(
        [sys.executable, "scripts/train_rl_torch_smoke.py", "--steps", "1", "--out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert out.exists()
