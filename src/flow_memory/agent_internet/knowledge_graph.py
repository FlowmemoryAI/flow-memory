"""Shared knowledge graph records."""
from flow_memory.agent_internet.core import KnowledgeArtifact, contribute_knowledge

CitationRewardIntent = dict
SharedFileIndexRecord = dict
KnowledgeContribution = KnowledgeArtifact

__all__ = ["KnowledgeArtifact", "KnowledgeContribution", "CitationRewardIntent", "SharedFileIndexRecord", "contribute_knowledge"]
