import unittest

from flow_memory.crypto.canonical_json import CanonicalJsonError, canonical_json, canonical_json_hash


class CryptoCanonicalJsonTests(unittest.TestCase):
    def test_canonical_json_is_deterministic_for_key_order_and_tuples(self) -> None:
        left = {"b": 2, "a": ("x", {"d": True, "c": None})}
        right = {"a": ["x", {"c": None, "d": True}], "b": 2}

        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(canonical_json(left), '{"a":["x",{"c":null,"d":true}],"b":2}')
        self.assertEqual(canonical_json_hash(left), canonical_json_hash(right))

    def test_canonical_json_rejects_non_string_object_keys(self) -> None:
        with self.assertRaises(CanonicalJsonError):
            canonical_json({1: "ambiguous"})

    def test_canonical_json_rejects_non_finite_float(self) -> None:
        with self.assertRaises(CanonicalJsonError):
            canonical_json({"value": float("nan")})


if __name__ == "__main__":
    unittest.main()
