from flow_memory.economy.payment_model import PaymentTerms
from flow_memory.economy.accounting import LocalAccountingLedger


def test_no_real_funds_by_default() -> None:
    terms = PaymentTerms("requester", "worker", 1.0)
    assert terms.simulated is True
    assert terms.as_record()["currency"] == "LOCAL_CREDITS"
    ledger = LocalAccountingLedger()
    assert ledger.as_record()["real_funds_used"] is False
