"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from flow_memory import Agent
from flow_memory.protocols import CapabilityManifest
from flow_memory.flowlang import run_flowlang_agent
from flow_memory.agents.neural_binding import AgentNeuralBinding
from flow_memory.agents.profile import AgentProfile
from flow_memory.compute_market.service import default_service
from flow_memory.compute_market.provider_contracts import validate_provider_contract_file


def _json_default(value: Any) -> str:
    try:
        return str(value.isoformat())
    except AttributeError:
        return repr(value)


def _run(prompt_parts: list[str], name: str, json_output: bool, neural_backend: str = "none") -> int:
    prompt = " ".join(prompt_parts)
    if neural_backend != "none":
        profile = AgentProfile(name=name, capabilities=("perception", "memory", "reasoning"), allowed_tools=("respond",), neural_config={"backend": neural_backend})
        neural = AgentNeuralBinding().annotate_plan(profile, prompt, type("PromptPlan", (), {"plan_id": "cli_prompt", "risk_level": "low", "economic_value": 0.0, "steps": (), "as_record": lambda self: {"plan_id": "cli_prompt", "risk_level": "low"}})())
        agent = Agent.create(name=name, capabilities=["perception", "memory", "reasoning"])
        cycle = agent.run_cycle(prompt)
        record = asdict(cycle)
        record["neural"] = neural
        if json_output:
            print(json.dumps(record, indent=2, default=_json_default))
        else:
            print(cycle.final_output)
        return 0
    agent = Agent.create(name=name, capabilities=["perception", "memory", "reasoning"])
    cycle = agent.run_cycle(prompt)
    if json_output:
        print(json.dumps(asdict(cycle), indent=2, default=_json_default))
    else:
        print(cycle.final_output)
    return 0


def _run_flow(flow_path: str, prompt_parts: list[str], json_output: bool, neural_backend: str = "none") -> int:
    prompt = " ".join(prompt_parts)
    result = run_flowlang_agent(flow_path, prompt, neural_backend=neural_backend)
    if json_output:
        print(json.dumps(result, indent=2, default=_json_default))
    else:
        print(result.get("output", {}).get("execution", {}).get("output", result))
    return 0

def _manifest(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="flow-memory manifest")
    parser.add_argument("--name", default="alpha")
    parser.add_argument("--capability", action="append", default=[])
    parser.add_argument("--permission", action="append", default=["respond"])
    args = parser.parse_args(argv)
    agent = Agent.create(name=args.name, capabilities=args.capability)
    manifest = CapabilityManifest(
        agent_did=agent.did,
        name=args.name,
        capabilities=tuple(args.capability),
        permissions=tuple(args.permission),
    )
    print(json.dumps(asdict(manifest), indent=2, default=_json_default))
    return 0


