"""Deterministic metadata registry for compute-market planning."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.compute_market.models import ComputeProvider, ComputeRoute, PriceCurve, ProviderCapability, UnitPriceSnapshot


@dataclass(frozen=True)
class AssetMetadata:
    asset_symbol: str
    asset_mint_or_address: str
    network: str
    decimals: int
    metadata_source: str = "flow-memory-default-registry"
    verified: bool = False
    dry_run_only: bool = True

    def as_record(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class NetworkMetadata:
    network: str
    chain_id: int | str
    native_asset: str
    metadata_source: str = "flow-memory-default-registry"
    verified: bool = False
    dry_run_only: bool = True

    def as_record(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ProviderMetadata:
    provider_id: str
    provider_name: str
    provider_type: str
    metadata_source: str = "flow-memory-default-registry"
    verified: bool = False
    dry_run_only: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class RouteMetadata:
    route_id: str
    provider_id: str
    provider_name: str
    metadata_source: str = "flow-memory-default-registry"
    verified: bool = False
    dry_run_only: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ExternalProtocolMetadata:
    protocol_id: str
    protocol_name: str
    network: str
    settlement_modes: tuple[str, ...]
    metadata_source: str = "flow-memory-default-registry"
    verified: bool = False
    dry_run_only: bool = True

    def as_record(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


def default_assets() -> tuple[AssetMetadata, ...]:
    return (
        AssetMetadata("USD", "offchain-accounting-usd", "local", 2, verified=True),
        AssetMetadata("USDC", "generic-usdc-asset", "solana", 6, verified=False),
        AssetMetadata("SOL", "native-sol", "solana", 9, verified=False),
        AssetMetadata("ETH", "native-eth", "base-sepolia", 18, verified=False),
        AssetMetadata("CREDITS", "local-compute-credits", "local", 6, verified=True),
    )


def default_networks() -> tuple[NetworkMetadata, ...]:
    return (
        NetworkMetadata("local", "local", "CREDITS", verified=True),
        NetworkMetadata("solana", "solana-dry-run", "SOL"),
        NetworkMetadata("base-sepolia", 84532, "ETH"),
        NetworkMetadata("offchain", "offchain", "USD", verified=True),
    )


def default_provider_metadata() -> tuple[ProviderMetadata, ...]:
    return tuple(
        ProviderMetadata(
            provider_id=provider.provider_id,
            provider_name=provider.provider_name,
            provider_type=provider.provider_type,
            verified=provider.provider_type == "local",
            dry_run_only=True,
        )
        for provider in default_compute_providers()
    )


def default_compute_providers() -> tuple[ComputeProvider, ...]:
    token_capability = ProviderCapability(
        "llm-token-inference",
        unit_types=("token",),
        models=("frontier-compatible", "commodity-open-weight"),
        max_capacity=4_000_000,
        networks=("offchain", "solana"),
        payment_assets=("USD", "USDC"),
        reliability_score=0.92,
    )
    request_capability = ProviderCapability(
        "request-inference",
        unit_types=("request", "inference_job"),
        models=("hosted-request-model",),
        max_capacity=10_000,
        networks=("offchain",),
        payment_assets=("USD",),
        reliability_score=0.88,
    )
    gpu_capability = ProviderCapability(
        "gpu-time",
        unit_types=("gpu_second", "gpu_minute", "gpu_hour"),
        models=("self-hosted-open-weight",),
        max_capacity=3600,
        networks=("local", "solana"),
        payment_assets=("CREDITS", "USDC"),
        reliability_score=0.84,
    )
    reserved_capability = ProviderCapability(
        "reserved-capacity",
        unit_types=("reserved_capacity_slot", "gpu_hour"),
        models=("reserved-gpu-slice",),
        max_capacity=24,
        networks=("offchain",),
        payment_assets=("USD",),
        reliability_score=0.95,
    )
    return (
        ComputeProvider(
            "market-token-provider",
            "Marketplace Token Inference",
            "marketplace",
            "marketplace",
            "solana",
            "USDC",
            capabilities=(token_capability,),
            reliability_score=0.86,
        ),
        ComputeProvider(
            "direct-request-provider",
            "Direct Request Inference",
            "direct",
            "direct",
            "offchain",
            "USD",
            capabilities=(request_capability,),
            reliability_score=0.9,
        ),
        ComputeProvider(
            "gpu-time-provider",
            "GPU Time Route",
            "marketplace",
            "marketplace",
            "solana",
            "USDC",
            capabilities=(gpu_capability,),
            reliability_score=0.82,
        ),
        ComputeProvider(
            "reserved-capacity-provider",
            "Reserved Capacity Route",
            "reserved",
            "reserved_capacity",
            "offchain",
            "USD",
            capabilities=(reserved_capability,),
            reliability_score=0.96,
        ),
        ComputeProvider(
            "local-provider",
            "Local Self-Hosted Route",
            "local",
            "local",
            "local",
            "CREDITS",
            capabilities=(gpu_capability,),
            reliability_score=0.78,
        ),
        ComputeProvider(
            "fallback-provider",
            "Centralized Fallback Route",
            "fallback",
            "fallback",
            "offchain",
            "USD",
            capabilities=(token_capability,),
            reliability_score=0.98,
        ),
    )


def default_compute_routes() -> tuple[ComputeRoute, ...]:
    return (
        _route("market-token-route", "market-token-provider", "Marketplace token route", "marketplace", "marketplace", "solana", "USDC", "token", 0.00000045, 0, 800, ("http_402_dry_run", "solana_usdc_dry_run"), 0.86),
        _route("direct-request-route", "direct-request-provider", "Direct request route", "direct", "direct", "offchain", "USD", "request", 0.015, 0, 650, ("generic_dry_run",), 0.9),
        _route("gpu-minute-route", "gpu-time-provider", "GPU minute marketplace route", "marketplace", "marketplace", "solana", "USDC", "gpu_minute", 0.09, 0, 1200, ("solana_usdc_dry_run",), 0.82),
        _route("reserved-slot-route", "reserved-capacity-provider", "Reserved capacity slot route", "reserved", "reserved_capacity", "offchain", "USD", "reserved_capacity_slot", 2.5, 0, 500, ("generic_dry_run",), 0.96, reservation_required=True),
        _route("local-no-payment-route", "local-provider", "Local no-payment route", "local", "local", "local", "CREDITS", "gpu_minute", 0.0, 0, 1500, ("no_payment",), 0.78),
        _route("fallback-token-route", "fallback-provider", "Fallback token route", "fallback", "fallback", "offchain", "USD", "token", 0.0000018, 0, 450, ("generic_dry_run",), 0.98, fallback_route=True),
    )


def provider_from_route(route: ComputeRoute) -> ComputeProvider:
    for provider in default_compute_providers():
        if provider.provider_id == route.provider_id:
            return provider
    return ComputeProvider(route.provider_id, route.provider_or_route, route.provider_type, route.market_type, route.network, route.payment_asset)


def route_metadata() -> tuple[RouteMetadata, ...]:
    return tuple(
        RouteMetadata(route.route_id, route.provider_id, route.provider_or_route, verified=route.provider_type == "local")
        for route in default_compute_routes()
    )


def external_protocols() -> tuple[ExternalProtocolMetadata, ...]:
    return (
        ExternalProtocolMetadata("http-402", "HTTP 402 machine-payable request", "offchain", ("http_402_dry_run",)),
        ExternalProtocolMetadata("solana-usdc", "Solana USDC dry-run payment intent", "solana", ("solana_usdc_dry_run",)),
        ExternalProtocolMetadata("base-sepolia-erc4337", "Base Sepolia ERC-4337 dry-run", "base-sepolia", ("base_sepolia_erc4337_dry_run",)),
        ExternalProtocolMetadata("generic", "Generic payment intent", "offchain", ("generic_dry_run", "no_payment")),
    )


def metadata_registry() -> Mapping[str, Any]:
    return {
        "assets": tuple(asset.as_record() for asset in default_assets()),
        "networks": tuple(network.as_record() for network in default_networks()),
        "providers": tuple(provider.as_record() for provider in default_provider_metadata()),
        "routes": tuple(route.as_record() for route in route_metadata()),
        "external_protocols": tuple(protocol.as_record() for protocol in external_protocols()),
        "dry_run_only": True,
    }


def _route(
    route_id: str,
    provider_id: str,
    name: str,
    provider_type: str,
    market_type: str,
    network: str,
    asset: str,
    unit_type: str,
    unit_price: float,
    estimated_units: float,
    latency: int,
    settlement_modes: tuple[str, ...],
    reliability: float,
    *,
    reservation_required: bool = False,
    fallback_route: bool = False,
) -> ComputeRoute:
    price_snapshot = UnitPriceSnapshot(unit_type, unit_price, asset, network, provider_id=provider_id, route_id=route_id)
    return ComputeRoute(
        route_id=route_id,
        provider_id=provider_id,
        provider_or_route=name,
        provider_type=provider_type,
        market_type=market_type,
        network=network,
        payment_asset=asset,
        unit_type=unit_type,
        unit_price=unit_price,
        estimated_units=estimated_units,
        estimated_total_cost=None,
        estimated_latency_ms=latency,
        capacity_available=True,
        reservation_required=reservation_required,
        settlement_mode=settlement_modes[0],
        settlement_modes=settlement_modes,
        fallback_route=fallback_route,
        reliability_score=reliability,
        supported_assets=(asset,),
        supported_networks=(network,),
        enabled=True,
        metadata={"provider_verified": provider_type in {"local", "reserved"}},
        price_curve=PriceCurve("unit", (price_snapshot,)),
    )
