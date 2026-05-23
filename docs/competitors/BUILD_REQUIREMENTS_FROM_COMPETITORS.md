# Build Requirements from Competitors

## Top 25 Build Requirements

### Critical (Must Have for MVP)

1. **Cognitive Kernel** (from AEON + Nookplot)
   - Typed agent loop: perceive → predict → remember → reason → act → evaluate → learn → transact
   - Event-driven architecture
   - State machine for agent lifecycle

2. **Working Memory** (from AEON + ODEI)
   - Typed blackboard with capacity limits (7 items)
   - Redis backend for speed
   - Automatic eviction policies

3. **Episodic Memory** (from ODEI + AEON)
   - Timeline-based event log
   - Vector embedding for similarity search
   - Qdrant backend

4. **Semantic Memory** (from ODEI)
   - Neo4j graph database
   - Typed relationships (not just text)
   - Structural queries

5. **Skill System** (from AEON)
   - Markdown-based skill definitions
   - Python/TypeScript implementation
   - Version control friendly

6. **Tool Registry** (from Nookplot)
   - MCP-compatible tool server
   - Sandboxed execution
   - Plugin architecture

7. **Safety Sandbox** (from Nookplot)
   - Docker containerization
   - gVisor for additional isolation
   - Resource limits (CPU, memory, network)

8. **Policy Engine** (from ODEI + Nookplot)
   - OPA/Rego rules
   - Constitutional values
   - Pre-execution validation

9. **Human Approval Gate** (from Nookplot)
   - Configurable approval thresholds
   - Notification system
   - Emergency stop

10. **Audit Logging** (from ODEI + Nookplot)
    - Immutable log chain
    - Content hashing
    - Actor attribution

### High Priority (Beta)

11. **Agent Identity (DID)** (from Nookplot)
    - W3C DID standard
    - Ethereum-compatible
    - Self-sovereign

12. **Smart Wallet** (from Nookplot)
    - ERC-4337 account abstraction
    - Meta-transactions
    - Gasless operations

13. **Task Marketplace** (from Nookplot)
    - Bid/ask system
    - Escrow contracts
    - Dispute resolution

14. **Reputation System** (from Nookplot + ODEI)
    - Non-transferable reputation
    - Staking mechanism
    - Slashing conditions

15. **MCP Server** (from Nookplot + ODEI)
    - Full protocol implementation
    - 20+ tools
    - Authentication

16. **A2A Server** (gap in all competitors)
    - Agent-to-agent protocol
    - Capability discovery
    - Message routing

17. **Self-Healing** (from AEON)
    - Health monitoring
    - Automatic repair
    - Issue tracking

18. **Quality Scoring** (from AEON)
    - Output evaluation
    - Degradation detection
    - Automatic optimization

19. **Notification System** (from AEON + Nookplot)
    - Multi-channel (Telegram, Discord, Slack)
    - Priority routing
    - Batch processing

20. **Dashboard** (from AEON)
    - Next.js frontend
    - Real-time monitoring
    - Skill management

### Medium Priority (Production)

21. **Dual-Stream Perception** (unique to Flow Memory)
    - Ventral stream (what)
    - Dorsal stream (where/how)
    - Appearance-invariant motion

22. **Predictive World Model** (unique to Flow Memory)
    - V-JEPA integration
    - Free energy minimization
    - Surprise detection

23. **Multi-Agent Swarm** (from Nookplot)
    - Agent discovery
    - Coalition formation
    - Consensus mechanisms

24. **Embodiment** (gap in all competitors)
    - Habitat simulation
    - MineDojo integration
    - Robotics adapter

25. **DAO Governance** (from Nookplot)
    - Token voting
    - Proposal system
    - Treasury management

## Top 10 Architectural Decisions

1. **Modular Monolith**: Single deployable with clear seams
2. **Python + Rust**: Python for AI, Rust for performance
3. **Layered Memory**: Multiple backends for different access patterns
4. **Optional Blockchain**: Additive, not required
5. **Markdown + Code Skills**: Simple definitions, powerful implementations
6. **Docker-First**: Local development, easy deployment
7. **Pluggable AI**: Support multiple models (Kimi, GPT, Claude)
8. **Local-First**: Works offline, syncs optionally
9. **Policy-First**: Safety before functionality
10. **Open Source**: Apache-2.0, community-driven

## Top 10 Risks

1. **Complexity**: Scope creep could delay MVP
2. **Performance**: AI models are resource-intensive
3. **Security**: Sandboxing must be bulletproof
4. **Adoption**: Competing against established players
5. **Token Regulation**: Legal uncertainty around tokens
6. **Model Dependency**: AI provider changes could break system
7. **Data Privacy**: User data handling requirements
8. **Scalability**: From single agent to swarm
9. **Maintenance**: Long-term support burden
10. **Community**: Building open source community

## Concrete Backlog

### Sprint 1: Foundation
- [ ] Project scaffolding
- [ ] Docker setup
- [ ] CI/CD pipeline
- [ ] Basic agent loop

### Sprint 2: Memory
- [ ] Working memory (Redis)
- [ ] Episodic memory (Qdrant)
- [ ] Semantic memory (Neo4j)
- [ ] Memory consolidation

### Sprint 3: Safety
- [ ] Policy engine (OPA)
- [ ] Sandbox (Docker)
- [ ] Approval gate
- [ ] Audit logging

### Sprint 4: Skills
- [ ] Skill registry
- [ ] 10 basic skills
- [ ] MCP server
- [ ] Tool execution

### Sprint 5: Economy
- [ ] DID system
- [ ] Smart wallet
- [ ] Testnet contracts
- [ ] Reputation system

### Sprint 6: Perception
- [ ] Ventral stream
- [ ] Dorsal stream
- [ ] World model
- [ ] Foveation

### Sprint 7: Coordination
- [ ] A2A server
- [ ] Agent discovery
- [ ] Swarm formation
- [ ] Consensus

### Sprint 8: Polish
- [ ] Dashboard
- [ ] Documentation
- [ ] Examples
- [ ] Tests

## Exact Citations

### Nookplot
- Repository: https://github.com/nookprotocol/nookplot
- Runtime SDK: `runtime/src/index.ts` (lines 1-80)
- Contracts: `contracts/contracts/AgentRegistry.sol` (lines 1-80)
- MCP Server: `mcp-server/src/index.ts` (lines 1-80)
- Gateway: `gateway/src/server.ts` (lines 1-80)

### AEON
- Repository: https://github.com/aaronjmars/aeon
- Skills: `skills/deep-research/SKILL.md` (lines 1-80)
- Memory: `memory/MEMORY.md` (lines 1-80)
- Workflows: `.github/workflows/aeon.yml` (lines 1-80)
- System Prompt: `CLAUDE.md` (lines 1-80)

### ODEI
- MCP Server: https://github.com/odei-ai/mcp-odei
- Memory Docs: https://github.com/odei-ai/memory
- Architecture: `memory/docs/architecture.md` (lines 1-100)
- API: https://api.odei.ai