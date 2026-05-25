"""Typed production-planning configuration for Flow Memory Compute Market."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class ComputeMarketConfig:
    compute_market_enabled: bool = True
    compute_market_mode: str = "production_planning"
    database_url: str = ".flow_memory/compute_market.sqlite3"
    storage_backend: str = "sqlite"
    storage_pool_size: int = 4
    storage_timeout_ms: int = 5_000
    storage_max_overflow: int = 4
    storage_statement_timeout_ms: int = 5_000
    postgres_ssl_mode: str = "require"
    migrations_auto_run: bool = True
    require_managed_sql_in_production: bool = False
    migrations_enabled: bool = True
    rate_limit_backend: str = "in_memory"
    circuit_breaker_backend: str = "in_memory"
    redis_url: str = ""
    redis_prefix: str = "flow-memory:compute-market"
    rate_limit_enabled: bool = True
    circuit_breaker_enabled: bool = True
    rate_limit_fail_closed: bool = True
    circuit_breaker_fail_closed: bool = True
    provider_registry_mode: str = "database"
    quote_cache_ttl: int = 300
    provider_timeout_ms: int = 2_000
    global_planning_timeout_ms: int = 10_000
    max_candidate_routes: int = 64
    max_quote_cache_entries: int = 10_000
    dry_run_required: bool = True
    live_settlement_enabled: bool = False
    broadcast_enabled: bool = False
    private_key_inputs_allowed: bool = False
    audit_required: bool = True
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    rate_limits_enabled: bool = True
    external_provider_quotes_enabled: bool = False
    external_provider_quote_timeout_ms: int = 5_000
    external_provider_execution_enabled: bool = False
    external_provider_execution_timeout_ms: int = 10_000
    economic_memory_writes_enabled: bool = True
    admin_mutations_enabled: bool = True
    audit_export_required: bool = False
    audit_export_uri: str = ""
    provider_contracts_required: bool = False
    provider_contracts_verified: bool = False
    external_provider_allowlist: tuple[str, ...] = ()
    settlement_environment: str = ""
    settlement_security_review_id: str = ""
    stripe_webhook_secret: str = ""

    @property
    def storage_backend_effective(self) -> str:
        normalized = self.storage_backend.strip().lower()
        if normalized in {"postgres", "postgresql"}:
            return "postgresql"
        if self.database_url.startswith(("postgres://", "postgresql://")) and normalized in {"", "sqlite"}:
            return "postgresql"
        if normalized:
            return normalized
        return "sqlite"


    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.compute_market_mode not in {"production_planning", "local_dev", "test"}:
            errors.append("compute_market_mode must be production_planning, local_dev, or test")
        if self.storage_backend_effective not in {"sqlite", "postgresql"}:
            errors.append("storage_backend must be sqlite or postgresql")
        if self.storage_backend_effective == "postgresql" and not self.database_url.startswith(("postgres://", "postgresql://")):
            errors.append("postgresql storage_backend requires a postgres/postgresql database_url")
        if self.require_managed_sql_in_production and self.compute_market_mode == "production_planning" and self.storage_backend_effective != "postgresql":
            errors.append("production_planning requires managed SQL when require_managed_sql_in_production=true")
        if self.storage_pool_size < 1:
            errors.append("storage_pool_size must be positive")
        if self.storage_timeout_ms < 1:
            errors.append("storage_timeout_ms must be positive")
        if self.storage_max_overflow < 0:
            errors.append("storage_max_overflow must be non-negative")
        if self.storage_statement_timeout_ms < 1:
            errors.append("storage_statement_timeout_ms must be positive")
        if self.postgres_ssl_mode not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
            errors.append("postgres_ssl_mode must be a valid PostgreSQL sslmode")
        if self.provider_timeout_ms < 1:
            errors.append("provider_timeout_ms must be positive")
        if self.global_planning_timeout_ms < self.provider_timeout_ms:
            errors.append("global_planning_timeout_ms must be at least provider_timeout_ms")
        if self.max_candidate_routes < 1:
            errors.append("max_candidate_routes must be positive")
        if self.quote_cache_ttl < 1:
            errors.append("quote_cache_ttl must be positive")
        if self.external_provider_quote_timeout_ms < 1_000:
            errors.append("external_provider_quote_timeout_ms must be at least 1000")
        if self.external_provider_execution_timeout_ms < 1_000:
            errors.append("external_provider_execution_timeout_ms must be at least 1000")
        if self.external_provider_execution_enabled and not self.external_provider_allowlist:
            errors.append("external_provider_execution_enabled requires external_provider_allowlist")
        if self.live_settlement_enabled and not self.settlement_environment:
            errors.append("live_settlement_enabled requires settlement_environment")
        if self.live_settlement_enabled and not self.settlement_security_review_id:
            errors.append("live_settlement_enabled requires settlement_security_review_id")
        if self.broadcast_enabled and not self.live_settlement_enabled:
            errors.append("broadcast_enabled requires live_settlement_enabled")
        if self.private_key_inputs_allowed:
            errors.append("private_key_inputs_allowed is prohibited")
        if self.compute_market_mode == "production_planning" and not self.audit_required:
            errors.append("audit_required=false is not allowed in production_planning mode")
        normalized_rate_backend = self.rate_limit_backend.strip().lower()
        normalized_circuit_backend = self.circuit_breaker_backend.strip().lower()
        if normalized_rate_backend not in {"memory", "in_memory", "redis", "none"}:
            errors.append("rate_limit_backend must be memory, redis, or none")
        if normalized_circuit_backend not in {"memory", "in_memory", "redis", "none"}:
            errors.append("circuit_breaker_backend must be memory, redis, or none")
        if self.compute_market_mode == "production_planning" and self.stripe_webhook_secret and len(self.stripe_webhook_secret) < 16:
            errors.append("stripe_webhook_secret must be high entropy when configured")
        return tuple(errors)

    def warnings(self) -> tuple[str, ...]:
        warnings: list[str] = []
        if self.compute_market_mode == "production_planning" and not self.metrics_enabled:
            warnings.append("metrics disabled in production_planning mode")
        if self.compute_market_mode == "production_planning" and not self.tracing_enabled:
            warnings.append("tracing disabled in production_planning mode")
        if not self.dry_run_required:
            warnings.append("dry_run_required=false should only be used after live settlement gates pass")
        return tuple(warnings)

    def as_record(self) -> dict[str, object]:
        return {
            "compute_market_enabled": self.compute_market_enabled,
            "compute_market_mode": self.compute_market_mode,
            "database_url": _redact_database_url(self.database_url),
            "storage_backend": self.storage_backend_effective,
            "storage_pool_size": self.storage_pool_size,
            "storage_timeout_ms": self.storage_timeout_ms,
            "storage_max_overflow": self.storage_max_overflow,
            "storage_statement_timeout_ms": self.storage_statement_timeout_ms,
            "postgres_ssl_mode": self.postgres_ssl_mode,
            "migrations_auto_run": self.migrations_auto_run,
            "require_managed_sql_in_production": self.require_managed_sql_in_production,
            "migrations_enabled": self.migrations_enabled,
            "rate_limit_backend": self.rate_limit_backend,
            "circuit_breaker_backend": self.circuit_breaker_backend,
            "redis_configured": bool(self.redis_url),
            "redis_prefix": self.redis_prefix,
            "rate_limit_enabled": self.rate_limit_enabled,
            "circuit_breaker_enabled": self.circuit_breaker_enabled,
            "rate_limit_fail_closed": self.rate_limit_fail_closed,
            "circuit_breaker_fail_closed": self.circuit_breaker_fail_closed,
            "provider_registry_mode": self.provider_registry_mode,
            "quote_cache_ttl": self.quote_cache_ttl,
            "provider_timeout_ms": self.provider_timeout_ms,
            "global_planning_timeout_ms": self.global_planning_timeout_ms,
            "max_candidate_routes": self.max_candidate_routes,
            "max_quote_cache_entries": self.max_quote_cache_entries,
            "dry_run_required": self.dry_run_required,
            "live_settlement_enabled": self.live_settlement_enabled,
            "broadcast_enabled": self.broadcast_enabled,
            "private_key_inputs_allowed": self.private_key_inputs_allowed,
            "audit_required": self.audit_required,
            "metrics_enabled": self.metrics_enabled,
            "tracing_enabled": self.tracing_enabled,
            "rate_limits_enabled": self.rate_limits_enabled,
            "external_provider_quotes_enabled": self.external_provider_quotes_enabled,
            "external_provider_quote_timeout_ms": self.external_provider_quote_timeout_ms,
            "external_provider_execution_enabled": self.external_provider_execution_enabled,
            "external_provider_execution_timeout_ms": self.external_provider_execution_timeout_ms,
            "economic_memory_writes_enabled": self.economic_memory_writes_enabled,
            "admin_mutations_enabled": self.admin_mutations_enabled,
            "audit_export_required": self.audit_export_required,
            "audit_export_configured": bool(self.audit_export_uri),
            "provider_contracts_required": self.provider_contracts_required,
            "provider_contracts_verified": self.provider_contracts_verified,
            "external_provider_allowlist_configured": bool(self.external_provider_allowlist),
            "settlement_environment_configured": bool(self.settlement_environment),
            "settlement_security_review_configured": bool(self.settlement_security_review_id),
            "stripe_webhook_secret_configured": bool(self.stripe_webhook_secret),
        }


def config_from_env(env: Mapping[str, str] | None = None) -> ComputeMarketConfig:
    source = env or os.environ
    return ComputeMarketConfig(
        compute_market_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_MARKET_ENABLED"), True),
        compute_market_mode=source.get("FLOW_MEMORY_COMPUTE_MARKET_MODE", "production_planning"),
        database_url=source.get(
            "FLOW_MEMORY_COMPUTE_DATABASE_URL",
            source.get("FLOW_MEMORY_COMPUTE_MARKET_DATABASE_URL", ".flow_memory/compute_market.sqlite3"),
        ),
        storage_backend=source.get("FLOW_MEMORY_COMPUTE_STORAGE_BACKEND", "sqlite"),
        storage_pool_size=_int(source.get("FLOW_MEMORY_COMPUTE_STORAGE_POOL_SIZE"), 4),
        storage_timeout_ms=_int(source.get("FLOW_MEMORY_COMPUTE_STORAGE_TIMEOUT_MS"), 5_000),
        storage_max_overflow=_int(source.get("FLOW_MEMORY_COMPUTE_STORAGE_MAX_OVERFLOW"), 4),
        storage_statement_timeout_ms=_int(source.get("FLOW_MEMORY_COMPUTE_STORAGE_STATEMENT_TIMEOUT_MS"), 5_000),
        postgres_ssl_mode=source.get("FLOW_MEMORY_COMPUTE_POSTGRES_SSL_MODE", "require"),
        migrations_auto_run=_bool(source.get("FLOW_MEMORY_COMPUTE_MIGRATIONS_AUTO_RUN"), True),
        require_managed_sql_in_production=_bool(source.get("FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION"), False),
        migrations_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_MIGRATIONS_ENABLED"), True),
        rate_limit_backend=source.get("FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND", "in_memory"),
        circuit_breaker_backend=source.get("FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND", "in_memory"),
        redis_url=source.get("FLOW_MEMORY_COMPUTE_REDIS_URL", ""),
        redis_prefix=source.get("FLOW_MEMORY_COMPUTE_REDIS_PREFIX", "flow-memory:compute-market"),
        rate_limit_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_RATE_LIMIT_ENABLED"), _bool(source.get("FLOW_MEMORY_COMPUTE_RATE_LIMITS_ENABLED"), True)),
        circuit_breaker_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_ENABLED"), True),
        rate_limit_fail_closed=_bool(source.get("FLOW_MEMORY_COMPUTE_RATE_LIMIT_FAIL_CLOSED"), True),
        circuit_breaker_fail_closed=_bool(source.get("FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_FAIL_CLOSED"), True),
        provider_registry_mode=source.get("FLOW_MEMORY_COMPUTE_PROVIDER_REGISTRY_MODE", "database"),
        quote_cache_ttl=_int(source.get("FLOW_MEMORY_COMPUTE_QUOTE_CACHE_TTL"), 300),
        provider_timeout_ms=_int(source.get("FLOW_MEMORY_COMPUTE_PROVIDER_TIMEOUT_MS"), 2_000),
        global_planning_timeout_ms=_int(source.get("FLOW_MEMORY_COMPUTE_GLOBAL_PLANNING_TIMEOUT_MS"), 10_000),
        max_candidate_routes=_int(source.get("FLOW_MEMORY_COMPUTE_MAX_CANDIDATE_ROUTES"), 64),
        max_quote_cache_entries=_int(source.get("FLOW_MEMORY_COMPUTE_MAX_QUOTE_CACHE_ENTRIES"), 10_000),
        dry_run_required=_bool(source.get("FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED"), True),
        live_settlement_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED"), False),
        broadcast_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED"), False),
        private_key_inputs_allowed=_bool(source.get("FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED"), False),
        audit_required=_bool(source.get("FLOW_MEMORY_COMPUTE_AUDIT_REQUIRED"), True),
        metrics_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_METRICS_ENABLED"), True),
        tracing_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_TRACING_ENABLED"), True),
        rate_limits_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_RATE_LIMITS_ENABLED"), True),
        external_provider_quotes_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED"), False),
        external_provider_quote_timeout_ms=_int(source.get("FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTE_TIMEOUT_MS"), 5_000),
        external_provider_execution_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_EXTERNAL_EXECUTION_ENABLED"), False),
        external_provider_execution_timeout_ms=_int(source.get("FLOW_MEMORY_COMPUTE_EXTERNAL_EXECUTION_TIMEOUT_MS"), 10_000),
        economic_memory_writes_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_ECONOMIC_MEMORY_WRITES_ENABLED"), True),
        admin_mutations_enabled=_bool(source.get("FLOW_MEMORY_COMPUTE_ADMIN_MUTATIONS_ENABLED"), True),
        audit_export_required=_bool(source.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_REQUIRED"), False),
        audit_export_uri=source.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI", ""),
        provider_contracts_required=_bool(source.get("FLOW_MEMORY_COMPUTE_PROVIDER_CONTRACTS_REQUIRED"), False),
        provider_contracts_verified=_bool(source.get("FLOW_MEMORY_COMPUTE_PROVIDER_CONTRACTS_VERIFIED"), False),
        external_provider_allowlist=_csv(source.get("FLOW_MEMORY_COMPUTE_EXTERNAL_PROVIDER_ALLOWLIST", "")),
        settlement_environment=source.get("FLOW_MEMORY_COMPUTE_SETTLEMENT_ENVIRONMENT", ""),
        settlement_security_review_id=source.get("FLOW_MEMORY_COMPUTE_SETTLEMENT_SECURITY_REVIEW_ID", ""),
        stripe_webhook_secret=source.get("FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_SECRET", ""),
    )


def ensure_database_parent(path: str) -> None:
    if path == ":memory:" or "://" in path:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv(value: str | None) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())

def _int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _redact_database_url(value: str) -> str:
    if "://" not in value:
        return value
    scheme, _, rest = value.partition("://")
    if "@" not in rest:
        return value
    return f"{scheme}://***@{rest.rsplit('@', 1)[-1]}"
