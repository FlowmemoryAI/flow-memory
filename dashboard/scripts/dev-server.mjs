import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const port = Number(process.env.PORT || 4173);
const replayPath = path.join(root, 'src', 'mock-data', 'local-network-replay.json');

function send(res, status, contentType, body) {
  res.writeHead(status, { 'content-type': contentType });
  res.end(body);
}

function dashboardHtml() {
  const replayExists = fs.existsSync(replayPath);
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Flow Memory Mission Control</title>
  <style>
    body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; background: #070a12; color: #edf7ff; }
    main { min-height: 100vh; display: grid; place-items: center; padding: 32px; }
    section { max-width: 960px; border: 1px solid rgba(126, 210, 255, .22); border-radius: 28px; padding: 32px; background: radial-gradient(circle at 20% 10%, rgba(99,102,241,.25), transparent 28%), rgba(10, 16, 30, .84); box-shadow: 0 24px 80px rgba(0,0,0,.35); }
    h1 { font-size: clamp(36px, 7vw, 84px); margin: 0 0 8px; letter-spacing: -.06em; }
    p { color: #a9bad0; line-height: 1.6; }
    code { color: #8ee6ff; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin-top: 24px; }
    .card { border: 1px solid rgba(255,255,255,.12); border-radius: 18px; padding: 16px; background: rgba(255,255,255,.04); }
    .label { color: #7dd3fc; font-size: 12px; text-transform: uppercase; letter-spacing: .12em; }
  </style>
</head>
<body>
  <main>
    <section>
      <div class="label">Public-alpha local dashboard</div>
      <h1>Mission Control</h1>
      <p>This dependency-free dev server confirms the dashboard package is runnable. The checked-in TypeScript components define the Mission Control mock/replay/live state model; production frontend bundling remains a public-alpha next step.</p>
      <div class="grid">
        <div class="card"><div class="label">Replay</div><p>${replayExists ? 'local-network-replay.json is present.' : 'Run the visual replay export first.'}</p></div>
        <div class="card"><div class="label">Backend</div><p>Use <code>python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765</code> for live mode.</p></div>
        <div class="card"><div class="label">Modes</div><p>Mock, replay, and live local API are explicit and labeled.</p></div>
      </div>
    </section>
  </main>
</body>
</html>`;
}

const server = http.createServer((req, res) => {
  if (req.url === '/' || req.url === '/mission-control') {
    send(res, 200, 'text/html; charset=utf-8', dashboardHtml());
    return;
  }
  if (req.url === '/mock-data/local-network-replay.json') {
    if (!fs.existsSync(replayPath)) {
      send(res, 404, 'application/json', JSON.stringify({ ok: false, error: 'replay_missing' }));
      return;
    }
    send(res, 200, 'application/json', fs.readFileSync(replayPath));
    return;
  }
  send(res, 404, 'application/json', JSON.stringify({ ok: false, error: 'not_found' }));
});

server.listen(port, '127.0.0.1', () => {
  console.log(`Flow Memory Mission Control dev server: http://127.0.0.1:${port}/mission-control`);
});
