import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const mockApi = readFileSync(new URL("../src/lib/mock-api.ts", import.meta.url), "utf8");
const endpoints = readFileSync(new URL("../src/lib/openapi-types.ts", import.meta.url), "utf8");
const screens = readFileSync(new URL("../src/app/screens.ts", import.meta.url), "utf8");

assert.match(mockApi, /mockDashboardSnapshot/);
assert.match(mockApi, /release_evidence\/clean_clone_validation\.json/);
assert.match(endpoints, /\/flowlang\/run/);
assert.match(screens, /Base Sepolia dry-run status/);
assert.match(mockApi, /rlBenchmarks/);
assert.match(mockApi, /paymentFlows/);
assert.match(screens, /neural status/);
assert.match(screens, /local network scenarios/);
assert.match(screens, /Mission Control: live \/ replay \/ mock/);
assert.match(screens, /\/visual\/state/);
console.log("dashboard mock api ok");
