from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import threading
from http.server import ThreadingHTTPServer
from typing import Any, Mapping, cast

from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.models import ComputeQuote, ComputeRoute
from flow_memory.compute_market.planner import budget_policy_from_payload, build_task_profile, decide_route, market_policy_from_payload
from flow_memory.compute_market.provider_sandbox import create_provider_sandbox_server, sandbox_quote
from flow_memory.compute_market.service import ComputeMarketService
from flow_memory.compute_market.storage import ComputeMarketStore
from flow_memory.crypto.keys import LocalKeyPair


_PROVIDER_ID = "sandbox-provider"
_ROUTE_ID = "sandbox-gpu-route"
_SIGNING_SECRET_ENV = "FLOW_MEMORY_PROVIDER_SANDBOX_SIGNING_SECRET"


def _provider_record(endpoint: str, signing_key: LocalKeyPair) -> dict[str, Any]:
    health_endpoint = endpoint.rsplit("/", 1)[0] + "/health"
    return {
        "provider_id": _PROVIDER_ID,
        "provider_name": "Flow Memory Provider Sandbox",
        "provider_type": "gpu",
        "market_type": "marketplace",
        "network": "offchain",
        "payment_asset": "USDC",
        "status": "active",
        "verified": True,
        "supported_unit_types": ("gpu_minute", "gpu_hour", "request"),
        "supported_assets": ("USDC", "CREDITS"),
        "supported_networks": ("offchain",),
        "quote_endpoint": endpoint,
        "health_endpoint": health_endpoint,
        "metadata": {
            "quote_endpoint": endpoint,
            "health_endpoint": health_endpoint,
            "outbound_signing_required": True,
            "outbound_signing_key_id": signing_key.key_id,
            "outbound_signing_key_env": _SIGNING_SECRET_ENV,
        },
        "sla": {"uptime_target": 0.99, "max_latency_ms": 1000, "refund_policy": "credit"},
    }


def _route_record() -> dict[str, Any]:
    return {
        "route_id": _ROUTE_ID,
        "provider_id": _PROVIDER_ID,
        "provider_or_route": "Flow Memory Sandbox GPU Route",
        "provider_type": "gpu",
        "market_type": "marketplace",
        "network": "offchain",
        "payment_asset": "USDC",
        "unit_type": "gpu_minute",
        "unit_price": 0.09,
        "estimated_units": 2.0,
        "estimated_total_cost": 0.18,
        "estimated_latency_ms": 1000,
        "capacity_available": True,
        "settlement_mode": "generic_dry_run",
        "settlement_modes": ("generic_dry_run",),
        "dry_run_only": True,
        "quote_ttl_seconds": 300,
        "confidence": 0.9,
        "enabled": True,
    }


def _get_json(url: str) -> tuple[int, Mapping[str, Any]]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload if isinstance(payload, Mapping) else {}
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8") or "{}")
        return exc.code, payload if isinstance(payload, Mapping) else {}


