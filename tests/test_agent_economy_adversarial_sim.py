import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flow_memory.simulation.reports import metrics_report, write_metrics_json


class AgentEconomyAdversarialSimulationTests(unittest.TestCase):
    def test_adversarial_scenarios_emit_metrics(self) -> None:
        report = metrics_report()
        metrics = {metric["scenario"]: metric for metric in report["metrics"]}

        self.assertGreaterEqual(report["scenario_count"], 5)
        self.assertIn("honest_baseline", metrics)
        self.assertIn("low_quality_underpriced", metrics)
        self.assertIn("colluding_verifier", metrics)
        self.assertIn("spam_and_overpriced_bids", metrics)
        self.assertIn("reputation_farming", metrics)
        self.assertIn("repeated_disputes_and_sybil", metrics)
        self.assertEqual(metrics["honest_baseline"]["settled_count"], 1)
        self.assertGreaterEqual(metrics["low_quality_underpriced"]["slashing_count"], 1)
        self.assertGreaterEqual(metrics["colluding_verifier"]["collusion_detected"], 1)
        self.assertGreaterEqual(metrics["spam_and_overpriced_bids"]["rejected_bid_count"], 2)
        self.assertGreaterEqual(metrics["reputation_farming"]["reputation_farming_detected"], 1)
        self.assertGreaterEqual(metrics["repeated_disputes_and_sybil"]["sybil_duplicates_detected"], 1)
        self.assertGreaterEqual(metrics["repeated_disputes_and_sybil"]["repeated_disputes_detected"], 1)

    def test_metrics_json_export_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "metrics-1.json"
            second = Path(tmp) / "metrics-2.json"
            write_metrics_json(first)
            write_metrics_json(second)
            self.assertEqual(first.read_text(encoding="utf-8"), second.read_text(encoding="utf-8"))
            payload = json.loads(first.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "local-prototype")

    def test_demo_exports_metrics_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            out = Path(tmp) / "metrics.json"
            completed = subprocess.run(
                [sys.executable, "examples/agent_economy_adversarial_sim_demo.py", "--out", str(out)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)
            self.assertTrue(out.exists())
            self.assertEqual(payload["scenario_count"], len(payload["metrics"]))


if __name__ == "__main__":
    unittest.main()
