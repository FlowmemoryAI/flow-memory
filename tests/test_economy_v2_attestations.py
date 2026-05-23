import unittest

from flow_memory.economy import Attestation


class EconomyV2AttestationTests(unittest.TestCase):
    def test_attestation_records_claim_and_evidence(self) -> None:
        attestation = Attestation(issuer="verifier", subject="task1", claim="accepted", evidence={"score": 5})
        record = attestation.as_record()
        self.assertEqual(record["issuer"], "verifier")
        self.assertEqual(record["evidence"]["score"], 5)


if __name__ == "__main__":
    unittest.main()
