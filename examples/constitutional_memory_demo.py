from flow_memory.memory.constitutional_graph import ConstitutionalGraph
from flow_memory.memory.memory_policy import MemoryPolicy


graph = ConstitutionalGraph()
policy = MemoryPolicy()
goal = graph.write("goals", "Ship agent economy v2", policy=policy, source="operator")
task = graph.write("tasks", "Add runtime managers", policy=policy, source="builder")
graph.relate(goal.node_id, "decomposes_to", task.node_id)
print({"domains": graph.domains(), "goals": [node.text for node in graph.retrieve("goals")], "edges": len(graph.edges)})