def _compute(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="flow-memory compute",
        description=(
            "Flow Memory Compute Market production-planning CLI. Dry-run only by default: "
            "no private keys, no funds moved, no transaction broadcast."
        ),
        epilog='Example: flow-memory compute plan --task "run agent batch inference" --marketplace-only --asset USDC --network solana --dry-run --json',
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    planning_commands = ("plan", "quote", "route", "payment-plan", "simulate-settlement", "intelligence-plan")
    for name in planning_commands:
        sub = subparsers.add_parser(name, help=f"Run compute-market {name} planning")
        _add_compute_common_args(sub)
    for name in ("providers", "routes", "policies", "economic-memory", "health", "readiness", "prices", "usage", "statement"):
        sub = subparsers.add_parser(name, help=f"Inspect compute-market {name}")
        _add_compute_query_args(sub)
    provider_health = subparsers.add_parser("provider-health", help="Run a provider health check")
    _add_compute_query_args(provider_health)
    audit = subparsers.add_parser("audit", help="Inspect compute-market audit events or verify audit hash chains")
    _add_compute_query_args(audit)
    audit.add_argument("audit_action", nargs="?", default="")
    audit.add_argument("--chain-id", default="all")
    audit.add_argument("--out", default="")
    audit.add_argument("--path", default="")
    audit.add_argument("--from-sequence", type=int, default=1)
    audit.add_argument("--to-sequence", type=int, default=0)
    audit.add_argument("--force", action="store_true")
    audit.add_argument("--export", action="store_true")
    audit.add_argument("--interval-seconds", type=int, default=0)
    audit.add_argument("--min-events", type=int, default=0)
    replay = subparsers.add_parser("replay-decision", help="Replay a past compute route decision")
    _add_compute_query_args(replay)
    replay.add_argument("decision_id")
    contract = subparsers.add_parser("provider-contract", help="Validate compute provider quote contracts")
    contract.add_argument("contract_action", choices=("validate",), help="Provider contract action")
    contract.add_argument("file", help="Quote JSON file to validate")
    contract.add_argument("--json", action="store_true", help="Print JSON output")
    contract.add_argument("--provider", default="")
    provider_admin = subparsers.add_parser("provider-admin", help="Administer market provider onboarding")
    provider_admin.add_argument("provider_action", choices=("apply", "verify", "disable", "conformance", "get", "reputation"))
    _add_compute_query_args(provider_admin)
    provider_admin.add_argument("--file", default="", help="JSON provider application, conformance request, or raw quote")
    provider_admin.add_argument("--verification-notes", default="")
    provider_admin.add_argument("--asset", action="append", default=[])
    provider_admin.add_argument("--network", action="append", default=[])
    billing = subparsers.add_parser("billing", help="Operate no-custody billing ledgers")
    billing.add_argument(
        "billing_action",
        choices=("balance", "usage", "provider-payouts", "payout-settle", "refund", "checkout", "webhook-stripe"),
    )
    billing.add_argument("billing_id", nargs="?", default="")
    _add_compute_query_args(billing)
    billing.add_argument("--account", "--account-id", dest="account_id", default="")
    billing.add_argument("--amount", type=float, default=0.0)
    billing.add_argument("--currency", default="USD")
    billing.add_argument("--status", default="")
    billing.add_argument("--external-payout-reference", default="")
    billing.add_argument("--settled-by", default="")
    billing.add_argument("--reason", default="")
    billing.add_argument("--usage-charge", "--usage-charge-id", dest="usage_charge_id", default="")
    billing.add_argument("--webhook-secret", default="")
    billing.add_argument("--stripe-signature", default="")
    billing.add_argument("--raw-event-file", default="")
    jobs = subparsers.add_parser("jobs", help="Operate compute job execution lifecycle")
    jobs.add_argument(
        "job_action",
        choices=("create", "get", "events", "artifacts", "cancel", "retry", "dispatch", "complete", "fail", "claim", "heartbeat", "release-claim"),
    )
    jobs.add_argument("job_id", nargs="?", default="")
    _add_compute_query_args(jobs)
    jobs.add_argument("--file", default="", help="JSON job payload or lifecycle payload")
    jobs.add_argument("--task-type", default="")
    jobs.add_argument("--input-ref", default="")
    jobs.add_argument("--model-or-runtime", default="")
    jobs.add_argument("--gpu-type", default="")
    jobs.add_argument("--gpu-count", type=int, default=0)
    jobs.add_argument("--memory-gb", type=int, default=0)
    jobs.add_argument("--max-runtime-seconds", type=int, default=0)
    jobs.add_argument("--budget-policy", default="")
    jobs.add_argument("--worker-id", default="")
    jobs.add_argument("--account", "--account-id", dest="account_id", default="")
    jobs.add_argument("--actual-units", type=float, default=0.0)
    jobs.add_argument("--actual-total-cost", type=float, default=0.0)
    jobs.add_argument("--actual-latency-ms", type=float, default=0.0)
    jobs.add_argument("--artifact-ref", default="")
    jobs.add_argument("--error-code", default="")
    jobs.add_argument("--reason", default="")
    jobs.add_argument("--lease-ttl-seconds", type=int, default=0)
    capacity = subparsers.add_parser("capacity", help="Operate capacity inventory and reservation book")
    capacity.add_argument("capacity_action", choices=("list", "order-book", "reserve", "confirm", "release", "expire", "auction"))
    capacity.add_argument("reservation_id", nargs="?", default="")
    _add_compute_query_args(capacity)
    capacity.add_argument("--file", default="", help="JSON capacity payload")
    capacity.add_argument("--capacity-units", type=float, default=0.0)
    capacity.add_argument("--available-units", type=float, default=0.0)
    capacity.add_argument("--unit-type", default="")
    capacity.add_argument("--resource-type", default="")
    capacity.add_argument("--gpu-type", default="")
    capacity.add_argument("--region", default="")
    capacity.add_argument("--starts-at", default="")
    capacity.add_argument("--ends-at", default="")
    capacity.add_argument("--reserved-from", default="")
    capacity.add_argument("--reserved-until", default="")
    capacity.add_argument("--hold-expires-at", default="")
    capacity.add_argument("--price-floor", type=float, default=0.0)
    capacity.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args(argv)
    service = default_service()
    payload = _compute_payload(args)
    try:
        if args.command == "providers":
            output = service.list_providers(payload)
        elif args.command == "provider-health":
            output = service.provider_health(str(args.provider))
        elif args.command == "routes":
            output = service.list_routes(payload)
        elif args.command == "policies":
            output = service.list_policies(payload)
        elif args.command == "economic-memory":
            output = service.economic_memory_query(payload)
        elif args.command == "audit":
            action = str(getattr(args, "audit_action", ""))
            if action == "verify":
                output = service.audit_verify(payload)
            elif action == "export":
                output = service.audit_export(payload)
            elif action == "checkpoint":
                output = service.audit_checkpoint(payload)
            elif action == "verify-export":
                output = service.audit_verify_export(payload)
            elif action == "replay":
                output = service.audit_forensic_replay(payload)
            elif action == "checkpoint-schedule":
                output = service.audit_checkpoint_schedule(payload)
            elif action == "chain-monitor":
                output = service.audit_chain_monitor(payload)
            else:
                output = service.audit(payload)
        elif args.command == "health":
            output = service.health()
        elif args.command == "readiness":
            output = service.readiness()
        elif args.command == "prices":
            output = service.compute_prices(payload)
        elif args.command == "usage":
            output = service.compute_usage(payload)
        elif args.command == "statement":
            output = service.compute_usage_statement(payload)
        elif args.command == "replay-decision":
            output = service.replay_decision(str(args.decision_id), payload)
        elif args.command == "provider-contract":
            output = validate_provider_contract_file(Path(str(args.file)), provider_id=str(getattr(args, "provider", "")))
        elif args.command == "provider-admin":
            output = _provider_admin_output(service, args, payload)
        elif args.command == "billing":
            output = _billing_output(service, args, payload)
        elif args.command == "jobs":
            output = _job_output(service, args, payload)
        elif args.command == "capacity":
            output = _capacity_output(service, args, payload)
        elif args.command == "intelligence-plan":
            output = service.intelligence_plan(payload)
        elif args.command == "quote":
            output = service.quote(payload)
        elif args.command == "route":
            output = service.route(payload)
        elif args.command == "payment-plan":
            output = service.payment_plan(payload)
        elif args.command == "simulate-settlement":
            output = service.simulate_settlement(payload)
        else:
            output = service.plan(payload)
    except ValueError as exc:
        output = {
            "ok": False,
            "error": {
                "message": str(exc),
                "reason_code": "validation_error",
                "next_safe_action": "remove unsafe fields or correct compute planning options",
                "request_id": payload.get("request_id", ""),
            },
        }
        print(json.dumps(output, indent=2, sort_keys=True, default=_json_default))
        return 2
    print(json.dumps(output, indent=2, sort_keys=True, default=_json_default))
    if not bool(output.get("ok", True)):
        allow_no_route = bool(getattr(args, "allow_no_route", False))
        no_route = "no_valid_route" in json.dumps(output, default=str)
        return 0 if allow_no_route and no_route else 1
    plan = output.get("compute_plan")
    if isinstance(plan, dict) and not bool(plan.get("ok", True)):
        allow_no_route = bool(getattr(args, "allow_no_route", False))
        no_route = "no_valid_route" in json.dumps(plan, default=str)
        return 0 if allow_no_route and no_route else 1
    return 0


def _add_compute_common_args(sub: argparse.ArgumentParser) -> None:
    _add_compute_query_args(sub)
    sub.add_argument("--task", default="plan compute for agent task")
    sub.add_argument("--marketplace-only", action="store_true")
    sub.add_argument("--asset", action="append", default=[])
    sub.add_argument("--network", action="append", default=[])
    sub.add_argument("--max-total-cost", type=float, default=0.0)
    sub.add_argument("--budget", type=float, default=0.0)
    sub.add_argument("--estimated-value", type=float, default=0.0)
    sub.add_argument("--intelligence-tier", default="")
    sub.add_argument("--reasoning-level", default="")
    sub.add_argument("--max-reasoning-steps", type=int, default=0)
    sub.add_argument("--max-tool-calls", type=int, default=0)
    sub.add_argument("--allow-background", action="store_true")
    sub.add_argument("--allow-reserved-capacity", action="store_true")
    sub.add_argument("--max-background-runtime-seconds", type=int, default=0)
    sub.add_argument("--checkpoint-interval-seconds", type=int, default=0)
    sub.add_argument("--max-unit-price", type=float, default=0.0)
    sub.add_argument("--selection-strategy", "--strategy", dest="selection_strategy", default="balanced")
    sub.add_argument("--scenario", default="provider_quote_available")
    sub.add_argument("--dry-run", action="store_true", default=True)
    sub.add_argument("--allow-unknown-price", action="store_true")
    sub.add_argument("--allow-stale-quote", action="store_true")
    sub.add_argument("--fallback-denied", action="store_true")
    sub.add_argument("--allow-no-route", action="store_true")


def _add_compute_query_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--json", action="store_true", help="Print JSON output")
    sub.add_argument("--request-id", default="")
    sub.add_argument("--idempotency-key", default="")
    sub.add_argument("--agent-id", default="")
    sub.add_argument("--goal-id", default="")
    sub.add_argument("--policy", default="")
    sub.add_argument("--provider", default="")
    sub.add_argument("--route", default="")
    sub.add_argument("--limit", type=int, default=100)
    sub.add_argument("--cursor", default="")



def _mapping_output(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    raise TypeError("compute market service returned a non-object response")


def _provider_admin_output(service: Any, args: Any, payload: dict[str, Any]) -> Mapping[str, Any]:
    action = str(getattr(args, "provider_action", ""))
    provider_payload = {**payload, **_load_json_object(str(getattr(args, "file", "")))}
    provider_id = str(provider_payload.get("provider_id") or getattr(args, "provider", "") or "")
    if provider_id:
        provider_payload["provider_id"] = provider_id
    assets = tuple(str(item) for item in getattr(args, "asset", ()) if str(item))
    networks = tuple(str(item) for item in getattr(args, "network", ()) if str(item))
    if assets and "allowed_assets" not in provider_payload:
        provider_payload["allowed_assets"] = assets
    if networks and "allowed_networks" not in provider_payload:
        provider_payload["allowed_networks"] = networks
    verification_notes = str(getattr(args, "verification_notes", ""))
    if verification_notes:
        provider_payload["verification_notes"] = verification_notes

    if action == "apply":
        return _mapping_output(service.apply_market_provider(provider_payload))
    if action == "verify":
        return _mapping_output(service.verify_market_provider(_required_provider_id(provider_id), provider_payload))
    if action == "disable":
        return _mapping_output(service.disable_market_provider(_required_provider_id(provider_id), provider_payload))
    if action == "get":
        return _mapping_output(service.market_provider(_required_provider_id(provider_id)))
    if action == "reputation":
        return _mapping_output(service.provider_reputation(_required_provider_id(provider_id)))
    if action == "conformance":
        conformance_payload: dict[str, Any] = dict(provider_payload)
        if (
            "sample_quote" not in conformance_payload
            and "quote" not in conformance_payload
            and "quote_id" in conformance_payload
        ):
            conformance_payload = {**conformance_payload, "sample_quote": dict(conformance_payload)}
        return _mapping_output(service.provider_conformance(_required_provider_id(provider_id), conformance_payload))
    raise ValueError(f"unsupported provider admin action: {action}")


def _billing_output(service: Any, args: Any, payload: dict[str, Any]) -> Mapping[str, Any]:
    action = str(getattr(args, "billing_action", ""))
    billing_id = str(getattr(args, "billing_id", ""))
    billing_payload = dict(payload)
    account_id = str(getattr(args, "account_id", ""))
    if account_id:
        billing_payload["account_id"] = account_id
    if billing_id and action in {"balance", "checkout"}:
        billing_payload["account_id"] = billing_id
    if action == "checkout":
        billing_payload["amount"] = float(getattr(args, "amount", 0.0) or 0.0)
        billing_payload["currency"] = str(getattr(args, "currency", "USD"))
        return _mapping_output(service.billing_checkout(billing_payload))
    if action == "balance":
        return _mapping_output(service.billing_balance(billing_payload))
    if action == "usage":
        return _mapping_output(service.billing_usage(billing_payload))
    if action == "provider-payouts":
        status = str(getattr(args, "status", ""))
        if status:
            billing_payload["status"] = status
        return _mapping_output(service.billing_provider_payouts(billing_payload))
    if action == "payout-settle":
        billing_payload["external_payout_reference"] = str(getattr(args, "external_payout_reference", ""))
        billing_payload["settled_by"] = str(getattr(args, "settled_by", ""))
        return _mapping_output(
            service.settle_provider_payout(_required_billing_id(billing_id, "payout_id"), billing_payload)
        )
    if action == "refund":
        usage_charge_id = str(getattr(args, "usage_charge_id", "") or billing_id)
        if usage_charge_id:
            billing_payload["usage_charge_id"] = usage_charge_id
        amount = float(getattr(args, "amount", 0.0) or 0.0)
        if amount > 0.0:
            billing_payload["amount"] = amount
        reason = str(getattr(args, "reason", ""))
        if reason:
            billing_payload["reason"] = reason
        billing_payload["currency"] = str(getattr(args, "currency", "USD"))
        return _mapping_output(service.billing_refund(billing_payload))
    if action == "webhook-stripe":
        billing_payload["raw_event"] = _load_json_object(str(getattr(args, "raw_event_file", "")))
        billing_payload["webhook_secret"] = str(getattr(args, "webhook_secret", ""))
        billing_payload["stripe_signature"] = str(getattr(args, "stripe_signature", ""))
        return _mapping_output(service.billing_webhook_stripe(billing_payload))
    raise ValueError(f"unsupported billing action: {action}")


def _required_billing_id(value: str, label: str) -> str:
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _job_output(service: Any, args: Any, payload: dict[str, Any]) -> Mapping[str, Any]:
    action = str(getattr(args, "job_action", ""))
    job_id = str(getattr(args, "job_id", ""))
    job_payload = {**payload, **_load_json_object(str(getattr(args, "file", "")))}
    for attr, key in (
        ("task_type", "task_type"),
        ("input_ref", "input_ref"),
        ("model_or_runtime", "model_or_runtime"),
        ("budget_policy", "budget_policy_id"),
        ("worker_id", "worker_id"),
        ("account_id", "account_id"),
        ("artifact_ref", "artifact_ref"),
        ("error_code", "error_code"),
        ("reason", "reason"),
    ):
        _set_if_present(job_payload, key, str(getattr(args, attr, "")))
    resource_request = dict(job_payload.get("resource_request", {})) if isinstance(job_payload.get("resource_request"), Mapping) else {}
    if str(getattr(args, "gpu_type", "")):
        resource_request["gpu_type"] = str(getattr(args, "gpu_type", ""))
    if int(getattr(args, "gpu_count", 0) or 0) > 0:
        resource_request["gpu_count"] = int(getattr(args, "gpu_count", 0) or 0)
    if int(getattr(args, "memory_gb", 0) or 0) > 0:
        resource_request["memory_gb"] = int(getattr(args, "memory_gb", 0) or 0)
    if int(getattr(args, "max_runtime_seconds", 0) or 0) > 0:
        resource_request["max_runtime_seconds"] = int(getattr(args, "max_runtime_seconds", 0) or 0)
    if resource_request:
        job_payload["resource_request"] = resource_request
    for attr, key in (
        ("actual_units", "actual_units"),
        ("actual_total_cost", "actual_total_cost"),
        ("actual_latency_ms", "actual_latency_ms"),
    ):
        value = float(getattr(args, attr, 0.0) or 0.0)
        if value > 0.0:
            job_payload[key] = value
    lease_ttl_seconds = int(getattr(args, "lease_ttl_seconds", 0) or 0)
    if lease_ttl_seconds > 0:
        job_payload["lease_ttl_seconds"] = lease_ttl_seconds
    if action == "create":
        return _mapping_output(service.create_job(job_payload))
    if action == "claim":
        if job_id:
            job_payload["job_id"] = job_id
        return _mapping_output(service.claim_job(job_payload))
    required_job_id = _required_billing_id(job_id, "job_id")
    if action == "get":
        return _mapping_output(service.get_job(required_job_id))
    if action == "events":
        return _mapping_output(service.job_events(required_job_id))
    if action == "artifacts":
        return _mapping_output(service.job_artifacts(required_job_id))
    if action == "cancel":
        return _mapping_output(service.cancel_job(required_job_id, job_payload))
    if action == "retry":
        return _mapping_output(service.retry_job(required_job_id, job_payload))
    if action == "dispatch":
        return _mapping_output(service.dispatch_job(required_job_id, job_payload))
    if action == "complete":
        return _mapping_output(service.complete_job(required_job_id, job_payload))
    if action == "fail":
        return _mapping_output(service.fail_job(required_job_id, job_payload))
    if action == "heartbeat":
        return _mapping_output(service.heartbeat_job(required_job_id, job_payload))
    if action == "release-claim":
        return _mapping_output(service.release_job_claim(required_job_id, job_payload))
    raise ValueError(f"unsupported job action: {action}")


def _capacity_output(service: Any, args: Any, payload: dict[str, Any]) -> Mapping[str, Any]:
    action = str(getattr(args, "capacity_action", ""))
    reservation_id = str(getattr(args, "reservation_id", ""))
    capacity_payload = {**payload, **_load_json_object(str(getattr(args, "file", "")))}
    if reservation_id:
        capacity_payload["reservation_id"] = reservation_id
    for attr, key in (
        ("unit_type", "unit_type"),
        ("resource_type", "resource_type"),
        ("gpu_type", "gpu_type"),
        ("region", "region"),
        ("starts_at", "starts_at"),
        ("ends_at", "ends_at"),
        ("reserved_from", "reserved_from"),
        ("reserved_until", "reserved_until"),
        ("hold_expires_at", "hold_expires_at"),
    ):
        _set_if_present(capacity_payload, key, str(getattr(args, attr, "")))
    for attr, key in (
        ("capacity_units", "capacity_units"),
        ("available_units", "available_units"),
        ("price_floor", "price_floor"),
    ):
        value = float(getattr(args, attr, 0.0) or 0.0)
        if value > 0.0:
            capacity_payload[key] = value
    if bool(getattr(args, "allow_partial", False)):
        capacity_payload["allow_partial"] = True
    if action == "list":
        return _mapping_output(service.list_capacity(capacity_payload))
    if action == "order-book":
        return _mapping_output(service.capacity_order_book(capacity_payload))
    if action == "reserve":
        return _mapping_output(service.reserve_capacity(capacity_payload))
    if action == "confirm":
        return _mapping_output(service.confirm_capacity(capacity_payload))
    if action == "release":
        return _mapping_output(service.release_capacity(capacity_payload))
    if action == "expire":
        return _mapping_output(service.expire_capacity(capacity_payload))
    if action == "auction":
        return _mapping_output(service.auction_capacity(capacity_payload))
    raise ValueError(f"unsupported capacity action: {action}")


def _set_if_present(payload: dict[str, Any], key: str, value: str) -> None:
    if value:
        payload[key] = value


def _load_json_object(path: str) -> dict[str, Any]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("provider admin file must contain a JSON object")
    return dict(data)


def _required_provider_id(provider_id: str) -> str:
    if not provider_id:
        raise ValueError("provider_id is required; pass --provider or include provider_id in --file")
    return provider_id


def _compute_payload(args: Any) -> dict[str, Any]:
    policy = {
        "policy_id": str(getattr(args, "policy", "") or "default-compute-market-policy"),
        "marketplace_only": bool(getattr(args, "marketplace_only", False)),
        "dry_run_required": bool(getattr(args, "dry_run", True)),
        "fallback_allowed": not bool(getattr(args, "fallback_denied", False)),
        "max_total_cost": float(getattr(args, "max_total_cost", 0.0) or 0.0),
        "max_unit_price": float(getattr(args, "max_unit_price", 0.0) or 0.0),
        "allowed_assets": tuple(getattr(args, "asset", ()) or ()),
        "allowed_networks": tuple(getattr(args, "network", ()) or ()),
        "allow_unknown_price": bool(getattr(args, "allow_unknown_price", False)),
        "allow_stale_quote": bool(getattr(args, "allow_stale_quote", False)),
        "estimated_value": float(getattr(args, "estimated_value", 0.0) or 0.0),
        "budget": float(getattr(args, "budget", 0.0) or 0.0),
        "intelligence_tier": str(getattr(args, "intelligence_tier", "")),
        "reasoning_level": str(getattr(args, "reasoning_level", "")),
        "allow_background": bool(getattr(args, "allow_background", False)),
        "allow_reserved_capacity": bool(getattr(args, "allow_reserved_capacity", False)),
        "max_background_runtime_seconds": int(getattr(args, "max_background_runtime_seconds", 0) or 0),
        "checkpoint_interval_seconds": int(getattr(args, "checkpoint_interval_seconds", 0) or 0),
        "reasoning_budget": {
            "reasoning_level": str(getattr(args, "reasoning_level", "")),
            "max_reasoning_steps": int(getattr(args, "max_reasoning_steps", 0) or 0),
            "max_tool_calls": int(getattr(args, "max_tool_calls", 0) or 0),
            "max_background_runtime_seconds": int(getattr(args, "max_background_runtime_seconds", 0) or 0),
            "checkpoint_interval_seconds": int(getattr(args, "checkpoint_interval_seconds", 0) or 0),
        },
    }
    return {
        "task": str(getattr(args, "task", "plan compute for agent task")),
        "agent_id": str(getattr(args, "agent_id", "")),
        "goal_id": str(getattr(args, "goal_id", "")),
        "request_id": str(getattr(args, "request_id", "")),
        "idempotency_key": str(getattr(args, "idempotency_key", "")),
        "provider_id": str(getattr(args, "provider", "")),
        "route_id": str(getattr(args, "route", "")),
        "policy": policy,
        "selection_strategy": str(getattr(args, "selection_strategy", "balanced")),
        "provider_constraints": (str(getattr(args, "provider", "")),) if getattr(args, "provider", "") else (),
        "scenario": str(getattr(args, "scenario", "provider_quote_available")),
        "limit": int(getattr(args, "limit", 100) or 100),
        "cursor": str(getattr(args, "cursor", "")),
        "chain_id": str(getattr(args, "chain_id", "")),
        "out": str(getattr(args, "out", "")),
        "path": str(getattr(args, "path", "")),
        "from_sequence": int(getattr(args, "from_sequence", 1) or 1),
        "to_sequence": int(getattr(args, "to_sequence", 0) or 0),
        "force": bool(getattr(args, "force", False)),
        "export": bool(getattr(args, "export", False)),
        "interval_seconds": int(getattr(args, "interval_seconds", 0) or 0),
        "min_events": int(getattr(args, "min_events", 0) or 0),
        "account_id": str(getattr(args, "account_id", "")),
        "estimated_value": float(getattr(args, "estimated_value", 0.0) or 0.0),
        "budget": float(getattr(args, "budget", 0.0) or 0.0),
        "intelligence_tier": str(getattr(args, "intelligence_tier", "")),
        "reasoning_level": str(getattr(args, "reasoning_level", "")),
        "allow_background": bool(getattr(args, "allow_background", False)),
        "allow_reserved_capacity": bool(getattr(args, "allow_reserved_capacity", False)),
        "max_background_runtime_seconds": int(getattr(args, "max_background_runtime_seconds", 0) or 0),
        "checkpoint_interval_seconds": int(getattr(args, "checkpoint_interval_seconds", 0) or 0),
        "reasoning_budget": {
            "reasoning_level": str(getattr(args, "reasoning_level", "")),
            "max_reasoning_steps": int(getattr(args, "max_reasoning_steps", 0) or 0),
            "max_tool_calls": int(getattr(args, "max_tool_calls", 0) or 0),
            "max_background_runtime_seconds": int(getattr(args, "max_background_runtime_seconds", 0) or 0),
            "checkpoint_interval_seconds": int(getattr(args, "checkpoint_interval_seconds", 0) or 0),
        },
        "dry_run": True,
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "manifest":
        return _manifest(argv[1:])
    if argv and argv[0] == "compute":
        return _compute(argv[1:])
    if argv and argv[0] == "run":
        argv = argv[1:]

    parser = argparse.ArgumentParser(prog="flow-memory", description="Run a local Flow Memory agent")
    parser.add_argument("prompt", nargs="+", help="Observation/goal for the agent")
    parser.add_argument("--name", default="alpha", help="Agent name")
    parser.add_argument("--flow", default="", help="FlowLang .flow file to compile and run")
    parser.add_argument("--json", action="store_true", help="Print full cognitive-cycle trace as JSON")
    parser.add_argument("--neural", default="none", choices=["none", "tiny_torch", "vjepa2", "videomae"], help="Optional neural advisory backend")
    args = parser.parse_args(argv)
    if args.flow:
        return _run_flow(args.flow, args.prompt, args.json, args.neural)
    return _run(args.prompt, args.name, args.json, args.neural)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
