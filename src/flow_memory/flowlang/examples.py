"""Built-in FlowLang v0 examples."""

EXAMPLE_FLOWLANG = """# FlowLang v0 example agent
agent FlowResearcher
identity did:flow:researcher-001

memory:
  working_capacity: 7
  episodic: true
  semantic: true
  procedural: true
  economic: true
  adapters: [local]

belief: Verified memory is stronger than prompt-only context.
belief: Economic actions require provenance, policy, and audit.
goal: Produce grounded research briefs.
goal: Settle only verified local work.

policy safe-local:
  permissions: [respond, memory.read, audit.emit]
  risk: low
  requires_approval: false

policy economic-approval:
  permissions: [wallet.sign, marketplace.settle]
  risk: high
  requires_approval: true

skill research-brief:
  description: Produce a cited local research brief from memory and observations.
  permissions: [memory.read, audit.emit]
  risk: low

skill settle-verified-work:
  description: Request local marketplace settlement after verification.
  permissions: [wallet.sign, marketplace.settle]
  risk: high

plan daily-research:
  goal: Research and summarize one verified topic.
  steps: [research-brief]
  risk: low

economy:
  settlement: local
  budget: 5
  currency: FLOW
  marketplace: local
  allow_slashing: true
"""

INVALID_MISSING_POLICY = """agent UnsafeAgent
identity did:flow:unsafe
skill unsafe-writer:
  description: Writes memory without policy.
  permissions: [memory.write]
  risk: high
plan unsafe-plan:
  steps: [unsafe-writer]
"""
