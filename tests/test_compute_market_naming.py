from pathlib import Path
from typing import Any, Mapping, cast

from flow_memory.api.manifest import API_ENDPOINTS
from flow_memory.api.openapi import openapi_schema

ROOT = Path(__file__).resolve().parents[1]
BANNED_PUBLIC_TERMS = ("squire", "square", "correlation")


def test_no_public_api_route_or_openapi_tag_uses_reference_branding() -> None:
    for endpoint in API_ENDPOINTS:
        assert "/squire" not in endpoint.path.lower()
        assert "squire" not in endpoint.name.lower()
        assert "squire" not in endpoint.description.lower()
    schema = openapi_schema()
    paths = cast(Mapping[str, Mapping[str, Mapping[str, Any]]], schema["paths"])
    assert all("squire" not in path.lower() for path in paths)
    for path_item in paths.values():
        for operation in path_item.values():
            assert "squire" not in " ".join(operation.get("tags", ())).lower()
            assert "squire" not in operation.get("summary", "").lower()


def test_cli_source_does_not_expose_legacy_command() -> None:
    text = (ROOT / "src" / "flow_memory" / "cli.py").read_text(encoding="utf-8").lower()
    assert "flow-memory compute" in text
    assert "flow-memory squire" not in text
    assert 'argv[0] == "squire"' not in text


def test_skill_metadata_uses_compute_market_product_name() -> None:
    skill = ROOT / "skills" / "compute-market" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    description_line = next(line for line in text.splitlines() if line.startswith("description:"))

    assert "name: compute-market" in text
    assert "Flow Memory Compute Market" in description_line
    for term in BANNED_PUBLIC_TERMS:
        assert term not in description_line.lower()


def test_docs_describe_compute_market_not_reference_branding() -> None:
    text = (ROOT / "docs" / "COMPUTE_MARKET.md").read_text(encoding="utf-8")

    assert "Flow Memory Compute Market" in text
    assert "Payment and settlement are dry-run only" in text
    assert "No funds are moved" in text
    assert "Transaction broadcast is disabled" in text
    assert "Marketplace-only policies fail closed" in text
    assert "Live settlement requires a separate security review" in text
    assert "All payment and settlement flows are dry-run only. Flow Memory does not handle private keys, does not move funds, and does not broadcast transactions in this release." in text
    for required in (
        "POST /compute/plan",
        "POST /compute/quote",
        "POST /compute/route",
        "POST /compute/payment-plan",
        "POST /compute/economic-memory/query",
        "flow-memory compute plan",
        "flow-memory compute quote",
        "flow-memory compute route",
        "flow-memory compute providers",
        "flow-memory compute simulate-settlement",
        "flow-memory compute economic-memory",
        "Flow Memory Compute Market Alpha",
    ):
        assert required in text


def test_launch_copy_uses_compute_market_positioning() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Flow Memory Compute Market gives agents economic memory for compute." in readme
    assert "All payment and settlement flows are dry-run only. Flow Memory does not handle private keys, does not move funds, and does not broadcast transactions in this release." in readme
    assert "production compute futures" in readme
    assert "Flow Memory Compute Market Alpha" in readme
