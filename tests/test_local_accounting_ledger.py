from flow_memory.economy.accounting import LocalAccountingLedger
from flow_memory.economy.fees import FeeSchedule
from flow_memory.economy.payment_model import PaymentTerms


def test_local_accounting_ledger_settles_worker_verifier_and_treasury():
    ledger = LocalAccountingLedger()
    ledger.credit("requester", 100.0)
    escrow = "escrow-1"
    ledger.lock_escrow(escrow, "requester", 20.0, task_id="task-1")
    fees = FeeSchedule().calculate(20.0)
    result = ledger.settle_escrow(
        escrow,
        PaymentTerms("requester", "worker", 20.0, verifier_id="verifier", verifier_fee=fees["verifier_fee"], treasury_fee=fees["treasury_fee"]),
        task_id="task-1",
    )
    assert result.ok is True
    assert ledger.balances["worker"] == fees["worker_net_amount"]
    assert ledger.balances["verifier"] == fees["verifier_fee"]
    assert ledger.balances["treasury"] == fees["treasury_fee"]
    assert ledger.as_record()["real_funds_used"] is False


def test_local_accounting_ledger_rejects_insufficient_balance():
    ledger = LocalAccountingLedger()
    try:
        ledger.lock_escrow("escrow-1", "requester", 1.0)
    except ValueError as exc:
        assert "insufficient" in str(exc)
    else:
        raise AssertionError("expected insufficient balance")
