import unittest

from flow_memory.api.signed_requests import sign_request, verify_request
from flow_memory.crypto import generate_local_keypair


class ApiSignedRequestsTests(unittest.TestCase):
    def test_signed_request_tamper_detection(self) -> None:
        key = generate_local_keypair("api")
        signature = sign_request("POST", "/x", {"a": 1}, key)
        self.assertTrue(verify_request("POST", "/x", {"a": 1}, signature, key))
        self.assertFalse(verify_request("POST", "/x", {"a": 2}, signature, key))


if __name__ == "__main__":
    unittest.main()
