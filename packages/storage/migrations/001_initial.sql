CREATE TABLE IF NOT EXISTS source_snapshots (
  snapshot_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  repo_path TEXT NOT NULL,
  git_ref VARCHAR(255),
  include_globs JSONB NOT NULL,
  exclude_globs JSONB NOT NULL,
  status VARCHAR(32) NOT NULL,
  root_node_id UUID,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_nodes (
  node_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  snapshot_id UUID REFERENCES source_snapshots(snapshot_id),
  node_type VARCHAR(64) NOT NULL,
  title VARCHAR(512) NOT NULL,
  source_uri TEXT,
  body_ptr TEXT,
  body_text TEXT,
  content_hash VARCHAR(64) NOT NULL,
  snapshot_ref VARCHAR(255),
  source_confidence DOUBLE PRECISION NOT NULL,
  serving_confidence DOUBLE PRECISION NOT NULL,
  volatility_score DOUBLE PRECISION NOT NULL,
  freshness_expires_at TIMESTAMPTZ,
  review_state VARCHAR(32) NOT NULL,
  derived_from_run_id UUID,
  metadata_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_edges (
  edge_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  from_node_id UUID REFERENCES knowledge_nodes(node_id),
  to_node_id UUID REFERENCES knowledge_nodes(node_id),
  edge_type VARCHAR(64) NOT NULL,
  evidence_spans JSONB NOT NULL,
  source_confidence DOUBLE PRECISION NOT NULL,
  serving_confidence DOUBLE PRECISION NOT NULL,
  active BOOLEAN NOT NULL,
  cycle_break_reason TEXT,
  created_by_run_id UUID,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_bundles (
  policy_bundle_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  query_class VARCHAR(128) NOT NULL,
  tool_allowlist JSONB NOT NULL,
  redaction_rules JSONB NOT NULL,
  max_tokens INTEGER NOT NULL,
  phase_b_required BOOLEAN NOT NULL,
  human_gate_required BOOLEAN NOT NULL,
  opa_decision_hash VARCHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS compiled_context_manifests (
  manifest_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  query_hash VARCHAR(64) NOT NULL,
  policy_bundle_id UUID REFERENCES policy_bundles(policy_bundle_id),
  context_hash VARCHAR(64) NOT NULL UNIQUE,
  budget_tokens INTEGER NOT NULL,
  actual_tokens INTEGER NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS compiled_context_items (
  manifest_id UUID REFERENCES compiled_context_manifests(manifest_id),
  ordinal INTEGER NOT NULL,
  node_id UUID REFERENCES knowledge_nodes(node_id),
  role VARCHAR(32) NOT NULL,
  token_count INTEGER NOT NULL,
  score DOUBLE PRECISION NOT NULL,
  snippet TEXT NOT NULL,
  PRIMARY KEY (manifest_id, ordinal)
);

CREATE TABLE IF NOT EXISTS answer_events (
  event_id UUID PRIMARY KEY,
  answer_id UUID NOT NULL,
  tenant_id UUID NOT NULL,
  phase VARCHAR(8) NOT NULL,
  status VARCHAR(32) NOT NULL,
  answer_text TEXT NOT NULL,
  confidence_band VARCHAR(16) NOT NULL,
  provisional BOOLEAN NOT NULL,
  provenance_json JSONB NOT NULL,
  conflict_flags_json JSONB NOT NULL,
  manifest_id UUID,
  phase_b_status VARCHAR(32),
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS review_queue (
  review_item_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  fact_fingerprint VARCHAR(64) NOT NULL,
  fact_type VARCHAR(128) NOT NULL,
  canonical_node_id UUID,
  dedup_count INTEGER NOT NULL,
  risk_level VARCHAR(16) NOT NULL,
  review_state VARCHAR(32) NOT NULL,
  sample_rate DOUBLE PRECISION NOT NULL,
  evidence_count INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS feedback_labels (
  label_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  target_type VARCHAR(32) NOT NULL,
  target_id UUID NOT NULL,
  label_type VARCHAR(32) NOT NULL,
  label_value DOUBLE PRECISION NOT NULL,
  labeled_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  audit_event_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  resource_type VARCHAR(64) NOT NULL,
  resource_id UUID,
  payload_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
