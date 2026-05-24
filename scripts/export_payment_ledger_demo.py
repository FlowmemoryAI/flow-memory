"""Export a local simulated payment ledger demo."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.economy.accounting import LocalAccountingLedger
from flow_memory.economy.payment_model import PaymentTerms


def build_payment_ledger_demo() -> dict[str, object]:
    ledger = LocalAccountingLedger()
    task_id = "task-payment-demo"
    escrow_id = "escrow-payment-demo"
    ledger.credit("requester", 10.0, task_id=task_id, metadata={"kind": "initial_local_balance"})
    ledger.lock_escrow(escrow_id, "requester", 6.0, task_id=task_id)
    settlement = ledger.settle_escrow(
        escrow_id,
        PaymentTerms(
            requester_id="requester",
            worker_id="worker-agent",
            verifier_id="verifier-agent",
            amount=6.0,
            verifier_fee=1.0,
            treasury_fee=0.5,
        ),
        task_id=task_id,
    )
    return {
        "ok": settlement.ok,
        "mode": "local_simulated_accounting",
        "task_id": task_id,
        "escrow_id": escrow_id,
        "ledger": ledger.as_record(),
        "settlement": settlement.as_record(),
        "who_pays": "TaskRequester funds escrow",
        "who_earns": "WorkerAgent earns after verification; VerifierAgent may receive a fee",
        "real_funds_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Flow Memory simulated payment ledger demo")
    parser.add_argument("--out", type=Path, default=Path("artifacts/economy/payment_ledger_demo.json"))
    args = parser.parse_args()
    payload = build_payment_ledger_demo()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["ok"] and payload["real_funds_used"] is False else 1


if __name__ == "__main__":
    raise SystemExit(main())
