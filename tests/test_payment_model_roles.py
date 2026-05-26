from flow_memory.economy.payment_model import EconomyActor, EconomyRole, PaymentTerms


def test_payment_roles_are_explicit() -> None:
    requester = EconomyActor("user-1", EconomyRole.TASK_REQUESTER)
    worker = EconomyActor("agent-1", EconomyRole.WORKER_AGENT, owner_id="owner-1")
    assert requester.as_record()["role"] == "task_requester"
    assert worker.as_record()["owner_id"] == "owner-1"


def test_payment_terms_disable_real_funds_by_default() -> None:
    terms = PaymentTerms("requester", "worker", 10.0, verifier_id="verifier", verifier_fee=1.0, treasury_fee=0.5)
    assert terms.validate() == ()
    assert terms.worker_net_amount == 8.5
    real_terms = PaymentTerms("requester", "worker", 10.0, simulated=False)
    assert "real funds are disabled by default" in real_terms.validate()
