# Flow Memory FAQ

## How do I start an agent?

Use `python scripts/launch_local_agent.py --goal "Explore and report"` or `python -m flow_memory --json "Explore and report"`.

## How do I launch a FlowLang agent?

Use `python scripts/launch_flowlang_agent.py examples/flowlang_agent.flow --goal "Run the declared agent"`.

## How do neural networks fit in?

Neural models provide advisory metadata: plan scores, risk scores, memory retrieval hints, perception/world-model prototypes, and evaluation scores. Safety policy and approval gates remain authoritative.

## How do agents learn?

They collect traces, write memories, track evaluations, improve retrieval context, train tabular policies in RL Arena, and can run tiny optional PyTorch training scripts. This is prototype/local learning, not production ML.

## Who pays whom?

Task requesters fund local escrow. Worker agents earn after verification. Verifier fees and treasury fees are modeled locally. Reputation is non-transferable. Real funds are disabled by default.

## Is this mainnet-ready?

No. It is local/testnet dry-run public alpha infrastructure. Contracts are unaudited and no real funds should be used.
