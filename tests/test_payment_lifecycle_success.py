from flow_memory.economy.accounting import LocalAccountingLedger
from flow_memory.economy.payment_model import PaymentTerms


def test_payment_lifecycle_success() -> None:
    ledger = LocalAccountingLedger()
    ledger.credit("requester", 12.0)
    ledger.lock_escrow("escrow-success", "requester", 12.0, task_id="task-success")
    result = ledger.settle_escrow("escrow-success", PaymentTerms("requester", "worker", 12.0, verifier_id="verifier", verifier_fee=1.0, treasury_fee=0.5), task_id="task-success")
    assert result.ok is True
    assert result.status == "settled"
    assert result.balances["worker"] == 10.5
    assert result.as_record()["simulated_today"] is True
