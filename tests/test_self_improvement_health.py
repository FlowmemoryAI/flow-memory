import unittest

from flow_memory.self_improvement import HealthMonitor


class SelfImprovementHealthTests(unittest.TestCase):
    def test_detects_degradation_flags(self) -> None:
        report = HealthMonitor().assess(api_errors=1, rate_limited=True, quality_score=0.1, failed_tests=("test_x",))
        self.assertTrue(report.degraded)
        self.assertTrue(report.has("api_error"))
        self.assertTrue(report.has("rate_limited"))
        self.assertTrue(report.has("low_quality"))
        self.assertTrue(report.has("failed_test"))


if __name__ == "__main__":
    unittest.main()
