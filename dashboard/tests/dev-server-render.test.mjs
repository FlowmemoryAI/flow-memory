import assert from "node:assert/strict";
import { dashboardHtml, createMissionControlDevServer } from "../scripts/dev-server.mjs";

const html = dashboardHtml();

assert.match(html, /Mission Control Run Selector/);
assert.match(html, /Live Neural Agent Launch/);
assert.match(html, /Live Agent Operations/);
assert.match(html, /Live Agent Supervisor/);
assert.match(html, /Local Network Replay/);
assert.match(html, /Visible neural embodiment/);
assert.match(html, /Mission Control Live 3D Mode/);
assert.match(html, /GPU evidence verified/);
assert.match(html, /Public-alpha finalizer status/);
assert.match(html, /C:\\tmp backup/);
assert.match(html, /not tracked/);
assert.match(html, /Replay\/mock mode works without API/);
assert.doesNotMatch(html, /production frontend bundling remains a public-alpha next step/);
assert.doesNotMatch(html, /POST \/launch\//);
assert.doesNotMatch(html, /POST \/network\/run-scenario/);
assert.doesNotMatch(html, /POST \/compute\//);

const server = createMissionControlDevServer();
assert.equal(typeof server.listen, "function");
server.close();

console.log("mission control dev server renders real dashboard ok");
