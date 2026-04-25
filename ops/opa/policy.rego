package lattice_jit.policy

default allow = true

default phase_b_required = false

query_class := input.query_class

phase_b_required if {
  input.query_class == "compliance"
}

phase_b_required if {
  input.query_class == "security"
}

tool_allowlist := ["git_local"]

max_tokens := 12000 if {
  phase_b_required
}

max_tokens := 16000 if {
  not phase_b_required
}
