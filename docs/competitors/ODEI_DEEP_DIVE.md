# ODEI Deep Dive

## Overview
ODEI is a constitutional AI system with graph-native persistent memory. It emphasizes policy-gated actions, structural retrieval, and governed state management. The system uses Neo4j for memory and has a strong focus on auditability and provenance.

## Repository Structure

### MCP-ODEI (MCP Server)
```
mcp-odei/
├── src/
│   └── index.ts           # MCP server implementation
├── .github/workflows/     # CI/CD
├── package.json           # Dependencies: @modelcontextprotocol/sdk, zod
├── tsconfig.json
├── README.md
└── smithery.yaml          # Smithery configuration
```

### Memory (Documentation)
```
memory/
├── docs/
│   ├── architecture.md    # Neo4j schema, Guardian pipeline
│   ├── guardrails.md      # Policy enforcement
│   ├── quickstart.md      # Getting started
│   ├── schema.md          # Data schema
│   └── temporal-memory.md # Time-based memory
├── README.md
└── .github/workflows/     # Linting
```

### AgentKit (Integration Examples)
```
odei-agentkit/
└── README.md              # LangGraph/AgentKit integration docs
```

## Language & Stack Stats
- **TypeScript**: MCP server
- **Markdown**: Documentation
- **Neo4j**: Graph database (external)
- **Minimal code**: Mostly documentation

## Runtime Architecture
- **Neo4j**: Graph database for memory
- **Guardian pipeline**: Validation before writes
- **MCP server**: Protocol implementation
- **API**: api.odei.ai (production)

## Agent Execution Model
- **Policy-gated**: Actions validated before execution
- **Constitutional**: Writes checked against system invariants
- **Graph-native**: Relationships are first-class
- **Structured retrieval**: Query by structure, not just text

## Memory Model

### Neo4j Schema
- **Labels**: Entity, Type, Path, Anchor, Fact, Intent
- **Properties**: id, title, summary, description, status, layer, domain, type, tags, metadata
- **System Properties**: guardianVersion, guardianCallerOrigin, guardianEffectiveActor, constitutionalScore
- **Indexes**: Unique on id, type+status, layer, contentHash
- **Full-text search**: On title, summary, description
- **Vector index**: 3072 dimensions, cosine similarity

### Node Types
| Layer | Types |
|-------|-------|
| foundation | vision, business, area |
| strategy | strategy, objective, key_result, initiative |
| tactics | project, milestone, risk |
| execution | task, time_block, action |
| track | observation, artifact, experience |
| mind | context, principle |
| policy | guardrail, invariant |

### Guardian Pipeline
1. **Validation**: Check invariants before write
2. **Actor attribution**: Track who/what made changes
3. **Scoring**: Constitutional alignment score
4. **Attestation**: Reason for actor override
5. **Deduplication**: Content hash-based

## Policy/Safety Model
- **Constitutional**: Validates against system invariants
- **Guardian**: Pipeline for write validation
- **Actor tracking**: Human vs agent vs system
- **Sudo mode**: Co-founder override capability
- **Auditability**: All decisions reconstructable

## API Surface
- **api.odei.ai**: Production API
- **MCP server**: Local protocol access
- **GraphQL**: Neo4j graph queries

## MCP/A2A Support
- **MCP server**: ✅ Implemented
  - world model queries
  - guardrail checks
  - signal scoring
  - governed retrieval
- **A2A**: ❌ Not found

## Blockchain/Contracts
- **No blockchain integration**: Focus on AI governance
- **Web3 mentions**: Some skills reference web3

## Wallet/Payment/Reputation
- **No wallet system**
- **No payment system**
- **No reputation system**
- **Constitutional scoring**: Alignment score 0-1

## Scheduling/Autonomy
- **Daemon-based**: 17 daemons (2/17 healthy)
- **Reactive**: Signal-based triggers
- **Governed**: All actions pass through Guardian

## Self-Healing/Evaluation
- **Health checks**: Daemon monitoring
- **Signal scoring**: Confidence metrics
- **Constitutional scoring**: Value alignment

## Deployment Model
- **Cloud-based**: api.odei.ai
- **Local-first**: MCP server runs locally
- **Neo4j**: External graph database

## Test Coverage
- **Minimal**: No test files in repositories
- **Health checks**: Basic daemon monitoring

## Documentation Quality
- **Excellent architecture docs**: Detailed schema
- **Guardian documentation**: Clear pipeline explanation
- **API docs**: Available at api.odei.ai
- **Research papers**: Separate research repo

## Live System Status (as of 2026-05-22)
- **Graph nodes**: 21,890+ (production)
- **Node types**: 59
- **Relationship types**: 92
- **Domains**: 7
- **Daemons healthy**: 2/17
- **Grok x ODEI exchanges**: 11,162

## Implementation Depth Assessment
| Feature | Status |
|---------|--------|
| Graph-native memory | ✅ Implemented |
| Constitutional AI | ✅ Implemented |
| Policy enforcement | ✅ Implemented |
| MCP server | ✅ Implemented |
| Structured retrieval | ✅ Implemented |
| Auditability | ✅ Implemented |
| Actor tracking | ✅ Implemented |
| Neo4j schema | ✅ Implemented |
| Guardian pipeline | ✅ Implemented |
| Agent runtime | ❌ Missing |
| Blockchain | ❌ Missing |
| Economic layer | ❌ Missing |
| Skill system | ❌ Missing |
| A2A support | ❌ Missing |
| Self-healing | ⚠️ Partial |

## What Flow Memory Should Copy
1. **Graph-native memory**: Neo4j with structured relationships
2. **Constitutional AI**: Policy-gated actions
3. **Guardian pipeline**: Validation before writes
4. **Actor tracking**: Human vs agent attribution
5. **Structured retrieval**: Query by relationships
6. **Auditability**: Full provenance tracking
7. **Vector search**: 3072-dim embeddings

## What Flow Memory Should Avoid
1. **Documentation-only repos**: Minimal actual code
2. **External dependency**: Heavy reliance on Neo4j
3. **Low daemon health**: 2/17 healthy is concerning
4. **No economic layer**: Missing incentive structure

## What Flow Memory Should Surpass
1. **Local-first**: Works without external Neo4j
2. **Economic layer**: Token incentives for participation
3. **Agent runtime**: Full execution environment
4. **Skill system**: Composable capabilities
5. **Dual-stream perception**: Visual understanding
6. **A2A support**: Agent-to-agent protocol
7. **Self-healing**: Automatic recovery
8. **Open source governance**: DAO from day one

## Citations
- MCP Server: https://github.com/odei-ai/mcp-odei
- Memory Docs: https://github.com/odei-ai/memory
- AgentKit: https://github.com/odei-ai/odei-agentkit
- Website: https://odei.ai
- API: https://api.odei.ai
- Architecture: `memory/docs/architecture.md`
- Guardrails: `memory/docs/guardrails.md`