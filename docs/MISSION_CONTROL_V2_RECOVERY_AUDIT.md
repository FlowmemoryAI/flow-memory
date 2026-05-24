# Mission Control V2 Recovery Audit

Date: 2026-05-24

Target worktree: `E:\FlowMemory\flow-memory-mission-control-v2`

Branch: `work/mission-control-visual-v2`

Baseline commit: `e72d2ba` or newer from `main`.

## Branch and worktree state

- The requested worktree was missing at the start of this recovery pass, so it was recreated from `main` at `e72d2ba` on branch `work/mission-control-visual-v2`.
- `main` was clean and already up to date before creating the worktree.
- This branch is isolated from `E:\FlowMemory\flow-memory`; all work in this pass is in the mission-control-v2 worktree.

## Baseline validation observed before edits

| Check | Result |
| --- | --- |
| `python -m pytest -q` | Pass: `532 passed, 17 skipped` |
| `bash scripts/verify.sh` | Failed in this new worktree because Git Bash selected `/usr/bin/python3`, which does not have `pytest`; Windows `python` worked for direct pytest. |
| `cd dashboard && npm test` | Failed because `dashboard/src/lib/mock-api.ts` was missing. |

The verify-script failure is an environment selection issue in the fresh worktree, not a Python package test failure. This pass will harden `scripts/verify.sh` for Windows Git Bash by preferring `python.exe` before `/usr/bin/python3` when no checked-in `.venv` exists.

## Mission Control pieces already present from main

Main already includes:

- `src/flow_memory/visualization/` with schema-versioned visual events, visual state dataclasses, reducer, snapshots, replay helpers, deterministic layout, and adapters for agent, memory, economy, neural, RL, safety, and audit signals.
- `src/flow_memory/api/visual_endpoints.py` and router registrations for `/visual/state`, `/visual/events`, `/visual/schema`, `/visual/replay/{run_id}`, `/network/state`, `/network/run-scenario`, and `/visual/replay/start`.
- Local network visual event emission for `basic-economy`, `neural-agent`, `rl-training`, `dispute-slashing`, `memory-learning`, and `safety-approval` scenarios.
- `scripts/export_visual_replay.py`, `scripts/validate_visual_replay.py`, `scripts/mission_control_demo_data.py`, and `examples/mission_control_visual_event_demo.py`.
- Dashboard Mission Control page/components and panel stubs under `dashboard/src/`.
- Replay controls scaffold in `dashboard/src/components/mission-control/ReplayControls.tsx` and controller logic in `dashboard/src/lib/replay-controller.ts`.
- Status docs: `docs/MISSION_CONTROL.md`, `docs/MISSION_CONTROL_QUICKSTART.md`, and `docs/MISSION_CONTROL_UX_AUDIT.md`.

Recent main commits relevant to this audit:

- `56a07c7` — preserved Mission Control replay-control polish.
- `c3ffdda` — refreshed Mission Control release evidence.
- `2abae11`, `8b7cbb1`, `1650eef`, `ef9f15f` — Mission Control launch/status, dashboard modes, replay validation, and local network visual work.
- `e72d2ba` — Squire layer and refreshed release evidence on top of the Mission Control baseline.

## Gaps found

### Reducer task-status overwrite bug

Found. The current reducer overwrites `VisualTaskNode` records unconditionally when another task event with the same `task_id` appears later. That can regress a settled task to an older/lower status such as `assigned` or `created` during replay reduction. Economy edges also overwrite by `edge_id` without state precedence metadata.

Required fix:

- Add explicit lifecycle precedence.
- Treat `settled` and `slashed` as terminal states.
- Allow only a valid later `disputed`/`slashed` path to override `settled` when explicitly sourced.
- Track ignored regressions in runtime metadata/warnings.

### Replay controls

Partially present. `ReplayControls.tsx` and `replay-controller.ts` exist, but the TypeScript support files they depend on are incomplete and dashboard tests currently fail before reaching replay-control assertions.

### Panels

Present but need hardening. Agent, neural, economy, RL, audit, and runtime panels exist. They already read visual state fields, but need stronger use of real field semantics, clearer empty/offline states, and support utilities under `dashboard/src/lib/visual-state.ts`.

### Mock/replay/live mode UX

Partially present. The Mission Control page references mock/replay/live concepts, but required dashboard library files are missing:

- `dashboard/src/lib/api.ts`
- `dashboard/src/lib/event-stream.ts`
- `dashboard/src/lib/visual-state.ts`
- `dashboard/src/lib/mock-api.ts`
- `dashboard/src/lib/openapi-types.ts`
- `dashboard/src/lib/mock-data.ts`

This prevents `npm test` from passing in the recovered branch.

### Demo replay data

Present, but it must be regenerated after reducer fixes so the dashboard replay reflects lifecycle precedence correctly and includes real local-network economy, neural, RL, safety, memory, and audit events.

## Recovery plan

1. Fix reducer lifecycle precedence and add regression tests.
2. Add missing dashboard library support files so `npm test` and `npm run build` pass.
3. Harden replay controls and panel state helpers around real visual fields.
4. Regenerate local network visual replay data.
5. Update Mission Control docs/status/build report with accurate V2 validation.
6. Run broad validation and push only `work/mission-control-visual-v2`.
