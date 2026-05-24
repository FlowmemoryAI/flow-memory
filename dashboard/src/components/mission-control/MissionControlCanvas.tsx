import type { VisualNetworkState } from "../../lib/visual-state";
import { agentNeuralActivity, agentRiskScore } from "../../lib/visual-state";
import { AgentNode3D } from "./AgentNode3D";
import { EconomyEdge } from "./EconomyEdge";
import { MemoryFlow } from "./MemoryFlow";
import { NeuralHalo } from "./NeuralHalo";
import { PredictionArc } from "./PredictionArc";
import { SafetyGate3D } from "./SafetyGate3D";
import { TaskPulse } from "./TaskPulse";

export function MissionControlCanvas({ state }: { state: VisualNetworkState }) {
  const selectedAgent = state.agents[0];
  const selectedNeural = selectedAgent ? state.neural.find((signal) => signal.agent_id === selectedAgent.agent_id) : undefined;
  return (
    <section data-mode={state.provenance} className="mission-control-canvas" aria-label="Flow Memory Mission Control visual network">
      <div className="canvas-backdrop" />
      <div className="canvas-label">
        <span>Mission Control</span>
        <strong>{state.provenance}</strong>
      </div>
      <div className="network-layer" style={{ "--agent-count": state.agents.length } as Record<string, number>}>
        <div className="network-orbit network-orbit-memory" />
        <div className="network-orbit network-orbit-economy" />
        {state.economy.map((edge, index) => <EconomyEdge key={edge.edge_id} edge={edge} index={index} />)}
        {state.memory.map((memory, index) => <MemoryFlow key={memory.memory_id} memory={memory} index={index} />)}
        {state.tasks.map((task, index) => <TaskPulse key={task.task_id} task={task} index={index} />)}
        {state.agents.map((agent, index) => (
          <AgentNode3D
            key={agent.agent_id}
            agent={agent}
            index={index}
            neuralActivity={agentNeuralActivity(state, agent.agent_id)}
            riskScore={agentRiskScore(state, agent.agent_id)}
            approvalRequired={state.safety.some((gate) => gate.agent_id === agent.agent_id && gate.requires_approval)}
            memoryLoad={state.memory.filter((memory) => memory.agent_id === agent.agent_id).length}
          />
        ))}
        {state.neural.map((signal, index) => <NeuralHalo key={signal.signal_id} signal={signal} index={index} />)}
        {selectedNeural ? <PredictionArc signal={selectedNeural} confidence={Math.max(0.12, selectedNeural.plan_score)} /> : null}
        {state.safety.map((gate, index) => <SafetyGate3D key={gate.gate_id} gate={gate} index={index} />)}
      </div>
      <div className="canvas-readout">
        <span>{state.runtime.agents} agents</span>
        <span>{state.runtime.tasks} tasks</span>
        <span>{state.economy.length} economy edges</span>
        <span>{state.safety.filter((gate) => gate.requires_approval).length} approvals</span>
      </div>
    </section>
  );
}
