"""Validate that a clean copied checkout can install and run Flow Memory."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.public_alpha_smoke import run_public_alpha_smoke

IGNORE_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "target",
    "out",
    "cache",
    "dist",
    "build",
}


@dataclass(frozen=True)
class CleanCloneStep:
    name: str
    command: tuple[str, ...]
    ok: bool
    returncode: int
    elapsed_seconds: float
    stdout_tail: str

    def as_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "command": self.command,
            "ok": self.ok,
            "returncode": self.returncode,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "stdout_tail": self.stdout_tail[-4000:],
        }


def ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORE_NAMES or name.endswith((".pyc", ".pyo"))}


def run_step(cwd: Path, name: str, command: tuple[str, ...]) -> CleanCloneStep:
    started = perf_counter()
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return CleanCloneStep(
        name=name,
        command=command,
        ok=completed.returncode == 0,
        returncode=completed.returncode,
        elapsed_seconds=perf_counter() - started,
        stdout_tail=output,
    )


def venv_python_path(clone: Path) -> Path:
    candidates = (
        clone / ".venv" / "Scripts" / "python.exe",
        clone / ".venv" / "Scripts" / "python",
        clone / ".venv" / "bin" / "python",
        clone / ".venv" / "bin" / "python3",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]



def validate_clean_clone(root: Path, *, output: Path, keep: bool = False, install: bool = True) -> dict[str, object]:
    root = root.resolve()
    temp_root = Path(tempfile.mkdtemp(prefix="flow-memory-clean-clone-"))
    clone = temp_root / "flow-memory"
    steps: list[CleanCloneStep] = []
    try:
        shutil.copytree(root, clone, ignore=ignore)
        steps.append(run_step(clone, "create_venv", (sys.executable, "-m", "venv", ".venv")))
        venv_python = venv_python_path(clone)
        if steps[-1].ok and install:
            steps.append(run_step(clone, "install_editable_dev", (str(venv_python), "-m", "pip", "install", "-e", ".[dev]")))
        if steps[-1].ok:
            smoke = run_public_alpha_smoke(clone, python=str(venv_python), include_verify=True)
        else:
            smoke = {"ok": False, "results": [], "skipped_reason": f"step failed: {steps[-1].name}"}
        report: dict[str, object] = {
            "ok": all(step.ok for step in steps) and bool(smoke.get("ok")),
            "source_root": str(root),
            "clone_root": str(clone),
            "install_attempted": install,
            "steps": [step.as_record() for step in steps],
            "smoke": smoke,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        return report
    finally:
        if not keep:
            shutil.rmtree(temp_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a clean clone public-alpha validation")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root to copy")
    parser.add_argument("--out", type=Path, default=Path("release_evidence/clean_clone_validation.json"), help="JSON report path")
    parser.add_argument("--keep", action="store_true", help="Keep temporary clone for debugging")
    parser.add_argument("--skip-install", action="store_true", help="Skip editable install after venv creation")
    args = parser.parse_args()

    report = validate_clean_clone(args.root, output=args.out, keep=args.keep, install=not args.skip_install)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
