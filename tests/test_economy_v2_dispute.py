import unittest

from flow_memory.economy import DisputeBook


class EconomyV2DisputeTests(unittest.TestCase):
    def test_dispute_double_resolution_rejected(self) -> None:
        book = DisputeBook()
        case = book.open_case("task1", opened_by="requester", respondent="agent", reason="bad work")
        book.resolve(case.dispute_id, "requester_upheld")
        with self.assertRaises(ValueError):
            book.resolve(case.dispute_id, "agent_upheld")


if __name__ == "__main__":
    unittest.main()
