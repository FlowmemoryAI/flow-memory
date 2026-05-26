import io
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout

from flow_memory.cli import main


class CLITests(unittest.TestCase):
    def _run_cli(self, argv: list[str]) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_module_shorthand_runs_json(self) -> None:
        code, output = self._run_cli(["--json", "Explore and report"])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIn("cycle_id", payload)
        self.assertTrue(payload["action_result"]["success"])

    def test_run_subcommand_runs(self) -> None:
        code, output = self._run_cli(["run", "Explore and report"])
        self.assertEqual(code, 0)
        self.assertIn("Processed goal", output)

    def test_compute_subcommands_output_plan_and_dry_run_payment(self) -> None:
        code, output = self._run_cli(
            [
                "compute",
                "plan",
                "--task",
                "run agent batch inference",
                "--marketplace-only",
                "--asset",
                "USDC",
                "--network",
                "solana",
                "--dry-run",
            ]
        )
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["compute_plan"]["payment_plan"]["dry_run_only"])
        self.assertIn("rejected_reasons", payload["compute_plan"])

        code, output = self._run_cli(["compute", "route", "--task", "route compute", "--asset", "NOTREAL"])
        self.assertEqual(code, 1)
        payload = json.loads(output)
        self.assertFalse(payload["ok"])
        self.assertIn("unsupported_asset", " ".join(tuple(reason for values in payload["route_decision"]["rejected_reasons"].values() for reason in values)))

        for command in ("quote", "providers", "payment-plan", "simulate-settlement", "economic-memory"):
            args = ["compute", command]
            if command in {"quote", "payment-plan", "simulate-settlement"}:
                args.extend(["--task", "compute task"])
            code, output = self._run_cli(args)
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(output)["ok"])


    def test_provider_admin_cli_applies_verifies_and_disables_provider(self) -> None:
        from flow_memory.compute_market.config import ComputeMarketConfig
        from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
        from flow_memory.compute_market.storage import ComputeMarketStore

        application = {
            "provider_id": "provider_cli_gpu_1",
            "provider_name": "CLI GPU Provider",
            "provider_type": "gpu",
            "supported_unit_types": ["gpu_minute", "gpu_hour", "request"],
            "supported_assets": ["USD", "USDC", "CREDITS"],
            "supported_networks": ["offchain", "solana", "base"],
            "quote_endpoint": "https://provider.example.com/quote",
            "health_endpoint": "https://provider.example.com/health",
            "credentials": {"secret_ref": "render/env/FLOW_MEMORY_PROVIDER_CLI_TOKEN"},
            "sla": {"uptime_target": 0.99, "max_latency_ms": 1000, "refund_policy": "credit"},
        }
        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
        )
        reset_default_service(service)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                application_path = Path(temp_dir) / "provider.json"
                application_path.write_text(json.dumps(application), encoding="utf-8")

                apply_code, apply_output = self._run_cli(
                    ["compute", "provider-admin", "apply", "--file", str(application_path)]
                )
                verify_code, verify_output = self._run_cli(
                    [
                        "compute",
                        "provider-admin",
                        "verify",
                        "--provider",
                        "provider_cli_gpu_1",
                        "--verification-notes",
                        "contract reviewed",
                    ]
                )
                reputation_code, reputation_output = self._run_cli(
                    ["compute", "provider-admin", "reputation", "--provider", "provider_cli_gpu_1"]
                )
                disable_code, disable_output = self._run_cli(
                    ["compute", "provider-admin", "disable", "--provider", "provider_cli_gpu_1"]
                )
        finally:
            reset_default_service(None)

        applied = json.loads(apply_output)
        verified = json.loads(verify_output)
        reputation = json.loads(reputation_output)
        disabled = json.loads(disable_output)
        self.assertEqual(apply_code, 0)
        self.assertEqual(verify_code, 0)
        self.assertEqual(reputation_code, 0)
        self.assertEqual(disable_code, 0)
        self.assertFalse(applied["inline_secrets_stored"])
        self.assertEqual(applied["credential_storage"], "external_secret_reference_only")
        self.assertTrue(verified["provider"]["verified"])
        self.assertEqual(reputation["reputation"]["provider_id"], "provider_cli_gpu_1")
        self.assertEqual(disabled["provider_application"]["status"], "disabled")


    def test_verify_script_uses_portable_python_launcher(self) -> None:
        verify_script = (Path(__file__).resolve().parents[1] / "scripts" / "verify.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("python3", verify_script)
        self.assertIn("py -3", verify_script)
        self.assertNotIn("python -m pytest", verify_script)


if __name__ == "__main__":
    unittest.main()
