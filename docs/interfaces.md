# HTTP And CLI Interfaces

## HTTP

### `GET /healthz`

Returns `{"status": "ok"}`. Used for health checks by Docker Compose and load balancers.

### `POST /v1/snapshots/git`

Request body:

```json
{
  "tenant_id": "00000000-0000-0000-0000-000000000001",
  "repo_path": "/workspace/project",
  "git_ref": "main",
  "include_globs": ["*.py"],
  "exclude_globs": ["tests/*"]
}
```

Response (`SnapshotResponse`):

```json
{
  "tenant_id": "uuid",
  "snapshot_id": "uuid",
  "root_node_id": "uuid",
  "status": "pending"
}
```

`status` is a `SnapshotStatus` enum: `pending`, `completed`, or `failed`.

### `POST /v1/snapshots/pdf`

Multipart form fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `tenant_id` | UUID | required | Tenant identifier |
| `pdf_path` | string | required | Local PDF file or directory |
| `page_mode` | string | `pymupdf4llm` | Parser/mode: `pymupdf4llm`, `markdown`, `cpu`, `pdfplumber`, `structured`, `page`, `document`, or optional `docling` |

### `POST /v1/queries`

Request body:

```json
{
  "tenant_id": "00000000-0000-0000-0000-000000000001",
  "query": "Where is the auth policy enforced?",
  "snapshot_id": "uuid",
  "subgraph_ids": null,
  "phase_b_mode": "auto"
}
```

Response (`QueryResponse`) includes `answer_id`, `phase_a` (an `AnswerEnvelope`), `phase_b_status`, and `manifest_id`.

### `GET /v1/answers/{answer_id}?tenant_id=<uuid>`

Returns the latest `AnswerEnvelope` for the answer ID. Requires `tenant_id` query parameter for tenant isolation.

`AnswerEnvelope` fields:

| Field | Type | Description |
|---|---|---|
| `answer_id` | UUID | Unique answer identifier |
| `tenant_id` | UUID | Tenant the answer belongs to |
| `phase` | `AnswerPhase` | `A` or `B` |
| `status` | `AnswerStatus` | `pending`, `complete`, `failed` |
| `answer_text` | string | The generated answer text |
| `confidence_band` | `ConfidenceBand` | `HIGH`, `MEDIUM`, or `LOW` |
| `provisional` | boolean | Whether the answer is provisional |
| `provenance` | `list[ProvenanceRef]` | Source provenance for each evidence item |
| `conflict_flags` | `list[string]` | Any conflict flags detected |
| `manifest_id` | UUID or null | The compiled context manifest ID |
| `phase_b_status` | string or null | Phase B verification status if applicable |
| `created_at` | datetime | When the answer was created |

Each `ProvenanceRef` contains: `node_id`, `title`, `source_uri`, `snapshot_id`, `snapshot_ref`, `content_hash`, `score`, `snippet`.

### `GET /v1/review-queue?tenant_id=<uuid>`

Returns queued governance items for operator review tooling.

`ReviewQueueResponse` contains `items: list[ReviewItem]`. Each `ReviewItem` has:

| Field | Type | Description |
|---|---|---|
| `review_item_id` | UUID | Unique review item identifier |
| `tenant_id` | UUID | Tenant the item belongs to |
| `fact_fingerprint` | string | Content hash for deduplication |
| `fact_type` | string | Class of fact (e.g., `compliance`, `security`) |
| `canonical_node_id` | UUID or null | The knowledge node under review |
| `dedup_count` | int | Number of times this fact was observed |
| `risk_level` | `ReviewRiskLevel` | `LOW`, `MEDIUM`, or `HIGH` |
| `review_state` | `ReviewState` | `NONE`, `PENDING`, `APPROVED`, `REJECTED`, `SAMPLED` |
| `sample_rate` | float | Sampling rate for load shedding |
| `evidence_count` | int | Number of provenance items linked |
| `created_at` | datetime | When the item was created |
| `reviewed_at` | datetime or null | When the item was reviewed |

### `POST /v1/review-queue/{review_item_id}/approve?tenant_id=<uuid>`

Approves a pending review item. Updates `review_state` to `APPROVED`, writes an audit event, and propagates the approval to the associated knowledge node. Returns the updated `ReviewItem`.

### `POST /v1/review-queue/{review_item_id}/reject?tenant_id=<uuid>`

Rejects a pending review item. Updates `review_state` to `REJECTED`, writes an audit event, and propagates the rejection to the associated knowledge node. Returns the updated `ReviewItem`.

## CLI

- `ljit ingest git --tenant-id <uuid> --repo-path <path> [--git-ref <ref>] [--include-globs <glob>]... [--exclude-globs <glob>]...`
- `ljit query --tenant-id <uuid> --query "<text>" [--snapshot-id <uuid>] [--phase-b-mode auto|off|force]`
- `ljit answer get <answer-id> --tenant-id <uuid>`
- `ljit review list --tenant-id <uuid>`
- `ljit review approve <review-item-id> --tenant-id <uuid>`
- `ljit review reject <review-item-id> --tenant-id <uuid>`

The CLI calls the same shared services as the API rather than shelling out to HTTP.
