import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_train_neural_gpu_fails_clearly_without_cuda(tmp_path: Path) -> None:
    try:
        import torch
        if torch.cuda.is_available():
            pytest.skip("CUDA available on this runner")
    except ImportError:
        pass
    out = tmp_path / "gpu"
    result = subprocess.run([sys.executable, "scripts/train_neural_gpu.py", "--steps", "1", "--out", str(out)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 1
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["ok"] is False
    assert "CUDA" in metrics["reason"] or "Optional dependency" in metrics["reason"]
