# AEON Deep Dive

## Overview
AEON is an autonomous agent framework designed for unattended execution on GitHub Actions. It emphasizes self-healing, persistent memory, and reactive triggers. The framework uses Claude Code as its execution engine and operates without requiring human approval for most tasks.

## Repository Structure
```
aeon/
├── .github/workflows/      # GitHub Actions workflows
│   ├── aeon.yml           # Main skill runner
│   ├── chain-runner.yml   # Skill chaining
│   ├── messages.yml       # Notification handler
│   └── sync-upstream.yml  # Sync from upstream
├── .outputs/              # Chain step outputs
├── a2a-server/            # A2A server (minimal)
├── articles/              # Generated articles
├── assets/                # Images and media
├── dashboard/             # Next.js dashboard
│   ├── lib/
│   └── outputs/           # Rendered outputs
├── docs/                  # Documentation
├── examples/              # Example skills
├── images/                # Image assets
├── mcp-server/            # MCP server (minimal)
├── memory/                # Persistent memory
│   ├── logs/              # Daily activity logs
│   ├── topics/            # Topic files
│   └── issues/            # Issue tracker
├── scripts/               # Utility scripts
├── skills/                # 121 skills
│   ├── deep-research/
│   ├── morning-brief/
│   ├── pr-review/
│   └── ...
├── soul/                  # Personality files
│   ├── SOUL.md
│   └── STYLE.md
├── templates/             # Skill templates
└── workflows/             # Workflow definitions
```

## Language & Stack Stats
- **Markdown**: 162 files (dominant - skills are markdown)
- **TypeScript**: 32 files (dashboard, servers)
- **JSON**: 16 files
- **YAML**: 9 files (workflows, config)
- **Python**: 5 files

## Runtime Architecture
- **GitHub Actions**: Primary execution environment
- **Claude Code**: AI execution engine
- **Node.js 20+**: Dashboard runtime
- **GitHub CLI**: Repository operations

## Agent Execution Model
1. **Skill-based**: Each skill is a markdown file with instructions
2. **Scheduled**: Cron-based scheduling via `aeon.yml`
3. **Chained**: Skills can be chained with output passing
4. **Self-healing**: Detects failures and repairs skills
5. **Quality scoring**: Self-evaluates output quality

### Skill Structure
```markdown
---
name: Skill Name
description: What it does
var: "default value"
tags: [tag1, tag2]
---

## Steps
1. Do something
2. Do something else
```

## Skill/Tool System
- **121 skills** covering:
  - Research (deep-research, paper-digest)
  - Monitoring (token-alert, github-monitor)
  - Communication (telegram-digest, tweet-roundup)
  - Development (pr-review, code-health)
  - Analysis (market-context-refresh, narrative-tracker)
  - Self-improvement (skill-repair, self-improve)
- **Tool integration**: WebSearch, WebFetch, GitHub CLI
- **MCP server**: Minimal implementation
- **A2A server**: Minimal implementation

