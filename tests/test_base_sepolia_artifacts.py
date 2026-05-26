import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import TypeAlias, cast

from flow_memory.web3 import CONTRACTS, dependency_graph, dry_run_transactions, generate_deployment_plan
from flow_memory.web3.erc4337 import UserOperationDraft
from flow_memory.web3.verification import validate_base_sepolia_artifacts


ObjectMap: TypeAlias = Mapping[str, object]
TransactionRecord: TypeAlias = Mapping[str, object]

class BaseSepoliaArtifactTests(unittest.TestCase):
    def test_deployment_plan_contains_preflight_fields(self) -> None:
        plan = generate_deployment_plan()
        deployment_order = cast(tuple[str, ...], plan["deployment_order"])
        dependency_graph_record = cast(ObjectMap, plan["dependency_graph"])
        self.assertEqual(84532, plan["chain_id"])
        self.assertEqual(CONTRACTS, deployment_order)
        self.assertFalse(plan["requires_private_key"])
        self.assertIn("TaskEscrow", dependency_graph_record)

    def test_dependency_order_places_dependencies_first(self) -> None:
        order = cast(tuple[str, ...], generate_deployment_plan()["deployment_order"])
        positions = {name: index for index, name in enumerate(order)}
        for name, dependencies in dependency_graph().items():
            for dependency in dependencies:
                self.assertLess(positions[dependency], positions[name])

    def test_dry_run_transaction_payloads_match_contracts(self) -> None:
        txs = cast(tuple[TransactionRecord, ...], dry_run_transactions()["transactions"])
        self.assertEqual(CONTRACTS, tuple(cast(str, tx["contract"]) for tx in txs))
        self.assertTrue(all(tx["dry_run"] for tx in txs))
        self.assertTrue(all(tx["chain_id"] == 84532 for tx in txs))

    def test_erc4337_user_operation_schema(self) -> None:
        operation = UserOperationDraft(sender="0x0000000000000000000000000000000000000000", call_data="0x1234")
        record = operation.as_record()
        self.assertTrue(record["dryRun"])
        self.assertFalse(operation.validate())
        self.assertIn("paymasterAndData", record)

    def test_base_sepolia_artifact_generation_and_validation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base-sepolia"
            subprocess.run(
                [sys.executable, "scripts/generate_deployment_plan.py", "--out", str(base / "deployment-plan.json")],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            dry_run = subprocess.run(
                [sys.executable, "scripts/base_sepolia_dry_run.py", "--out", str(base / "dry-run-transactions.json")],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "scripts/export_contract_registry.py", "--out", str(base / "contract-registry.json")],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            plan = cast(ObjectMap, json.loads((base / "deployment-plan.json").read_text(encoding="utf-8")))
            dry = cast(ObjectMap, json.loads(dry_run.stdout))
            (base / "dry-run-transactions.json").write_text(
                json.dumps(dry["transactions"], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (base / "constructor-args.json").write_text(
                json.dumps(plan["constructor_args"], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (base / "dependency-graph.json").write_text(
                json.dumps(plan["dependency_graph"], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (base / "risk-notes.md").write_text("# Risk notes\n\nUnaudited dry run only.\n", encoding="utf-8")
            (base / "verification-checklist.md").write_text("# Checklist\n\n- No real funds.\n", encoding="utf-8")
            report = validate_base_sepolia_artifacts(base)

        self.assertTrue(report.ok, report.as_record())


if __name__ == "__main__":
    unittest.main()
