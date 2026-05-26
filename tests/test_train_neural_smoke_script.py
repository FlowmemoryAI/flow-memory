import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_train_neural_smoke_writes_metrics(tmp_path: Path) -> None:
    out = tmp_path / "smoke"
    result = subprocess.run([sys.executable, "scripts/train_neural_smoke.py", "--out", str(out), "--steps", "1"], cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr + result.stdout
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["ok"] is True
    assert (out / "model_card.md").exists()
