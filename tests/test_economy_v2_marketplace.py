import unittest

from flow_memory.economy.attestations import Attestation
from flow_memory.economy.dispute import DisputeCase
from flow_memory.economy.economy_v2 import AgentEconomyV2
from flow_memory.economy.escrow import EscrowAccount


class EconomyV2MarketplaceTests(unittest.TestCase):
    def test_success_lifecycle_records_escrow_reputation_attestations_and_audit(self) -> None:
        economy = AgentEconomyV2()
        requester = "did:key:requester"
        agent = "did:key:agent"

        task = economy.create_task(requester=requester, title="classify sample", reward=7.5)
        bid = economy.place_bid(task.task_id, agent_did=agent, price=7.0)
        assigned = economy.assign(task.task_id, bid.bid_id, actor=requester)
        escrow = economy.fund_escrow(task.task_id, actor=requester)
        submission = economy.submit_work(task.task_id, agent_did=agent, artifact={"answer": "benign"})
        verified = economy.verify_work(task.task_id, actor=requester, accepted=True, notes="meets spec")
        settlement = economy.settle_task(task.task_id, actor=requester)

        self.assertEqual(assigned.status, "assigned")
        self.assertIsInstance(escrow, EscrowAccount)
        self.assertEqual(escrow.status, "funded")
        self.assertEqual(submission.status, "submitted")
        self.assertEqual(verified.status, "verified")
        self.assertEqual(settlement["status"], "settled")
        self.assertEqual(settlement["escrow_status"], "released")
        self.assertEqual(economy.escrow.releases[agent], 7.5)
        self.assertEqual(economy.reputation_for(agent).score, 5.0)
        self.assertEqual(economy.reputation_for(agent).events[-1]["delta"], 5.0)
        self.assertEqual(economy.tasks[task.task_id].status, "settled")
        self.assertTrue(any(entry["action"] == "task_settled" for entry in economy.audit_log))
        self.assertTrue(all(isinstance(attestation, Attestation) for attestation in economy.attestations))
        self.assertEqual([attestation.claim for attestation in economy.attestations], ["work_submitted", "work_accepted"])

    def test_failure_dispute_slash_lifecycle_refunds_escrow_and_audits(self) -> None:
        economy = AgentEconomyV2()
        requester = "did:key:requester"
        agent = "did:key:agent"

        task = economy.create_task(requester=requester, title="write report", reward=3.0)
        bid = economy.place_bid(task.task_id, agent_did=agent, price=2.5)
        economy.assign(task.task_id, bid.bid_id, actor=requester)
        economy.fund_escrow(task.task_id, actor=requester)
        economy.submit_work(task.task_id, agent_did=agent, artifact={"report": "wrong subject"})
        rejected = economy.verify_work(task.task_id, actor=requester, accepted=False, notes="incorrect output")
        dispute = economy.open_dispute(
            task.task_id,
            actor=requester,
            reason="bad work",
            evidence={"expected": "market analysis"},
        )
        settlement = economy.resolve_dispute(dispute.dispute_id, actor=requester, slash=True)

        self.assertEqual(rejected.status, "rejected")
        self.assertIsInstance(dispute, DisputeCase)
        self.assertEqual(dispute.status, "open")
        self.assertEqual(settlement["status"], "slashed")
        self.assertEqual(settlement["escrow_status"], "refunded")
        self.assertEqual(settlement["dispute_resolution"], "requester_upheld")
        self.assertEqual(economy.escrow.refunds[requester], 3.0)
        self.assertEqual(economy.reputation_for(agent).score, -10.0)
        self.assertEqual(economy.disputes.cases[dispute.dispute_id].status, "resolved")
        self.assertEqual(economy.tasks[task.task_id].status, "slashed")
        self.assertTrue(any(entry["action"] == "dispute_resolved" for entry in economy.audit_log))

    def test_double_settlement_rejected(self) -> None:
        economy = AgentEconomyV2()
        requester = "did:key:requester"
        agent = "did:key:agent"
        task = economy.create_task(requester=requester, title="dedupe", reward=1.0)
        bid = economy.place_bid(task.task_id, agent_did=agent, price=1.0)
        economy.assign(task.task_id, bid.bid_id, actor=requester)
        economy.fund_escrow(task.task_id, actor=requester)
        economy.submit_work(task.task_id, agent_did=agent, artifact={"done": True})
        economy.verify_work(task.task_id, actor=requester, accepted=True)

        economy.settle_task(task.task_id, actor=requester)

        with self.assertRaisesRegex(ValueError, "already settled"):
            economy.settle_task(task.task_id, actor=requester)

    def test_unauthorized_settlement_rejected(self) -> None:
        economy = AgentEconomyV2()
        requester = "did:key:requester"
        agent = "did:key:agent"
        task = economy.create_task(requester=requester, title="auth", reward=1.0)
        bid = economy.place_bid(task.task_id, agent_did=agent, price=1.0)
        economy.assign(task.task_id, bid.bid_id, actor=requester)
        economy.fund_escrow(task.task_id, actor=requester)
        economy.submit_work(task.task_id, agent_did=agent, artifact={"done": True})
        economy.verify_work(task.task_id, actor=requester, accepted=True)

        with self.assertRaisesRegex(PermissionError, "requester"):
            economy.settle_task(task.task_id, actor=agent)

        self.assertEqual(economy.escrow.for_task(task.task_id).status, "funded")
        self.assertNotIn(task.task_id, economy.settlements)

    def test_reputation_updates_are_non_transferable(self) -> None:
        economy = AgentEconomyV2()
        agent = "did:key:agent"
        other = "did:key:other"

        economy.reputation_for(agent).record({"event": "local_score_update"}, 4.0)

        self.assertEqual(economy.reputation_for(agent).score, 4.0)
        self.assertEqual(economy.reputation_for(other).score, 0.0)
        self.assertFalse(hasattr(economy.reputation_for(agent), "transfer"))
        self.assertFalse(hasattr(economy, "transfer_reputation"))


if __name__ == "__main__":
    unittest.main()
