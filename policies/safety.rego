package flowmemory.safety

default allow := false

default requires_human := false

low_risk_permissions := {"respond", "memory.read", "environment.observe", "tool.invoke"}

allow if {
  every step in input.steps {
    step.required_permission in low_risk_permissions
    not step.approval_required
    step.economic_value == 0
  }
}

requires_human if {
  some step in input.steps
  step.required_permission == "wallet.transfer"
}

requires_human if {
  some step in input.steps
  step.required_permission == "code.execute"
}

requires_human if {
  some step in input.steps
  step.economic_value > 0
}
