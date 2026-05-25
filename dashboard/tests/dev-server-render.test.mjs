import assert from "node:assert/strict";
import http from "node:http";
import { dashboardHtml, createMissionControlDevServer, startMissionControlDevServer } from "../scripts/dev-server.mjs";

const html = dashboardHtml();

assert.match(html, /Mission Control Run Selector/);
assert.match(html, /Verified work becomes living memory/);
assert.match(html, /FlowMemory turns local agent runs/);
assert.match(html, /mission-brand-nav/);
assert.match(html, /mission-media-stage/);
assert.match(html, /mission-horizontal-accordion/);
assert.match(html, /mission-marquee/);
assert.match(html, /mission-proof-bento/);
assert.match(html, /mission-action-footer/);
assert.match(html, /data-motion="scrub-text"/);
assert.doesNotMatch(html, /Mission Control for verified work memory/);
assert.doesNotMatch(html, /mission-hero-metrics/);
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

async function listenAtOrAbove(startPort) {
  for (let candidate = startPort; candidate < startPort + 100; candidate += 1) {
    const candidateServer = http.createServer((_, res) => {
      res.writeHead(200, { "content-type": "text/plain" });
      res.end("occupied");
    });
    const started = await new Promise((resolve) => {
      candidateServer.once("error", () => resolve(false));
      candidateServer.listen(candidate, "127.0.0.1", () => resolve(true));
    });
    if (started) return { server: candidateServer, port: candidate };
  }
  throw new Error("No available local test port found");
}

const occupied = await listenAtOrAbove(31000);
const logs = [];
const started = await startMissionControlDevServer({
  port: occupied.port,
  host: "127.0.0.1",
  maxAttempts: 100,
  log: (message) => logs.push(message),
});
try {
  assert.notEqual(started.port, occupied.port);
  assert.match(logs.join("\n"), /already in use; trying/);
  const response = await fetch(started.url);
  assert.equal(response.status, 200);
  assert.match(await response.text(), /Verified work becomes living memory/);
} finally {
  started.server.close();
  occupied.server.close();
}

console.log("mission control dev server renders real dashboard ok");
