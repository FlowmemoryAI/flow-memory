"""Print safe recovery instructions for the missing RunPod GPU evidence artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "artifacts" / "incoming" / "flow-memory-cloud-gpu-run-001.tar.gz"


def recovery_instructions() -> dict[str, object]:
    powershell = [
        "cd E:\\FlowMemory\\flow-memory",
        "mkdir artifacts\\incoming -Force",
        "Copy-Item \"$env:USERPROFILE\\Downloads\\flow-memory-cloud-gpu-run-001.tar.gz\" `",
        "  \"artifacts\\incoming\\flow-memory-cloud-gpu-run-001.tar.gz\" `",
        "  -Force",
        "python scripts/import_gpu_run_artifact.py artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz",
        "python scripts/verify_gpu_run_artifact.py flow-memory-cloud-gpu-run-001",
        "python scripts/summarize_gpu_run.py flow-memory-cloud-gpu-run-001",
        "python scripts/export_release_evidence.py",
        "python scripts/verify_release_evidence.py",
        "python scripts/release_decision.py --target neural-gpu-smoke",
    ]
    return {
        "ok": EXPECTED.exists(),
        "artifact_present": EXPECTED.exists(),
        "expected_path": str(EXPECTED),
        "blocker_if_missing": "gpu_evidence_verified_run_missing",
        "do_not_fake_evidence": True,
        "powershell_commands": powershell,
        "next_step": "copy the real RunPod tarball into artifacts/incoming and run the import/verify/summarize commands",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Print RunPod GPU artifact recovery instructions")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    record = recovery_instructions()
    if args.json:
        text = json.dumps(record, indent=2, sort_keys=True)
    else:
        lines = ["# GPU Artifact Recovery", "", f"Expected path: `{record['expected_path']}`", "", "Run:", "", "```powershell", *record["powershell_commands"], "```", "", "Do not fake GPU evidence. The release gate must remain blocked until the real tarball is imported."]
        text = "\n".join(lines) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
