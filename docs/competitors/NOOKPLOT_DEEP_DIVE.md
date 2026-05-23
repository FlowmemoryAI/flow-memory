# Nookplot Deep Dive

## Overview
Nookplot is a decentralized AI agent social network with on-chain identity, knowledge publishing, and economic incentives. It positions itself as a platform for AI agents to collaborate, share knowledge, and earn rewards.

## Repository Structure
```
nookplot/
├── api/                    # API server (TypeScript)
│   ├── src/
│   │   ├── middleware/
│   │   ├── routes/
│   │   ├── services/       # 80+ services
│   │   └── test/
│   └── deployment/
├── cli/                    # Command line interface
├── contracts/              # Solidity smart contracts
│   ├── contracts/          # 20 contracts
│   └── test/               # Comprehensive test suite
├── gateway/                # Gateway server with 100+ routes
├── indexer/                # The Graph indexer
├── integrations/           # Third-party integrations
├── landing/                # Landing page
├── mcp-server/             # MCP server implementation
├── runtime/                # Agent runtime SDK
│   └── src/                # 40+ modules
├── runtime-py/             # Python runtime
├── schemas/                # Shared schemas
├── sdk/                    # TypeScript SDK
└── web/                    # Web frontend
```

## Language & Stack Stats
- **TypeScript**: 818 files (dominant)
- **JSON**: 58 files
- **Python**: 36 files
- **Markdown**: 34 files
- **Solidity**: 25 files
- **JavaScript**: 1 file
- **YAML**: 1 file

## Runtime Architecture
The Nookplot Runtime SDK provides:
- **ConnectionManager**: WebSocket connection with heartbeat
- **IdentityManager**: DID-based identity with Ethereum signing
- **MemoryBridge**: IPFS + on-chain knowledge publishing
- **EventManager**: Real-time event subscription
- **EconomyManager**: Token economics and staking
- **SocialManager**: Agent social graph
- **InboxManager**: Direct messaging between agents
- **ToolManager**: Tool registry and execution
- **ProactiveManager**: Scheduled/autonomous actions
- **SwarmManager**: Multi-agent coordination
- **PolicyManager**: Policy enforcement
- **OracleManager**: External data feeds
- **GpuManager**: GPU compute marketplace

## Agent Execution Model
- Agents connect via WebSocket to gateway
- Heartbeat every 30 seconds
- Actions signed with Ethereum private key
- Meta-transactions via ERC2771 forwarder
- IPFS for content, on-chain for indexing

## Memory Model
- **IPFS**: Content-addressed storage for knowledge
- **Subgraph**: Indexed on-chain data via The Graph
- **MemoryBridge**: Bidirectional sync between local and network
- **Knowledge bundles**: Grouped content with citations

## Policy/Safety Model
- **PolicyManager**: Runtime policy enforcement
- **ContentSafety**: Content scanning and moderation
- **HumanVerification**: Human-in-the-loop for critical actions
- **NetworkGuard**: Rate limiting and egress control
- **AuditLog**: Immutable action logging

## API Surface
- REST API with 100+ endpoints
- WebSocket for real-time events
- GraphQL via subgraph
- SDK for TypeScript and Python

## MCP/A2A Support
- **MCP Server**: Full implementation with 20+ tools
  - auth, memory, models, onchain, skills, swarms, tokens, workspaces
- **A2A**: Not explicitly found

## Blockchain/Contracts
- **20 Solidity contracts**:
  - AgentRegistry: DID-based agent identity
  - AgentFactory: Agent creation
  - ServiceMarketplace: Task marketplace
  - BountyContract: Bounty system
  - RewardPool: Staking rewards
  - RevenueRouter: Fee distribution
  - GpuAttestation: GPU verification
  - SocialGraph: Agent relationships
  - KnowledgeBundle: Content bundling
- **UUPS proxy pattern** for upgradeability
- **ERC2771** meta-transactions
- **ERC8004** token standard

## Wallet/Payment/Reputation
- **Smart wallet**: ERC-4337 account abstraction
- **Credits**: Off-chain credit system
- **Staking**: Token staking for reputation
- **Slashing**: Economic penalties
- **Reputation**: On-chain reputation tracking
- **Revenue sharing**: Automatic fee distribution

## Scheduling/Autonomy
- **ProactiveManager**: Scheduled actions
- **Heartbeat**: 30-second keepalive
- **Autonomous dispatch**: Action catalog with deduplication
- **GPU scheduling**: Compute job allocation

## Self-Healing/Evaluation
- **SelfImprovementEngine**: Skill optimization
- **QualityScorer**: Output quality scoring
- **SkillMatchingService**: Skill-agent matching
- **PerformanceTracker**: Performance monitoring

## Deployment Model
- Docker containers for API, gateway, indexer
- Cloudflare for CDN/edge
- IPFS for content storage
- The Graph for indexing

## Test Coverage
- **Comprehensive**: 20+ contract test files
- **Runtime tests**: Memory, autonomous, content safety
- **Gateway tests**: Auth, rate limiting, validation
- **Service tests**: Most services have test files

## Documentation Quality
- Good inline documentation
- README with examples
- SDK documentation
- Contract NatSpec comments

## Implementation Depth Assessment
| Feature | Status |
|---------|--------|
| On-chain identity | ✅ Implemented |
| Knowledge publishing | ✅ Implemented |
| Economic incentives | ✅ Implemented |
| Agent runtime SDK | ✅ Implemented |
| MCP server | ✅ Implemented |
| GPU marketplace | ✅ Implemented |
| Social graph | ✅ Implemented |
| Reputation system | ✅ Implemented |
| Policy engine | ✅ Implemented |
| Content safety | ✅ Implemented |
| A2A support | ❌ Missing |
| Local-first memory | ❌ Missing |
| Constitutional AI | ❌ Missing |
| Graph-native memory | ❌ Missing |

## What Flow Memory Should Copy
1. **Comprehensive contract suite**: 20 well-designed contracts
2. **Runtime SDK**: Multi-language SDK (TypeScript + Python)
3. **MCP server**: Full tool implementation
4. **Economic model**: Staking + slashing + revenue sharing
5. **Content safety**: Multi-layer content scanning
6. **Gateway architecture**: Scalable API gateway

## What Flow Memory Should Avoid
1. **Complexity**: 800+ TypeScript files is overwhelming
2. **Centralized gateway**: Heavy reliance on hosted gateway
3. **Token speculation**: Economic model could attract speculators
4. **IPFS dependency**: Content availability issues

## What Flow Memory Should Surpass
1. **Local-first**: Nookplot is cloud-dependent; Flow Memory should be local-first
2. **Constitutional AI**: Add policy-gated actions with explicit values
3. **Graph-native memory**: Neo4j instead of IPFS for structured memory
4. **A2A support**: Agent-to-agent protocol
5. **Appearance-invariant perception**: Dorsal stream for motion understanding
6. **Open source governance**: DAO from day one

## Citations
- Repository: https://github.com/nookprotocol/nookplot
- Documentation: https://nookplot.com/docs
- Contracts: `contracts/contracts/*.sol`
- Runtime: `runtime/src/*.ts`
- Gateway: `gateway/src/*.ts`
- MCP: `mcp-server/src/*.ts`