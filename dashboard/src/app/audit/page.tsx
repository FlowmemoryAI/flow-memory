import replay from "../../mock-data/local-network-replay.json";

export default function AuditPage() {
  return <main><h1>Audit</h1><pre>{JSON.stringify(replay.state.audit.slice(0, 20), null, 2)}</pre></main>;
}
