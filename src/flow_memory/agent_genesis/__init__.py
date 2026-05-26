"""Agent Genesis: birth, genome, consent, and network learning protocol."""
from flow_memory.agent_genesis.archetypes import AgentArchetype, get_archetype, list_archetypes
from flow_memory.agent_genesis.boundaries import AgentBoundary, compile_boundaries, get_boundary, list_boundaries
from flow_memory.agent_genesis.birth import AgentBirthCertificate, CreateAgentBirthRequest, birth_agent, first_prediction_ceremony, get_birth_certificate
from flow_memory.agent_genesis.consent import NetworkLearningConsent, create_consent, get_consent
from flow_memory.agent_genesis.contribution import NetworkContribution, create_contribution, export_contribution_bundle, list_contributions, sanitize_contribution, validate_contribution
from flow_memory.agent_genesis.genome import AgentGenome, create_genome, export_genome, fork_genome, genome_to_agent_profile, get_genome, import_genome, validate_genome
from flow_memory.agent_genesis.instincts import AgentInstinct, get_instinct, list_instincts, merge_instinct_profiles
from flow_memory.agent_genesis.memory_seed import MemorySeed, create_memory_seed, get_memory_seed
from flow_memory.agent_genesis.mirror import AgentMirror, build_mirror, get_mirror
from flow_memory.agent_genesis.passport import AgentPassport, build_passport, get_passport
from flow_memory.agent_genesis.stages import STAGES, calculate_stage
from flow_memory.agent_genesis.teaching import TeachingEvent, create_teaching_event, list_teaching_events, write_teaching_event

__all__ = [
    "AgentArchetype",
    "AgentBirthCertificate",
    "AgentBoundary",
    "AgentGenome",
    "AgentInstinct",
    "AgentMirror",
    "AgentPassport",
    "CreateAgentBirthRequest",
    "MemorySeed",
    "NetworkContribution",
    "NetworkLearningConsent",
    "STAGES",
    "TeachingEvent",
    "birth_agent",
    "build_mirror",
    "build_passport",
    "calculate_stage",
    "compile_boundaries",
    "create_consent",
    "create_contribution",
    "create_genome",
    "create_memory_seed",
    "create_teaching_event",
    "export_contribution_bundle",
    "export_genome",
    "first_prediction_ceremony",
    "fork_genome",
    "genome_to_agent_profile",
    "get_archetype",
    "get_birth_certificate",
    "get_boundary",
    "get_consent",
    "get_genome",
    "get_instinct",
    "get_memory_seed",
    "get_mirror",
    "get_passport",
    "import_genome",
    "list_archetypes",
    "list_boundaries",
    "list_contributions",
    "list_instincts",
    "list_teaching_events",
    "merge_instinct_profiles",
    "sanitize_contribution",
    "validate_contribution",
    "validate_genome",
    "write_teaching_event",
]
