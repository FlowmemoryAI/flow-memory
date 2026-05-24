import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../src/app/mission-control/page.tsx", import.meta.url), "utf8");
const canvas = readFileSync(new URL("../src/components/mission-control/MissionControlCanvas.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/lib/api.ts", import.meta.url), "utf8");
const replay = JSON.parse(readFileSync(new URL("../src/mock-data/local-network-replay.json", import.meta.url), "utf8"));
const config = readFileSync(new URL("../src/lib/mission-control-config.ts", import.meta.url), "utf8");

assert.match(page, /The Human Compute Network/);
assert.match(canvas, /AgentNode3D/);
assert.match(canvas, /EconomyEdge/);
assert.match(canvas, /SafetyGate3D/);
assert.match(api, /\/visual\/state/);
assert.match(api, /\/network\/run-scenario/);
assert.match(config, /live local API/);
assert.match(config, /visualFieldMappings/);
assert.match(config, /network:run/);
assert.equal(replay.ok, true);
assert.ok(replay.state.agents.length >= 4);
assert.ok(replay.state.tasks.length >= 1);
console.log("mission control dashboard scaffold ok");
