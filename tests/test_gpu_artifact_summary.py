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


def test_imported_gpu_run_summary_script_prints_neural_fields(tmp_path: Path):
    input_dir = tmp_path / "run"
    input_dir.mkdir()
    (input_dir / "validation.json").write_text(
        json.dumps(
            {
                "ok": True,
                "mode": "full",
                "results": [
                    {"name": "cli_neural", "ok": True},
                    {"name": "agent_policy_benchmark", "ok": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    (input_dir / "gpu_info.json").write_text(
        json.dumps(
            {
                "gpu_name": "NVIDIA GeForce RTX 4090",
                "torch_version": "2.12.0+cu130",
                "cuda_available": True,
            }
        ),
        encoding="utf-8",
    )
    artifact = tmp_path / "run.tar.gz"
    subprocess.run(
        [
            sys.executable,
            "scripts/package_gpu_artifacts.py",
            "--input",
            str(input_dir),
            "--out",
            str(artifact),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    imported = subprocess.run(
        [
            sys.executable,
            "scripts/import_gpu_run_artifact.py",
            "--artifact",
            str(artifact),
            "--out",
            str(tmp_path / "gpu_runs"),
            "--run-id",
            "run-001",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(imported.stdout)["summary"]["environment"]["gpu_name"] == "NVIDIA GeForce RTX 4090"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/summarize_gpu_run.py",
            str(tmp_path / "gpu_runs" / "run-001"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "GPU: NVIDIA GeForce RTX 4090" in result.stdout
    assert "CLI neural: ok" in result.stdout
