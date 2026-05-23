"""FlowIR public contracts."""

from flow_memory.ir.agent import AgentSpec
from flow_memory.ir.compiler import CompileResult, compile_agent, manifest_json
from flow_memory.ir.economy import EconomicSpec
from flow_memory.ir.manifest import (
    FLOWIR_SCHEMA_VERSION,
    FLOWIR_SIGNATURE_ALGORITHM,
    ManifestEnvelope,
    ManifestSignature,
    SignedManifestEnvelope,
    canonical_json,
    envelope_manifest,
    manifest_digest,
    sign_manifest,
    verify_manifest_signature,
)
from flow_memory.ir.memory import MemorySpec
from flow_memory.ir.plan import PlanSpec
from flow_memory.ir.policy import PermissionSpec, PolicySpec, RiskLevel, is_unsafe_permission
from flow_memory.ir.skill import SkillSpec

__all__ = [
    "AgentSpec",
    "CompileResult",
    "EconomicSpec",
    "FLOWIR_SCHEMA_VERSION",
    "FLOWIR_SIGNATURE_ALGORITHM",
    "ManifestEnvelope",
    "ManifestSignature",
    "MemorySpec",
    "PermissionSpec",
    "PlanSpec",
    "PolicySpec",
    "RiskLevel",
    "SignedManifestEnvelope",
    "SkillSpec",
    "canonical_json",
    "compile_agent",
    "envelope_manifest",
    "is_unsafe_permission",
    "manifest_digest",
    "manifest_json",
    "sign_manifest",
    "verify_manifest_signature",
]
