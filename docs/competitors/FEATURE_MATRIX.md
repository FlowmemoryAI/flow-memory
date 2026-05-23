# Feature Matrix

## Competitor Feature Comparison

### Core Agent Capabilities

| Feature | Nookplot | AEON | ODEI | Flow Memory |
|---------|----------|------|------|-------------|
| **Autonomous Execution** | ✅ | ✅ | ⚠️ | ✅ |
| **Skill System** | ✅ (tools) | ✅ (121 skills) | ❌ | ✅ |
| **Memory** | ✅ (IPFS) | ✅ (markdown) | ✅ (graph) | ✅ (layered) |
| **Working Memory** | ❌ | ⚠️ (simple) | ✅ (Intent) | ✅ |
| **Episodic Memory** | ⚠️ (CIDs) | ✅ (logs) | ✅ (Fact) | ✅ |
| **Semantic Memory** | ✅ (bundles) | ⚠️ (topics) | ✅ (full graph) | ✅ |
| **Procedural Memory** | ❌ | ✅ (skills) | ❌ | ✅ |
| **Economic Memory** | ✅ | ❌ | ❌ | ✅ |

### Perception & Understanding

| Feature | Nookplot | AEON | ODEI | Flow Memory |
|---------|----------|------|------|-------------|
| **Text Understanding** | ✅ | ✅ | ✅ | ✅ |
| **Visual Perception** | ❌ | ❌ | ❌ | ✅ (dual-stream) |
| **Motion Understanding** | ❌ | ❌ | ❌ | ✅ (dorsal stream) |
| **3D Scene Understanding** | ❌ | ❌ | ❌ | ✅ |
| **Audio Processing** | ❌ | ❌ | ❌ | ⚠️ |
| **Multi-modal** | ❌ | ❌ | ❌ | ✅ |

### Action & Execution

| Feature | Nookplot | AEON | ODEI | Flow Memory |
|---------|----------|------|------|-------------|
| **Tool Use** | ✅ | ✅ | ⚠️ (MCP) | ✅ |
| **Sandboxed Execution** | ⚠️ | ❌ | ❌ | ✅ |
| **Policy Gating** | ✅ | ❌ | ✅ | ✅ |
| **Human Approval** | ✅ | ❌ | ❌ | ✅ |
| **Chain of Skills** | ❌ | ✅ | ❌ | ✅ |
| **Parallel Execution** | ❌ | ✅ | ❌ | ✅ |

### Communication

| Feature | Nookplot | AEON | ODEI | Flow Memory |
|---------|----------|------|------|-------------|
| **MCP Support** | ✅ | ⚠️ | ✅ | ✅ |
| **A2A Support** | ❌ | ⚠️ | ❌ | ✅ |
| **Agent Messaging** | ✅ (inbox) | ❌ | ❌ | ✅ |
| **Notifications** | ✅ | ✅ | ❌ | ✅ |
| **Social Graph** | ✅ | ❌ | ❌ | ✅ |

### Economics & Incentives

| Feature | Nookplot | AEON | ODEI | Flow Memory |
|---------|----------|------|------|-------------|
| **Blockchain** | ✅ | ❌ | ❌ | ✅ |
| **Smart Contracts** | ✅ (20) | ❌ | ❌ | ✅ |
| **Token System** | ✅ | ❌ | ❌ | ✅ |
| **Staking** | ✅ | ❌ | ❌ | ✅ |
| **Slashing** | ✅ | ❌ | ❌ | ✅ |
| **Task Marketplace** | ✅ | ❌ | ❌ | ✅ |
| **Reputation** | ✅ | ❌ | ⚠️ | ✅ |
| **Revenue Sharing** | ✅ | ❌ | ❌ | ✅ |

### Safety & Governance

| Feature | Nookplot | AEON | ODEI | Flow Memory |
|---------|----------|------|------|-------------|
| **Content Safety** | ✅ | ❌ | ❌ | ✅ |
| **Policy Engine** | ✅ | ❌ | ✅ | ✅ |
| **Constitutional AI** | ❌ | ❌ | ✅ | ✅ |
| **Audit Logs** | ✅ | ⚠️ (logs) | ✅ | ✅ |
| **Rate Limiting** | ✅ | ❌ | ❌ | ✅ |
| **Circuit Breakers** | ❌ | ❌ | ❌ | ✅ |

### Self-Improvement

| Feature | Nookplot | AEON | ODEI | Flow Memory |
|---------|----------|------|------|-------------|
| **Self-Healing** | ✅ | ✅ | ⚠️ | ✅ |
| **Quality Scoring** | ✅ | ✅ | ✅ | ✅ |
| **Skill Repair** | ❌ | ✅ | ❌ | ✅ |
| **Auto-Optimization** | ✅ | ✅ | ❌ | ✅ |
| **Learning from Feedback** | ⚠️ | ⚠️ | ❌ | ✅ |

### Deployment & Infrastructure

| Feature | Nookplot | AEON | ODEI | Flow Memory |
|---------|----------|------|------|-------------|
| **Docker** | ✅ | ❌ | ❌ | ✅ |
| **Local-First** | ❌ | ⚠️ | ⚠️ | ✅ |
| **Cloud-Native** | ✅ | ✅ | ✅ | ✅ |
| **Self-Hosted** | ⚠️ | ✅ | ❌ | ✅ |
| **Zero Infrastructure** | ❌ | ✅ | ❌ | ❌ |

## Feature Coverage Summary

| Project | Implemented | Scaffold | Missing | Coverage |
|---------|-------------|----------|---------|----------|
| **Nookplot** | 18 | 2 | 12 | 56% |
| **AEON** | 14 | 4 | 14 | 44% |
| **ODEI** | 10 | 2 | 20 | 31% |
| **Flow Memory (Target)** | 32 | 0 | 0 | 100% |

## Unique Differentiators

### Nookplot
- Most comprehensive blockchain integration
- GPU marketplace
- Social graph for agents
- Knowledge bundles with citations

### AEON
- 121 pre-built skills
- Self-healing with issue tracker
- Zero infrastructure (GitHub Actions)
- Soul/personality system

### ODEI
- Graph-native memory (Neo4j)
- Constitutional AI with Guardian pipeline
- Structured retrieval
- Actor attribution

### Flow Memory (Planned)
- Dual-stream perception (unique)
- Appearance-invariant motion (unique)
- Layered memory system
- Local-first architecture
- Economic autonomy
- Policy-gated actions
- A2A + MCP support
- Docker sandboxing