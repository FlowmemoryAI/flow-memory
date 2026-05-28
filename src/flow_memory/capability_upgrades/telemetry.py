"""Visual telemetry event names for capability upgrades."""
CAPABILITY_UPGRADE_EVENTS = (
    "byok_provider_listed",
    "byok_credential_bound",
    "byok_credential_revoked",
    "byok_inference_intent_simulated",
    "x402_adapter_status_checked",
    "x402_route_prepared",
    "wallet_identity_bound",
    "onchain_upgrade_prepared",
    "onchain_upgrade_simulated",
    "onchain_upgrade_policy_reviewed",
    "onchain_upgrade_approved",
    "onchain_signature_requested",
    "onchain_relay_blocked",
    "emergency_stop_activated",
    "emergency_stop_cleared",
)

__all__ = ["CAPABILITY_UPGRADE_EVENTS"]