## Memory Model
- **MEMORY.md**: Index file (~50 lines)
- **topics/**: Detailed notes by topic
- **logs/**: Daily activity logs (YYYY-MM-DD.md)
- **issues/**: Structured issue tracker
  - INDEX.md: Open/resolved issues
  - ISS-{NNN}.md: Individual issues with YAML frontmatter
- **watched-repos.md**: Tracked repositories

### Memory Operations
- Read at start of every task
- Append logs after completion
- Consolidate during reflection

## Policy/Safety Model
- **Sandbox limitations**: GitHub Actions sandbox
- **Prefetch pattern**: Cache data before Claude runs
- **Post-process pattern**: Queue actions after Claude finishes
- **No explicit policy engine**: Relies on Claude's safety
- **Human approval**: Not required ("no babysitting")

## API Surface
- **Dashboard**: Next.js app at localhost:5555
- **API routes**: `/api/*` for secrets, workflow dispatch
- **GitHub Actions**: Workflow dispatch for skills
- **Notification channels**: Telegram, Discord, Slack

## MCP/A2A Support
- **MCP server**: Minimal (`aeon-mcp` package, only SDK dependency)
- **A2A server**: Minimal (empty package.json)
- **Implementation depth**: Scaffold only, not functional

## Blockchain/Contracts
- **No blockchain integration**: Pure GitHub Actions framework
- **Token mentions**: References to tokens in skills but no on-chain logic

## Wallet/Payment/Reputation
- **No wallet system**
- **No payment system**
- **No reputation system**
- **Cost tracking**: `cost-report` skill tracks API costs

## Scheduling/Autonomy Model
- **Cron-based**: `aeon.yml` defines schedules
- **Parallel execution**: Multiple skills can run simultaneously
- **Chain execution**: Sequential with output passing
- **Reactive triggers**: Issue labels, webhooks
- **Self-scheduling**: Skills can trigger other skills

### Schedule Examples
```yaml
morning-brief: { enabled: false, schedule: "0 7 * * *" }
pr-review: { enabled: false, schedule: "0 9 * * *" }
token-alert: { enabled: false, schedule: "0 12 * * *" }
```

## Self-Healing/Evaluation
- **skill-health**: Monitors skill success rates
- **skill-evals**: Evaluates output quality
- **skill-repair**: Fixes failing skills
- **self-improve**: Optimizes skill prompts
- **heartbeat**: Regular health checks
- **Issue tracker**: Structured issue management

### Quality Metrics
- Success rate tracking
- Output degradation detection
- Automatic skill patching

## Deployment Model
- **Zero infrastructure**: Runs on GitHub Actions
- **Fork-based**: Users fork the repo
- **Dashboard**: Local Next.js app
- **Secrets**: GitHub Secrets for API keys

## Test Coverage
- **Minimal**: No test files found
- **Validation**: `./onboard` script for setup verification
- **Smoke tests**: Some workflow validation

## Documentation Quality
- **Excellent README**: Comprehensive with comparisons
- **Skill documentation**: Each skill has SKILL.md
- **System prompt**: CLAUDE.md defines behavior
- **Showcase**: SHOWCASE.md with examples
- **Templates**: TEMPLATE.md for new skills

## Implementation Depth Assessment
| Feature | Status |
|---------|--------|
| Autonomous execution | ✅ Implemented |
| Skill system | ✅ Implemented (121 skills) |
| Persistent memory | ✅ Implemented |
| Self-healing | ✅ Implemented |
| Quality scoring | ✅ Implemented |
| Scheduling | ✅ Implemented |
| Notification system | ✅ Implemented |
| Dashboard | ✅ Implemented |
| Soul/personality | ✅ Implemented |
| MCP server | ⚠️ Scaffold only |
| A2A server | ⚠️ Scaffold only |
| Blockchain | ❌ Missing |
| Economic layer | ❌ Missing |
| Reputation | ❌ Missing |
| Policy engine | ❌ Missing |
| Sandboxed execution | ❌ Missing (relies on GHA) |

## What Flow Memory Should Copy
1. **Skill system**: Markdown-based skills are elegant
2. **Self-healing**: Automatic repair and quality scoring
3. **Memory structure**: Clear separation (index, topics, logs, issues)
4. **Soul system**: Personality files for voice matching
5. **Notification system**: Multi-channel with priority
6. **Dashboard**: Local UI for monitoring
7. **Zero infrastructure**: GitHub Actions deployment

## What Flow Memory Should Avoid
1. **GitHub Actions dependency**: Single vendor lock-in
2. **No sandboxing**: Relies on GHA sandbox limitations
3. **Minimal MCP/A2A**: Scaffold only, not functional
4. **No blockchain**: Missing economic layer
5. **Markdown-only skills**: Limited expressiveness

## What Flow Memory Should Surpass
1. **True sandboxing**: Docker-based isolated execution
2. **Functional MCP/A2A**: Full protocol implementation
3. **Blockchain integration**: On-chain identity and economics
4. **Policy engine**: Explicit policy enforcement
5. **Graph-native memory**: Neo4j instead of markdown files
6. **Dual-stream perception**: Visual understanding
7. **Constitutional AI**: Value-aligned actions
8. **Local-first**: Works without cloud dependencies

## Citations
- Repository: https://github.com/aaronjmars/aeon
- Website: https://www.aeon.fun/
- Skills: `skills/*/SKILL.md`
- Workflows: `.github/workflows/*.yml`
- Memory: `memory/MEMORY.md`
- System prompt: `CLAUDE.md`