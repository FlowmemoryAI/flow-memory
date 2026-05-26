import json
import subprocess
import sys
from pathlib import Path

from scripts.export_payment_ledger_demo import build_payment_ledger_demo

ROOT = Path(__file__).resolve().parents[1]


def test_payment_ledger_demo_is_local_and_settled() -> None:
    payload = build_payment_ledger_demo()
    assert payload["ok"] is True
    assert payload["real_funds_used"] is False
    balances = payload["ledger"]["balances"]
    assert balances["worker-agent"] == 4.5
    assert balances["verifier-agent"] == 1.0
    assert balances["treasury"] == 0.5


def test_payment_ledger_demo_script_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "payment.json"
    completed = subprocess.run(
        [sys.executable, "scripts/export_payment_ledger_demo.py", "--out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout)["ok"] is True
    assert json.loads(out.read_text(encoding="utf-8"))["real_funds_used"] is False