def validate_provider_sandbox() -> Mapping[str, Any]:
    signing_key = LocalKeyPair("sandbox-provider-signing", "sandbox-provider-shared-secret")
    old_secret = os.environ.get(_SIGNING_SECRET_ENV)
    os.environ[_SIGNING_SECRET_ENV] = signing_key.secret
    server = create_provider_sandbox_server("127.0.0.1", 0, signing_key=signing_key)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = cast(tuple[str, int], server.server_address)
        endpoint = f"http://{host}:{port}/quote"
        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(
                compute_market_mode="test",
                rate_limits_enabled=False,
                external_provider_quotes_enabled=True,
                external_provider_allowlist=(host,),
                external_provider_quote_timeout_ms=1_000,
            ),
        )
        provider_created = service.create_provider(_provider_record(endpoint, signing_key))
        route_created = service.create_route(_route_record())
        provider_health = service.provider_health(_PROVIDER_ID)
        sample_quote = sandbox_quote({})
        health_status, health_payload = _get_json(endpoint.rsplit("/", 1)[0] + "/health")
        for contract_unsafe_key in ("broadcast_allowed", "private_key_required", "broadcast_required", "private_key"):
            sample_quote.pop(contract_unsafe_key, None)
        conformance = service.provider_conformance(
            _PROVIDER_ID,
            {"sample_quote": sample_quote, "allowed_assets": ("USDC",), "allowed_networks": ("offchain",)},
        )
        quote_request = service.request_external_provider_quote(
            {
                "provider_id": _PROVIDER_ID,
                "route_id": _ROUTE_ID,
                "task": "provider sandbox conformance validation",
                "allowed_assets": ("USDC",),
                "allowed_networks": ("offchain",),
                "budget": 1.0,
                "selection_strategy": "lowest_cost",
            }
        )
        accepted_quotes = tuple(item for item in quote_request.get("quotes", ()) if isinstance(item, Mapping))
        quote = _quote_from_record(accepted_quotes[0]) if accepted_quotes else None
        route = ComputeRoute(**_route_record())
        plan_payload = {
            "task": "provider sandbox conformance validation",
            "budget": 1.0,
            "allowed_assets": ("USDC",),
            "allowed_networks": ("offchain",),
            "settlement_modes_allowed": ("generic_dry_run",),
            "selection_strategy": "lowest_cost",
        }
        decision = decide_route(
            (quote,) if quote is not None else (),
            (route,),
            build_task_profile(plan_payload),
            budget_policy_from_payload(plan_payload),
            market_policy_from_payload(plan_payload),
            request_id="provider-sandbox-conformance",
            payload=plan_payload,
        )
        cache_records = service.store.list_records("quote_cache_entry", filters={"provider_id": _PROVIDER_ID, "route_id": _ROUTE_ID}).records
        quote_records = service.store.list_records("compute_quote", filters={"provider_id": _PROVIDER_ID, "route_id": _ROUTE_ID}).records
        audit_events = service.audit({}).get("audit_events", ())
        health_records = service.store.list_records("provider_health_snapshot", filters={"provider_id": _PROVIDER_ID}).records
        audit_actions = tuple(str(event.get("action", "")) for event in audit_events if isinstance(event, Mapping))
        selected_route = decision.selected_route if isinstance(decision.selected_route, Mapping) else {}
        normalized_quote = decision.normalized_quote if isinstance(decision.normalized_quote, Mapping) else {}
        ok = all(
            (
                provider_created.get("ok") is True,
                route_created.get("ok") is True,
                conformance.get("ok") is True,
                quote_request.get("ok") is True,
                bool(quote_records),
                provider_health.get("ok") is True,
                health_status == 200,
                health_payload.get("ok") is True,
                bool(cache_records),
                "market.quote.ingested" in audit_actions,
                bool(health_records),
                bool(selected_route),
                selected_route.get("route_id") == _ROUTE_ID,
                bool(normalized_quote),
                normalized_quote.get("source") == "live_provider",
                decision.fail_closed_errors == (),
            )
        )
        return {
            "ok": ok,
            "provider_id": _PROVIDER_ID,
            "route_id": _ROUTE_ID,
            "sandbox_endpoint": endpoint,
            "provider_created": provider_created.get("ok") is True,
            "route_created": route_created.get("ok") is True,
            "contract_ok": conformance.get("ok") is True,
            "quote_ingested": quote_request.get("ok") is True,
            "provider_health_checked": provider_health.get("ok") is True,
            "sandbox_health_status": health_status,
            "quote_count": len(quote_records),
            "quote_cache_count": len(cache_records),
            "audit_ingested": "market.quote.ingested" in audit_actions,
            "health_count": len(health_records),
            "selected_route_id": selected_route.get("route_id", ""),
            "selected_quote_source": normalized_quote.get("source", ""),
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
            "fail_closed_errors": decision.fail_closed_errors,
            "rejected_reasons": decision.rejected_reasons,
        }
    except Exception as exc:
        return {"ok": False, "error_code": type(exc).__name__, "message": str(exc)}
    finally:
        server.shutdown()
        server.server_close()
        if old_secret is None:
            os.environ.pop(_SIGNING_SECRET_ENV, None)
        else:
            os.environ[_SIGNING_SECRET_ENV] = old_secret


def _quote_from_record(record: Mapping[str, Any]) -> ComputeQuote:
    allowed = set(ComputeQuote.__dataclass_fields__)
    return ComputeQuote(**{str(key): value for key, value in record.items() if str(key) in allowed})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Compute Market provider sandbox conformance end to end")
    parser.parse_args(argv)
    result = validate_provider_sandbox()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
