import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

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


    def test_intelligence_utility_cli_commands(self) -> None:
        from flow_memory.compute_market.config import ComputeMarketConfig
        from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
        from flow_memory.compute_market.storage import ComputeMarketStore

        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
        )
        reset_default_service(service)
        try:
            plan_code, plan_output = self._run_cli(
                [
                    "compute",
                    "intelligence-plan",
                    "--task",
                    "research competitor repo",
                    "--agent-id",
                    "agent_cli_intelligence",
                    "--estimated-value",
                    "50",
                    "--budget",
                    "5",
                    "--allow-background",
                ]
            )
            prices_code, prices_output = self._run_cli(["compute", "prices"])
            usage_code, usage_output = self._run_cli(["compute", "usage", "--agent-id", "agent_cli_intelligence"])
            statement_code, statement_output = self._run_cli(["compute", "statement"])
        finally:
            reset_default_service(None)

        plan = json.loads(plan_output)
        prices = json.loads(prices_output)
        usage = json.loads(usage_output)
        statement = json.loads(statement_output)

        self.assertEqual(plan_code, 0)
        self.assertEqual(prices_code, 0)
        self.assertEqual(usage_code, 0)
        self.assertEqual(statement_code, 0)
        self.assertEqual(plan["intelligence_plan"]["recommended_intelligence_tier"], "background_agent")
        self.assertTrue(prices["ok"])
        self.assertEqual(usage["usage_records"][0]["agent_id"], "agent_cli_intelligence")
        self.assertGreaterEqual(statement["statement"]["record_count"], 1)

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
        original_provider_token = os.environ.get("FLOW_MEMORY_PROVIDER_CLI_TOKEN")
        os.environ["FLOW_MEMORY_PROVIDER_CLI_TOKEN"] = "cli-secret-token"
        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
        )
        reset_default_service(service)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                application_path = Path(temp_dir) / "provider.json"
                application_path.write_text(json.dumps(application), encoding="utf-8")
                review_application_path = Path(temp_dir) / "provider-review.json"
                review_application_path.write_text(
                    json.dumps({**application, "provider_id": "provider_cli_review", "provider_name": "CLI Review Provider"}),
                    encoding="utf-8",
                )

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
                review_apply_code, review_apply_output = self._run_cli(
                    ["compute", "provider-admin", "apply", "--file", str(review_application_path)]
                )
                revision_code, revision_output = self._run_cli(
                    [
                        "compute",
                        "provider-admin",
                        "request-revision",
                        "--provider",
                        "provider_cli_review",
                        "--revision-notes",
                        "add compliance package",
                        "--reviewed-by",
                        "cli-admin",
                    ]
                )
                reject_code, reject_output = self._run_cli(
                    [
                        "compute",
                        "provider-admin",
                        "reject",
                        "--provider",
                        "provider_cli_review",
                        "--rejection-reason",
                        "compliance package rejected",
                    ]
                )
        finally:
            reset_default_service(None)
            if original_provider_token is None:
                os.environ.pop("FLOW_MEMORY_PROVIDER_CLI_TOKEN", None)
            else:
                os.environ["FLOW_MEMORY_PROVIDER_CLI_TOKEN"] = original_provider_token

        applied = json.loads(apply_output)
        verified = json.loads(verify_output)
        reputation = json.loads(reputation_output)
        disabled = json.loads(disable_output)
        review_applied = json.loads(review_apply_output)
        revision = json.loads(revision_output)
        rejected = json.loads(reject_output)
        self.assertEqual(apply_code, 0)
        self.assertEqual(verify_code, 0)
        self.assertEqual(reputation_code, 0)
        self.assertEqual(disable_code, 0)
        self.assertEqual(review_apply_code, 0)
        self.assertEqual(revision_code, 0)
        self.assertEqual(reject_code, 0)
        self.assertFalse(applied["inline_secrets_stored"])
        self.assertEqual(applied["credential_storage"], "external_secret_reference_only")
        self.assertTrue(verified["provider"]["verified"])
        self.assertEqual(reputation["reputation"]["provider_id"], "provider_cli_gpu_1")
        self.assertEqual(disabled["provider_application"]["status"], "disabled")
        self.assertEqual(review_applied["provider_application"]["status"], "pending")
        self.assertEqual(revision["provider_application"]["status"], "revision_requested")
        self.assertEqual(rejected["provider_application"]["status"], "rejected")

    def test_billing_cli_lists_usage_payouts_refunds_and_settles(self) -> None:
        import hmac

        from flow_memory.compute_market.config import ComputeMarketConfig
        from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
        from flow_memory.compute_market.storage import ComputeMarketStore
        from flow_memory.crypto.hashes import content_hash

        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
        )
        raw_event = {
            "id": "evt_cli_credit",
            "type": "checkout.session.completed",
            "amount": 1.0,
            "currency": "usd",
            "metadata": {"account_id": "acct_cli"},
        }
        secret = "whsec_cli_secret"
        signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
        service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})
        created = service.create_job(
            {
                "task_type": "inference",
                "input_ref": "s3://flow-memory-inputs/job-cli.json",
                "model_or_runtime": "llama-runtime",
                "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
                "budget_policy_id": "policy_default",
                "route_id": "route_live_gpu_1",
                "provider_id": "provider_live_gpu_1",
            }
        )
        job_id = str(created["job"]["job_id"])
        service.dispatch_job(job_id, {})
        completed = service.complete_job(
            job_id,
            {"account_id": "acct_cli", "actual_units": 2, "actual_total_cost": 0.18, "currency": "USD"},
        )
        payout_id = str(completed["provider_payout"]["provider_payout_id"])
        usage_charge_id = str(completed["usage_charge"]["usage_charge_id"])
        reset_default_service(service)
        try:
            balance_code, balance_output = self._run_cli(["compute", "billing", "balance", "acct_cli"])
            usage_code, usage_output = self._run_cli(["compute", "billing", "usage", "--account-id", "acct_cli"])
            payout_code, payout_output = self._run_cli(
                [
                    "compute",
                    "billing",
                    "provider-payouts",
                    "--account-id",
                    "acct_cli",
                    "--provider",
                    "provider_live_gpu_1",
                    "--status",
                    "accrued",
                ]
            )
            settle_code, settle_output = self._run_cli(
                [
                    "compute",
                    "billing",
                    "payout-settle",
                    payout_id,
                    "--external-payout-reference",
                    "external-transfer-1",
                    "--settled-by",
                    "ops",
                ]
            )
            refund_code, refund_output = self._run_cli(
                ["compute", "billing", "refund", usage_charge_id, "--reason", "cli_sla_credit"]
            )
        finally:
            reset_default_service(None)

        balance = json.loads(balance_output)
        usage = json.loads(usage_output)
        payout = json.loads(payout_output)
        settled = json.loads(settle_output)
        refund = json.loads(refund_output)

        self.assertEqual(balance_code, 0)
        self.assertEqual(usage_code, 0)
        self.assertEqual(payout_code, 0)
        self.assertEqual(settle_code, 0)
        self.assertEqual(refund_code, 1)
        self.assertEqual(balance["balance"]["available_credits"], 0.82)
        self.assertEqual(usage["usage_charges"][0]["usage_charge_id"], usage_charge_id)
        self.assertEqual(payout["provider_payouts"][0]["provider_payout_id"], payout_id)
        self.assertEqual(settled["provider_payout"]["status"], "settled")
        self.assertFalse(settled["provider_payout"]["funds_moved"])
        self.assertFalse(refund["ok"])
        self.assertEqual(refund["error"]["error_code"], "billing.refund.provider_payout_not_adjustable")

    def test_execution_and_capacity_cli_lifecycle(self) -> None:
        from flow_memory.compute_market.config import ComputeMarketConfig
        from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
        from flow_memory.compute_market.storage import ComputeMarketStore

        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
        )
        reset_default_service(service)
        try:
            create_code, create_output = self._run_cli(
                [
                    "compute",
                    "jobs",
                    "create",
                    "--task-type",
                    "inference",
                    "--input-ref",
                    "s3://flow-memory-inputs/job-cli-lifecycle.json",
                    "--model-or-runtime",
                    "llama-runtime",
                    "--provider",
                    "provider_live_gpu_1",
                    "--route",
                    "route_live_gpu_1",
                    "--gpu-type",
                    "H100",
                    "--gpu-count",
                    "1",
                    "--memory-gb",
                    "80",
                    "--max-runtime-seconds",
                    "600",
                    "--budget-policy",
                    "policy_default",
                ]
            )
            job_id = json.loads(create_output)["job"]["job_id"]
            dispatch_code, dispatch_output = self._run_cli(["compute", "jobs", "dispatch", job_id])
            complete_code, complete_output = self._run_cli(
                [
                    "compute",
                    "jobs",
                    "complete",
                    job_id,
                    "--actual-units",
                    "2",
                    "--actual-total-cost",
                    "0.18",
                    "--actual-latency-ms",
                    "250",
                    "--artifact-ref",
                    "s3://flow-memory-results/job-cli-lifecycle.json",
                ]
            )
            events_code, events_output = self._run_cli(["compute", "jobs", "events", job_id])
            artifacts_code, artifacts_output = self._run_cli(["compute", "jobs", "artifacts", job_id])
            expire_code, expire_output = self._run_cli(["compute", "jobs", "expire-leases"])

            list_code, list_output = self._run_cli(
                [
                    "compute",
                    "capacity",
                    "list",
                    "--provider",
                    "provider_live_gpu_1",
                    "--route",
                    "route_live_gpu_1",
                    "--capacity-units",
                    "10",
                    "--gpu-type",
                    "H100",
                    "--region",
                    "us-east",
                    "--ends-at",
                    "2099-01-01T00:00:00Z",
                    "--price-floor",
                    "2.4",
                ]
            )
            reserve_code, reserve_output = self._run_cli(
                [
                    "compute",
                    "capacity",
                    "reserve",
                    "--provider",
                    "provider_live_gpu_1",
                    "--route",
                    "route_live_gpu_1",
                    "--capacity-units",
                    "2",
                ]
            )
            reservation_id = json.loads(reserve_output)["reservation"]["reservation_id"]
            confirm_code, confirm_output = self._run_cli(["compute", "capacity", "confirm", reservation_id])
            order_book_code, order_book_output = self._run_cli(["compute", "capacity", "order-book"])
            release_code, release_output = self._run_cli(["compute", "capacity", "release", reservation_id])
        finally:
            reset_default_service(None)

        created = json.loads(create_output)
        dispatched = json.loads(dispatch_output)
        completed = json.loads(complete_output)
        events = json.loads(events_output)
        artifacts = json.loads(artifacts_output)
        expired_leases = json.loads(expire_output)
        listed = json.loads(list_output)
        confirmed = json.loads(confirm_output)
        order_book = json.loads(order_book_output)
        released = json.loads(release_output)

        self.assertEqual(create_code, 0)
        self.assertEqual(dispatch_code, 0)
        self.assertEqual(complete_code, 0)
        self.assertEqual(events_code, 0)
        self.assertEqual(artifacts_code, 0)
        self.assertEqual(expire_code, 0)
        self.assertEqual(created["job"]["status"], "queued")
        self.assertEqual(dispatched["job"]["status"], "running")
        self.assertEqual(completed["job"]["status"], "succeeded")
        self.assertEqual(completed["artifact"]["artifact_ref"], "s3://flow-memory-results/job-cli-lifecycle.json")
        self.assertTrue(any(event["event_type"] == "job.completed" for event in events["events"]))
        self.assertEqual(artifacts["artifacts"][0]["artifact_ref"], "s3://flow-memory-results/job-cli-lifecycle.json")
        self.assertEqual(expired_leases["expired_count"], 0)

        self.assertEqual(list_code, 0)
        self.assertEqual(reserve_code, 0)
        self.assertEqual(confirm_code, 0)
        self.assertEqual(order_book_code, 0)
        self.assertEqual(release_code, 0)
        self.assertEqual(listed["capacity_window"]["capacity_units"], 10.0)
        self.assertEqual(confirmed["reservation"]["status"], "confirmed")
        self.assertEqual(order_book["summary"]["total_capacity_units"], 10.0)
        self.assertEqual(released["reservation"]["status"], "released")


    def test_verify_script_uses_portable_python_launcher(self) -> None:
        verify_script = (Path(__file__).resolve().parents[1] / "scripts" / "verify.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("python3", verify_script)
        self.assertIn("py -3", verify_script)
        self.assertNotIn("python -m pytest", verify_script)


if __name__ == "__main__":
    unittest.main()
