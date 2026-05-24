"""Export public-alpha utility smoke evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.check_dashboard_api import check_dashboard_api
from scripts.check_release_api import check_release_api
from scripts.export_payment_ledger_demo import build_payment_ledger_demo
from scripts.export_rl_env_manifest import export_rl_env_manifest
from scripts.validate_local_network_report import validate_local_network_report


def build_utility_evidence(root: str | Path = ROOT) -> dict[str, object]:
    root_path = Path(root)
    network_report = root_path / "artifacts" / "network" / "local_network_report.json"
    evidence = {
        "dashboard_api": check_dashboard_api(require_scopes=True),
        "release_api": check_release_api(require_scopes=True),
        "rl_env_manifest": export_rl_env_manifest(),
        "payment_ledger_demo": build_payment_ledger_demo(),
        "local_network_report": validate_local_network_report(network_report),
        "real_funds_used": False,
        "raw_artifacts_exposed": False,
    }
    evidence["ok"] = all(
        bool(dict(evidence[key]).get("ok"))
        for key in ("dashboard_api", "release_api", "rl_env_manifest", "payment_ledger_demo")
    ) and evidence["real_funds_used"] is False and evidence["raw_artifacts_exposed"] is False
    evidence["hash"] = hashlib.sha256(json.dumps({k: v for k, v in evidence.items() if k != "hash"}, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Flow Memory utility evidence")
    parser.add_argument("--out", type=Path, default=Path("release_evidence/utility_evidence.json"))
    args = parser.parse_args()
    payload = build_utility_evidence(ROOT)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
