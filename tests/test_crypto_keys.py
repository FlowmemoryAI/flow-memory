import unittest

from flow_memory.crypto import generate_local_keypair


class CryptoKeysTests(unittest.TestCase):
    def test_generate_local_keypair(self) -> None:
        key = generate_local_keypair("k")
        self.assertEqual(key.public_id(), "k")
        self.assertNotIn("secret", key.as_public_record())


if __name__ == "__main__":
    unittest.main()
