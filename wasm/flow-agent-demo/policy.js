window.flowPolicy = { format: "flow-memory-tabular-q-v1", actions: ["execute", "request_approval", "choose_safer_plan"], select(state) { return state.safetyViolations > 0 ? 1 : 2; } };
