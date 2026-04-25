from __future__ import annotations

import json
from functools import lru_cache
from uuid import UUID

import typer
from lattice_jit.contracts import PhaseBMode, QueryRequest, SnapshotGitRequest
from lattice_jit.core import AppContainer, build_container

app = typer.Typer(help="Lattice-JIT operator CLI")
ingest_app = typer.Typer(help="Snapshot ingestion commands")
answer_app = typer.Typer(help="Answer inspection commands")
review_app = typer.Typer(help="Review queue commands")
app.add_typer(ingest_app, name="ingest")
app.add_typer(answer_app, name="answer")
app.add_typer(review_app, name="review")


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return build_container()


@ingest_app.command("git")
def ingest_git(
    tenant_id: UUID = typer.Option(...),
    repo_path: str = typer.Option(...),
    git_ref: str | None = typer.Option(None),
    include_globs: list[str] = typer.Option(default_factory=list),
    exclude_globs: list[str] = typer.Option(default_factory=list),
) -> None:
    container = get_container()
    response = container.snapshot_service.ingest(
        SnapshotGitRequest(
            tenant_id=tenant_id,
            repo_path=repo_path,
            git_ref=git_ref,
            include_globs=include_globs,
            exclude_globs=exclude_globs,
        )
    )
    container.governance_service.record_snapshot_ingested(
        tenant_id=tenant_id,
        snapshot_id=response.snapshot_id,
        repo_path=repo_path,
        node_count=len(container.repository.list_snapshot_nodes(response.snapshot_id)),
    )
    typer.echo(json.dumps(response.model_dump(mode="json"), indent=2))


@app.command("query")
def run_query(
    tenant_id: UUID = typer.Option(...),
    query: str = typer.Option(...),
    snapshot_id: UUID | None = typer.Option(None),
    phase_b_mode: PhaseBMode = typer.Option(PhaseBMode.AUTO),
) -> None:
    response = get_container().query_service.run(
        QueryRequest(
            tenant_id=tenant_id,
            query=query,
            snapshot_id=snapshot_id,
            phase_b_mode=phase_b_mode,
        )
    )
    typer.echo(json.dumps(response.model_dump(mode="json"), indent=2))


@answer_app.command("get")
def answer_get(answer_id: UUID) -> None:
    response = get_container().query_service.get_answer(answer_id)
    typer.echo(json.dumps(response.model_dump(mode="json"), indent=2))


@review_app.command("list")
def review_list(tenant_id: UUID = typer.Option(...)) -> None:
    items = get_container().governance_service.list_review_queue(tenant_id)
    typer.echo(json.dumps({"items": [item.model_dump(mode="json") for item in items]}, indent=2))
