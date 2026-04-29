from __future__ import annotations

import csv
import io
import json
from functools import lru_cache
from pathlib import Path
from uuid import UUID

import typer
from lattice_jit.contracts import PhaseBMode, QueryRequest, SnapshotGitRequest
from lattice_jit.core import AppContainer, build_container

app = typer.Typer(help="Lattice-JIT operator CLI")
ingest_app = typer.Typer(help="Snapshot ingestion commands")
answer_app = typer.Typer(help="Answer inspection commands")
review_app = typer.Typer(help="Review queue commands")
audit_app = typer.Typer(help="Audit trail commands")
app.add_typer(ingest_app, name="ingest")
app.add_typer(answer_app, name="answer")
app.add_typer(review_app, name="review")
app.add_typer(audit_app, name="audit")


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


@ingest_app.command("pdf")
def ingest_pdf(
    tenant_id: UUID = typer.Option(...),
    pdf_path: str = typer.Option(...),
    page_mode: str = typer.Option("document"),
) -> None:
    try:
        from lattice_jit.connectors.pdf import PdfSnapshotService
    except ImportError as exc:
        typer.echo("pypdf2 is not installed. Install it with: pip install pypdf2", err=True)
        raise typer.Exit(code=1) from exc
    container = get_container()
    service = PdfSnapshotService(container.repository)
    response = service.ingest(tenant_id=tenant_id, pdf_path=pdf_path, page_mode=page_mode)
    container.governance_service.record_snapshot_ingested(
        tenant_id=tenant_id,
        snapshot_id=response.snapshot_id,
        repo_path=pdf_path,
        node_count=len(container.repository.list_snapshot_nodes(response.snapshot_id)),
    )
    typer.echo(json.dumps(response.model_dump(mode="json"), indent=2))


@ingest_app.command("sharepoint")
def ingest_sharepoint(
    tenant_id: UUID = typer.Option(...),
    site_url: str = typer.Option(...),
    drive_name: str = typer.Option("Documents"),
    folder_path: str = typer.Option("/"),
) -> None:
    try:
        from lattice_jit.connectors.sharepoint import SharePointSnapshotService
    except ImportError:
        typer.echo(
            "SharePoint connector dependencies not installed. "
            "Install: pip install requests python-docx openpyxl python-pptx",
            err=True,
        )
        raise typer.Exit(code=1) from None
    container = get_container()
    service = SharePointSnapshotService(container.repository)
    response = service.ingest(
        tenant_id=tenant_id, site_url=site_url, drive_name=drive_name, folder_path=folder_path
    )
    container.governance_service.record_snapshot_ingested(
        tenant_id=tenant_id,
        snapshot_id=response.snapshot_id,
        repo_path=site_url,
        node_count=len(container.repository.list_snapshot_nodes(response.snapshot_id)),
    )
    typer.echo(json.dumps(response.model_dump(mode="json"), indent=2))


@ingest_app.command("confluence")
def ingest_confluence(
    tenant_id: UUID = typer.Option(...),
    confluence_url: str = typer.Option(...),
    space_key: str = typer.Option(...),
    page_limit: int = typer.Option(500),
) -> None:
    try:
        from lattice_jit.connectors.confluence import ConfluenceSnapshotService
    except ImportError:
        typer.echo(
            "Confluence connector dependencies not installed. Install: pip install requests html2text",
            err=True,
        )
        raise typer.Exit(code=1) from None
    container = get_container()
    service = ConfluenceSnapshotService(container.repository)
    response = service.ingest(
        tenant_id=tenant_id, confluence_url=confluence_url, space_key=space_key, page_limit=page_limit
    )
    container.governance_service.record_snapshot_ingested(
        tenant_id=tenant_id,
        snapshot_id=response.snapshot_id,
        repo_path=f"{confluence_url}/spaces/{space_key}",
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
def answer_get(
    answer_id: UUID = typer.Argument(...),
    tenant_id: UUID = typer.Option(...),
) -> None:
    response = get_container().query_service.get_answer(answer_id, tenant_id=tenant_id)
    typer.echo(json.dumps(response.model_dump(mode="json"), indent=2))


@review_app.command("list")
def review_list(tenant_id: UUID = typer.Option(...)) -> None:
    items = get_container().governance_service.list_review_queue(tenant_id)
    typer.echo(json.dumps({"items": [item.model_dump(mode="json") for item in items]}, indent=2))


@review_app.command("approve")
def review_approve(
    review_item_id: UUID = typer.Argument(...),
    tenant_id: UUID = typer.Option(...),
) -> None:
    result = get_container().governance_service.approve_review(review_item_id, tenant_id)
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))


@review_app.command("reject")
def review_reject(
    review_item_id: UUID = typer.Argument(...),
    tenant_id: UUID = typer.Option(...),
) -> None:
    result = get_container().governance_service.reject_review(review_item_id, tenant_id)
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))


@audit_app.command("list")
def audit_list(
    tenant_id: UUID = typer.Option(...),
    event_type: str | None = typer.Option(None),
    resource_type: str | None = typer.Option(None),
    resource_id: UUID | None = typer.Option(None),
    limit: int = typer.Option(100),
    offset: int = typer.Option(0),
) -> None:
    container = get_container()
    items = container.repository.list_audit_events_filtered(
        tenant_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        limit=limit,
        offset=offset,
    )
    total = container.repository.count_audit_events(
        tenant_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    typer.echo(
        json.dumps(
            {
                "items": [item.model_dump(mode="json") for item in items],
                "total": total,
                "limit": limit,
                "offset": offset,
            },
            indent=2,
        )
    )


@audit_app.command("export")
def audit_export(
    tenant_id: UUID = typer.Option(...),
    format: str = typer.Option("json"),
    output: Path = typer.Option(Path("audit_events.json")),
    event_type: str | None = typer.Option(None),
    resource_type: str | None = typer.Option(None),
    resource_id: UUID | None = typer.Option(None),
) -> None:
    container = get_container()
    items = container.repository.list_audit_events_filtered(
        tenant_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        limit=10_000,
        offset=0,
    )
    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "audit_event_id", "tenant_id", "event_type", "resource_type",
            "resource_id", "payload", "created_at",
        ])
        for item in items:
            writer.writerow([
                str(item.audit_event_id),
                str(item.tenant_id),
                item.event_type,
                item.resource_type,
                str(item.resource_id) if item.resource_id else "",
                str(item.payload),
                item.created_at.isoformat(),
            ])
        output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        output.write_text(json.dumps([item.model_dump(mode="json") for item in items], indent=2), encoding="utf-8")
    typer.echo(f"Exported {len(items)} audit events to {output}")
