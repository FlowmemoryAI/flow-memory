import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gpu_artifact_packaging_records_checkpoint_hash(tmp_path: Path):
    input_dir = tmp_path / "run"
    input_dir.mkdir()
    (input_dir / "validation.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (input_dir / "dummy.pt").write_bytes(b"checkpoint")
    out = tmp_path / "run.tar.gz"
    result = subprocess.run([sys.executable, "scripts/package_gpu_artifacts.py", "--input", str(input_dir), "--out", str(out)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr + result.stdout
    assert out.exists()
    checkpoint_manifest = json.loads((input_dir / "checkpoint_manifest.json").read_text(encoding="utf-8"))
    assert checkpoint_manifest["checkpoints"][0]["path"] == "dummy.pt"


def test_gitignore_blocks_model_artifacts():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "artifacts/" in text
    assert "*.pt" in text
    assert "*.safetensors" in text
