import assert from "node:assert/strict";
import http from "node:http";
import { dashboardHtml, createMissionControlDevServer, startMissionControlDevServer } from "../scripts/dev-server.mjs";

const html = dashboardHtml();

assert.match(html, /Mission Control Run Selector/);
assert.match(html, /Human compute becomes memory/);
assert.match(html, /mission-hero-simple-3d/);
assert.match(html, /mission-3d-visualizer/);
assert.match(html, /mission-3d-canvas/);
assert.match(html, /data-3d-mode="swarm"/);
assert.match(html, /Signal field/);
assert.match(html, /Neural braid/);
assert.match(html, /Memory loom/);
assert.match(html, /A calmer neural strand visualization/);
assert.match(html, /Neural loom/);
assert.match(html, /Signals appear/);
assert.match(html, /Fibers converge/);
assert.match(html, /Memory is woven/);
assert.match(html, /Neural braid forming/);
assert.match(html, /data-story-mode="swarm"/);
assert.match(html, /mission-3d-story-readout/);
assert.match(html, /mission-story-steps/);
assert.match(html, /mission-loom-rail/);
assert.match(html, /data-neural-strands="loom"/);
assert.match(html, /mission-brand-nav/);
assert.match(html, /mission-action-footer/);
assert.match(html, /data-motion="scrub-text"/);
assert.match(html, /\/vendor\/gsap\.min\.js/);
assert.match(html, /\/vendor\/ScrollTrigger\.min\.js/);
assert.match(html, /\/vendor\/three\.module\.js/);
assert.match(html, /gsap\.registerPlugin\(ScrollTrigger\)/);
assert.match(html, /new THREE\.WebGLRenderer/);
assert.match(html, /window\.__flowMemory3DReady = true/);
assert.match(html, /new THREE\.CatmullRomCurve3/);
assert.match(html, /new THREE\.TubeGeometry/);
assert.match(html, /vertexColors: true/);
assert.match(html, /strandPulses/);
assert.doesNotMatch(html, /Interactive memory field/);
assert.doesNotMatch(html, /Loading interactive memory field/);
assert.doesNotMatch(html, /mission-inline-image/);
assert.doesNotMatch(html, /mission-media-stage/);
assert.doesNotMatch(html, /mission-horizontal-accordion/);
assert.doesNotMatch(html, /mission-marquee/);
assert.doesNotMatch(html, /mission-proof-bento/);
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
assert.match(html, /Predictive Cognitive Core/);
assert.match(html, /prediction matched reality/i);
assert.match(html, /Predictive Cognition/);
assert.match(html, /Counterfactual predictions/);
assert.match(html, /PolicyEngine and ApprovalGate remain authoritative/);
assert.match(html, /Predictive Learning Benchmark/);
assert.match(html, /Prediction error drops after lessons consolidate/);
assert.match(html, /Benchmark scenarios/);
assert.match(html, /Accuracy and error trend/);
assert.match(html, /Selected lesson details/);
assert.match(html, /repeated mistakes reduced/);
assert.match(html, /Lessons never bypass PolicyEngine or ApprovalGate/);
assert.match(html, /Agent Genesis/);
assert.match(html, /Birth an agent into the network/);
assert.match(html, /Agent Birth Flow/);
assert.match(html, /Agent Genome/);
assert.match(html, /Memory Seed/);
assert.match(html, /Learning Consent/);
assert.match(html, /First Prediction/);
assert.match(html, /Agent Mirror/);
assert.match(html, /Agent Passport/);
assert.match(html, /Network learning is opt-in/);
assert.match(html, /raw private payload/);
assert.match(html, /Node download is optional/);
assert.match(html, /Birth an agent from the dashboard/);
assert.match(html, /agent-genesis-create-form/);
assert.match(html, /Birth agent online/);
assert.match(html, /POST \/genesis\/birth/);
assert.match(html, /no wallet required/);
assert.match(html, /Agent Internet/);
assert.match(html, /Agent Skill Matcher/);
assert.match(html, /Collaboration Graph/);
assert.match(html, /Shared Cognitive Workspace/);
assert.match(html, /x402 dry-run payment intent/);
assert.match(html, /ERC-8004 export-only adapter/);
assert.match(html, /MCP manifest policy-gated/);
assert.match(html, /raw private memory excluded/);
assert.match(html, /GET \/internet\/agents/);
assert.match(html, /BYOK \+ On-chain Upgrades/);
assert.match(html, /BYOK Model Keys/);
assert.match(html, /x402 testnet route/);
assert.match(html, /Coinbase CDP facilitator/);
assert.match(html, /x402\.org testnet facilitator/);
assert.match(html, /x402\[fastapi,httpx,evm\]>=2\.11\.0/);
assert.match(html, /eip155:84532/);
assert.match(html, /On-chain Agent Upgrade/);
assert.match(html, /Wallet Binding/);
assert.match(html, /no wallet\/API key\/funds required for first agent/);
assert.match(html, /raw API key not persisted/);
assert.match(html, /key fingerprint only/);
assert.match(html, /Base Sepolia default/);
assert.match(html, /mainnet writes disabled/);
assert.match(html, /relay disabled by default/);
assert.match(html, /no seed phrases/);
assert.match(html, /no transaction broadcast/);
assert.match(html, /emergency stop/);
assert.match(html, /Flow Memory Forge/);
assert.match(html, /Create your first Flow Memory agent/);
assert.match(html, /flow-memory-forge-form/);
assert.match(html, /Capability Composer/);
assert.match(html, /Simple mode/);
assert.match(html, /Advanced mode/);
assert.match(html, /POST \/forge\/birth/);
assert.match(html, /GET \/forge\/defaults/);
assert.match(html, /\/forge/);
assert.match(html, /\/agents\/new/);
assert.match(html, /Private by default/);
assert.match(html, /Network learning is opt-in/);
assert.match(html, /BYOK model key/);
assert.match(html, /Wallet identity/);
assert.match(html, /On-chain dry run/);
assert.match(html, /x402 dry-run route/);
assert.match(html, /Publish Agent Internet identity/);
assert.match(html, /Find collaborators/);
assert.match(html, /read-only demo mode/);
assert.match(html, /Proof of Learning/);
assert.match(html, /Experience Graph/);
assert.match(html, /Every prediction becomes experience/);
assert.match(html, /proof-learning-panel/);
assert.match(html, /private payload excluded/);
assert.match(html, /GET \/experience-graph/);
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
  const servedHtml = await response.text();
  assert.match(servedHtml, /Human compute becomes memory/);
  assert.match(servedHtml, /mission-3d-canvas/);
  assert.match(servedHtml, /Flow Memory Forge/);
  const forgeResponse = await fetch(new URL("/forge", started.url));
  assert.equal(forgeResponse.status, 200);
  assert.match(await forgeResponse.text(), /Create your first Flow Memory agent/);
  const agentsNewResponse = await fetch(new URL("/agents/new", started.url));
  assert.equal(agentsNewResponse.status, 200);
  assert.match(await agentsNewResponse.text(), /Capability Composer/);
  const forgeDefaultsResponse = await fetch(new URL("/forge/defaults", started.url));
  assert.equal(forgeDefaultsResponse.status, 200);
  const forgeDefaultsPayload = await forgeDefaultsResponse.json();
  assert.equal(forgeDefaultsPayload.ok, true);
  assert.equal(forgeDefaultsPayload.data.summary.first_agent_requires_wallet, false);
  const gsapResponse = await fetch(new URL("/vendor/gsap.min.js", started.url));
  assert.equal(gsapResponse.status, 200);
  assert.match(await gsapResponse.text(), /GSAP/);
  const triggerResponse = await fetch(new URL("/vendor/ScrollTrigger.min.js", started.url));
  assert.equal(triggerResponse.status, 200);
  assert.match(await triggerResponse.text(), /ScrollTrigger/);
  const threeResponse = await fetch(new URL("/vendor/three.module.js", started.url));
  assert.equal(threeResponse.status, 200);
  assert.match(await threeResponse.text(), /class WebGLRenderer/);
  const threeCoreResponse = await fetch(new URL("/vendor/three.core.js", started.url));
  assert.equal(threeCoreResponse.status, 200);
  assert.match(await threeCoreResponse.text(), /class Vector3/);
  const graphResponse = await fetch(new URL("/experience-graph", started.url));
  assert.equal(graphResponse.status, 200);
  const graphPayload = await graphResponse.json();
  assert.equal(graphPayload.ok, true);
  assert.match(JSON.stringify(graphPayload), /Proof of Learning|Experience Graph/);
  const proofResponse = await fetch(new URL("/proof-of-learning", started.url));
  assert.equal(proofResponse.status, 200);
  const proofPayload = await proofResponse.json();
  assert.equal(proofPayload.private_payload_excluded, true);
  const birthResponse = await fetch(new URL("/genesis/birth", started.url), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      user_id: "dashboard-test",
      agent_name: "DashboardMira",
      archetype_id: "research-builder",
      purpose: "Verify dashboard agent creation",
      instincts: ["careful", "builder"],
      boundaries: ["ask_before_risky_action", "never_share_private_memory"],
      consent_mode: "private_only",
    }),
  });
  assert.equal(birthResponse.status, 200);
  const birthPayload = await birthResponse.json();
  assert.equal(birthPayload.ok, true);
  assert.match(birthPayload.data.agent_id, /^genesis_agent_/);
  assert.equal(birthPayload.data.birth_certificate.privacy.mode, "private_only");
  assert.equal(birthPayload.data.birth_certificate.privacy.raw_private_payload_excluded, true);
  const forgeBirthResponse = await fetch(new URL("/forge/birth", started.url), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      user_id: "dashboard-test",
      agent_name: "ForgeMira",
      archetype_id: "research-builder",
      purpose: "Verify Forge agent creation",
      instincts: ["careful", "builder"],
      boundaries: ["ask_before_risky_action", "never_share_private_memory"],
      consent_mode: "private_only",
    }),
  });
  assert.equal(forgeBirthResponse.status, 200);
  const forgeBirthPayload = await forgeBirthResponse.json();
  assert.equal(forgeBirthPayload.ok, true);
  assert.match(forgeBirthPayload.data.agent_id, /^genesis_agent_/);
  assert.equal(forgeBirthPayload.data.first_agent_requires_wallet, false);
  assert.equal(forgeBirthPayload.data.no_broadcast, true);
  const unsafeLaunchResponse = await fetch(new URL("/launch/agent", started.url), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "{}",
  });
  assert.equal(unsafeLaunchResponse.status, 405);
} finally {
  started.server.close();
  occupied.server.close();
}

console.log("mission control dev server renders real dashboard ok");
