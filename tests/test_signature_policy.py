import unittest

from flow_memory.crypto.asymmetric import DEV_HMAC_ALGORITHM, ED25519_ALGORITHM, LOCAL_TEST_ASYMMETRIC_ALGORITHM
from flow_memory.crypto.signature_policy import SignaturePolicy


class SignaturePolicyTests(unittest.TestCase):
    def test_dev_hmac_is_allowed_only_for_local_demo_contexts(self) -> None:
        self.assertTrue(SignaturePolicy("local").evaluate_algorithm(DEV_HMAC_ALGORITHM).ok)

        decision = SignaturePolicy("public-alpha").evaluate_algorithm(DEV_HMAC_ALGORITHM)

        self.assertFalse(decision.ok)
        self.assertEqual(decision.reason, "dev_hmac is local/demo only")

    def test_public_alpha_accepts_asymmetric_algorithms(self) -> None:
        policy = SignaturePolicy("base-sepolia")

        self.assertTrue(policy.evaluate_algorithm(ED25519_ALGORITHM).ok)
        self.assertTrue(policy.evaluate_algorithm(LOCAL_TEST_ASYMMETRIC_ALGORITHM).ok)

    def test_public_alpha_rejects_unknown_non_asymmetric_algorithm(self) -> None:
        decision = SignaturePolicy("testnet").evaluate_algorithm("rsa-demo")

        self.assertFalse(decision.ok)
        self.assertEqual(decision.reason, "public-alpha/testnet requires asymmetric signatures")


if __name__ == "__main__":
    unittest.main()
