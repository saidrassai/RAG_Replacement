# HTTP And CLI Interfaces

## HTTP

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

Response:

```json
{
  "snapshot_id": "uuid",
  "root_node_id": "uuid",
  "status": "completed"
}
```

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

Response includes `answer_id`, `phase_a`, `phase_b_status`, and `manifest_id`.

### `GET /v1/answers/{answer_id}`

Returns the latest answer envelope for the answer ID, including provenance, confidence band, provisional flag, and phase information.

### `GET /v1/review-queue?tenant_id=<uuid>`

Returns queued governance items for operator review tooling.

## CLI

- `ljit ingest git --tenant-id <uuid> --repo-path <path> [--git-ref <ref>]`
- `ljit query --tenant-id <uuid> --query "<text>" [--snapshot-id <uuid>] [--phase-b-mode auto|off|force]`
- `ljit answer get <answer-id>`
- `ljit review list --tenant-id <uuid>`

The CLI calls the same shared services as the API rather than shelling out to HTTP.
