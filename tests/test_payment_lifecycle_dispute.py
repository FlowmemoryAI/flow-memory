from flow_memory.economy.accounting import LocalAccountingLedger


def test_payment_lifecycle_dispute_refund_and_slash() -> None:
    ledger = LocalAccountingLedger()
    ledger.credit("requester", 8.0)
    ledger.credit("worker", 3.0)
    ledger.lock_escrow("escrow-dispute", "requester", 8.0, task_id="task-dispute")
    refund = ledger.refund_escrow("escrow-dispute", "requester", task_id="task-dispute")
    slash = ledger.slash("worker", 2.0, task_id="task-dispute", reason="bad work")
    assert refund.ok is True
    assert refund.status == "refunded"
    assert ledger.balances["requester"] == 8.0
    assert ledger.balances["worker"] == 1.0
    assert slash.as_record()["entry_type"] == "slash"
    assert ledger.balances["treasury"] == 2.0
