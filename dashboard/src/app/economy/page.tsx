import replay from "../../mock-data/local-network-replay.json";

export default function EconomyPage() {
  return <main><h1>Economy</h1><pre>{JSON.stringify(replay.state.economy, null, 2)}</pre></main>;
}
