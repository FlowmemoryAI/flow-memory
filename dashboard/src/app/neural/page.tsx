import replay from "../../mock-data/local-network-replay.json";

export default function NeuralPage() {
  return <main><h1>Neural Advisory</h1><pre>{JSON.stringify(replay.state.neural, null, 2)}</pre></main>;
}
