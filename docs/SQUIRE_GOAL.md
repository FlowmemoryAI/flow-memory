# Squire Research Migration Note

This document is retained only as migration context from the earlier Squire/UsePod/Level5 research spike.

Public Flow Memory launch surfaces now use **Flow Memory Compute Market** terminology and endpoints:

- `docs/COMPUTE_MARKET.md`
- `skills/compute-market/SKILL.md`
- `python -m flow_memory compute ...`
- `/compute/*` local API endpoints

Do not present SQUIRE redemption, live UsePod/Level5 calls, live provider settlement, real funds, or mainnet payments as implemented Flow Memory behavior. The current implementation is deterministic local simulation with dry-run payment/settlement metadata only.
