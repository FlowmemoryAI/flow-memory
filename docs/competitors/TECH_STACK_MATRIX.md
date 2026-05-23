# Tech Stack Matrix

## Competitor Technology Comparison

| Layer | Nookplot | AEON | ODEI | Flow Memory (Proposed) |
|-------|----------|------|------|------------------------|
| **Runtime** | TypeScript + Python | GitHub Actions + Node.js | TypeScript + Neo4j | Python + Rust |
| **AI Engine** | Custom runtime | Claude Code | Custom API | Pluggable (Kimi, GPT, Claude) |
| **Memory** | IPFS + Subgraph | Markdown files | Neo4j graph | Neo4j + Qdrant + Redis |
| **Working Memory** | N/A | MEMORY.md (markdown) | Neo4j (Intent nodes) | Redis (typed blackboard) |
| **Episodic Memory** | IPFS CIDs | logs/ (markdown) | Neo4j (Fact nodes) | Qdrant (vector + timeline) |
| **Semantic Memory** | Knowledge bundles | topics/ (markdown) | Neo4j (full graph) | Neo4j (knowledge graph) |
| **Policy Engine** | PolicyManager | None (Claude safety) | Guardian pipeline | OPA/Rego + custom |
| **Sandbox** | ContentSafety | GHA sandbox | None | Docker + gVisor |
| **MCP** | ✅ Full (20+ tools) | ⚠️ Scaffold | ✅ Implemented | ✅ Planned |
| **A2A** | ❌ Missing | ⚠️ Scaffold | ❌ Missing | ✅ Planned |
| **Blockchain** | ✅ Solidity (20 contracts) | ❌ Missing | ❌ Missing | ✅ Solidity planned |
| **Identity** | DID + Ethereum | GitHub identity | None | W3C DID |
| **Wallet** | Smart wallet (ERC-4337) | None | None | Smart wallet (ERC-4337) |
| **Reputation** | On-chain staking | None | Constitutional score | Non-transferable + staking |
| **Scheduling** | ProactiveManager | Cron (GitHub Actions) | Daemons | Cron + reactive triggers |
| **Perception** | None | None | None | Dual-stream (V-JEPA) |
| **Embodiment** | None | None | None | Habitat/MineDojo/Isaac |
| **Dashboard** | Web frontend | Next.js (local) | odei.ai | Planned |
| **Notifications** | Inbox + channels | Telegram/Discord/Slack | None | Planned |

## Language Distribution

| Project | TypeScript | Python | Solidity | Markdown | Other |
|---------|-----------|--------|----------|----------|-------|
| **Nookplot** | 818 (68%) | 36 (3%) | 25 (2%) | 34 (3%) | 288 (24%) |
| **AEON** | 32 (14%) | 5 (2%) | 0 | 162 (71%) | 29 (13%) |
| **ODEI** | 1 (5%) | 0 | 0 | 19 (95%) | 0 |
| **Flow Memory** | TBD | TBD | TBD | TBD | TBD |

## Package Managers & Build Tools

| Project | Package Manager | Build Tool | Test Runner | Linter |
|---------|----------------|------------|-------------|--------|
| **Nookplot** | npm (workspaces) | TypeScript | Vitest | ESLint |
| **AEON** | npm | Next.js | None | None |
| **ODEI** | npm | TypeScript | None | ESLint |
| **Flow Memory** | pip + cargo | setuptools + cargo | pytest | ruff + clippy |

## Database & Storage

| Project | Primary | Secondary | Vector | Cache |
|---------|---------|-----------|--------|-------|
| **Nookplot** | PostgreSQL (implied) | IPFS | None | Redis (implied) |
| **AEON** | Git repo (markdown) | None | None | None |
| **ODEI** | Neo4j | None | Neo4j (3072d) | None |
| **Flow Memory** | Neo4j | Qdrant | Qdrant | Redis |

## Infrastructure

| Project | Hosting | CDN | CI/CD | Monitoring |
|---------|---------|-----|-------|------------|
| **Nookplot** | Cloud (implied) | Cloudflare | GitHub Actions | Custom |
| **AEON** | GitHub Actions | None | GitHub Actions | None |
| **ODEI** | Cloud (api.odei.ai) | None | GitHub Actions | Basic health |
| **Flow Memory** | Docker + self-hosted | Planned | GitHub Actions | Planned |

## Key Insights

1. **Nookplot** is the most comprehensive with actual contracts and runtime
2. **AEON** prioritizes simplicity with markdown-based skills
3. **ODEI** focuses on memory architecture with minimal code
4. **Flow Memory** should combine the best of all three:
   - Nookplot's economic layer and contracts
   - AEON's skill system and autonomy
   - ODEI's graph-native memory and constitutional AI
   - Add unique features: dual-stream perception, local-first, A2A