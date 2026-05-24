import replay from "../../mock-data/local-network-replay.json";

export default function AgentsPage() {
  return <main><h1>Agents</h1><pre>{JSON.stringify(replay.state.agents, null, 2)}</pre></main>;
}
