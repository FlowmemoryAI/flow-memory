import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const controller = readFileSync(new URL("../src/lib/replay-controller.ts", import.meta.url), "utf8");
const controls = readFileSync(new URL("../src/components/mission-control/ReplayControls.tsx", import.meta.url), "utf8");

assert.match(controller, /initialReplayState/);
assert.match(controller, /visibleReplayEvents/);
assert.match(controller, /stepReplay/);
assert.match(controller, /resetReplay/);
assert.match(controller, /replayProgress/);
assert.match(controller, /setReplayPlaying/);
assert.match(controller, /setReplaySpeed/);
assert.match(controller, /toggleReplayFilter/);
assert.match(controls, /Play/);
assert.match(controls, /Pause/);
assert.match(controls, /Reset/);
assert.match(controls, /Step forward/);
assert.match(controls, /Step backward/);
assert.match(controls, /Speed/);
console.log("mission control replay controls ok");
