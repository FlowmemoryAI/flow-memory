package flowmemory.safety

default allow := false

allowed_permissions := {
  "respond",
  "memory.read",
  "environment.observe",
  "tool.invoke",
  "economy.read",
  "marketplace.read",
}

deny[msg] {
  step := input.steps[_]
  not allowed_permissions[step.required_permission]
  msg := sprintf("permission denied: %s", [step.required_permission])
}

allow {
  count(deny) == 0
}
