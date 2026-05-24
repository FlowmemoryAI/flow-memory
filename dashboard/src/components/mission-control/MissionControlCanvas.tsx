import type { VisualNetworkState } from "../../lib/visual-state";
import { AgentNode3D } from "./AgentNode3D";
import { EconomyEdge } from "./EconomyEdge";
import { MemoryFlow } from "./MemoryFlow";
import { NeuralHalo } from "./NeuralHalo";
import { SafetyGate3D } from "./SafetyGate3D";
import { TaskPulse } from "./TaskPulse";

export function MissionControlCanvas({ state }: { state: VisualNetworkState }) {
  return (
    <section data-mode={state.provenance} className="mission-control-canvas">
      <div className="canvas-label">Flow Memory Mission Control · {state.provenance}</div>
      <div className="network-layer">
        {state.agents.map((agent) => <AgentNode3D key={agent.agent_id} agent={agent} />)}
        {state.tasks.map((task) => <TaskPulse key={task.task_id} task={task} />)}
        {state.economy.map((edge) => <EconomyEdge key={edge.edge_id} edge={edge} />)}
        <MemoryFlow count={state.memory.length} />
        <NeuralHalo count={state.neural.length} />
        <SafetyGate3D count={state.safety.length} />
      </div>
    </section>
  );
}
