from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from lattice_jit.connectors.pdf import PdfSnapshotService
from lattice_jit.contracts import (
    AnswerEnvelope,
    QueryRequest,
    QueryResponse,
    ReviewItem,
    ReviewQueueResponse,
    SnapshotGitRequest,
    SnapshotResponse,
)
from lattice_jit.core import AppContainer, NotFoundError, build_container


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return build_container()


def create_app() -> FastAPI:
    application = FastAPI(title="Lattice-JIT Compiler v3.1")

    templates_dir = Path(__file__).resolve().parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    application.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
        name="static",
    )

    @application.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/v1/snapshots/git", response_model=SnapshotResponse)
    def create_git_snapshot(
        request: SnapshotGitRequest,
        container: AppContainer = Depends(get_container),
    ) -> SnapshotResponse:
        response = container.snapshot_service.ingest(request)
        container.governance_service.record_snapshot_ingested(
            tenant_id=request.tenant_id,
            snapshot_id=response.snapshot_id,
            repo_path=request.repo_path,
            node_count=len(container.repository.list_snapshot_nodes(response.snapshot_id)),
        )
        return response

    @application.post("/v1/snapshots/pdf", response_model=SnapshotResponse)
    def create_pdf_snapshot(
        tenant_id: UUID = Form(...),
        pdf_path: str = Form(...),
        page_mode: str = Form("document"),
        container: AppContainer = Depends(get_container),
    ) -> SnapshotResponse:
        service = PdfSnapshotService(container.repository)
        response = service.ingest(tenant_id=tenant_id, pdf_path=pdf_path, page_mode=page_mode)
        container.governance_service.record_snapshot_ingested(
            tenant_id=tenant_id,
            snapshot_id=response.snapshot_id,
            repo_path=pdf_path,
            node_count=len(container.repository.list_snapshot_nodes(response.snapshot_id)),
        )
        return response

    @application.post("/v1/queries", response_model=QueryResponse)
    def create_query(
        request: QueryRequest,
        container: AppContainer = Depends(get_container),
    ) -> QueryResponse:
        try:
            return container.query_service.run(request)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/v1/answers/{answer_id}", response_model=AnswerEnvelope)
    def get_answer(
        answer_id: UUID,
        tenant_id: UUID,
        container: AppContainer = Depends(get_container),
    ) -> AnswerEnvelope:
        try:
            return container.query_service.get_answer(answer_id, tenant_id=tenant_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/v1/review-queue", response_model=ReviewQueueResponse)
    def get_review_queue(
        tenant_id: UUID,
        container: AppContainer = Depends(get_container),
    ) -> ReviewQueueResponse:
        return ReviewQueueResponse(items=container.governance_service.list_review_queue(tenant_id))

    @application.post("/v1/review-queue/{review_item_id}/approve", response_model=ReviewItem)
    def approve_review(
        review_item_id: UUID,
        tenant_id: UUID,
        container: AppContainer = Depends(get_container),
    ) -> ReviewItem:
        try:
            return container.governance_service.approve_review(review_item_id, tenant_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/v1/review-queue/{review_item_id}/reject", response_model=ReviewItem)
    def reject_review(
        review_item_id: UUID,
        tenant_id: UUID,
        container: AppContainer = Depends(get_container),
    ) -> ReviewItem:
        try:
            return container.governance_service.reject_review(review_item_id, tenant_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/v1/opa/health")
    def opa_health(
        container: AppContainer = Depends(get_container),
    ) -> dict[str, str]:
        return container.query_service.policy_evaluator.health_check()

    @application.get("/v1/audit-events")
    def list_audit_events(
        tenant_id: UUID,
        event_type: str | None = Query(None),
        resource_type: str | None = Query(None),
        resource_id: UUID | None = Query(None),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        container: AppContainer = Depends(get_container),
    ) -> dict[str, object]:
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
        return {
            "items": [item.model_dump(mode="json") for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @application.get("/v1/audit-events/export")
    def export_audit_events(
        tenant_id: UUID,
        format: str = Query("json"),
        event_type: str | None = Query(None),
        resource_type: str | None = Query(None),
        resource_id: UUID | None = Query(None),
        container: AppContainer = Depends(get_container),
    ):
        items = container.repository.list_audit_events_filtered(
            tenant_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=10_000,
            offset=0,
        )
        if format == "csv":
            import csv
            import io

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
            buf.seek(0)
            return StreamingResponse(
                iter([buf.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=audit_events.csv"},
            )
        import json

        return StreamingResponse(
            iter([json.dumps([item.model_dump(mode="json") for item in items], indent=2)]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_events.json"},
        )

    @application.get("/ui/review-queue", response_class=HTMLResponse)
    def ui_review_queue(
        request: Request,
        tenant_id: UUID,
        risk_level: str | None = Query(None),
        fact_type: str | None = Query(None),
        review_state: str | None = Query(None),
        sort_by: str = Query("created_at"),
        sort_desc: bool = Query(True),
        limit: int = Query(20),
        offset: int = Query(0),
        container: AppContainer = Depends(get_container),
    ):
        items = container.governance_service.list_review_queue(tenant_id)
        # Client-side filtering (simple approach for server-rendered UI)
        if risk_level and risk_level != "all":
            items = [i for i in items if i.risk_level.value.lower() == risk_level.lower()]
        if fact_type:
            items = [i for i in items if fact_type.lower() in i.fact_type.lower()]
        if review_state and review_state != "all":
            items = [i for i in items if i.review_state.value.lower() == review_state.lower()]
        # Sort
        if sort_by == "risk_level":
            items.sort(key=lambda i: i.risk_level.value, reverse=sort_desc)
        elif sort_by == "created_at":
            items.sort(key=lambda i: i.created_at, reverse=sort_desc)
        elif sort_by == "dedup_count":
            items.sort(key=lambda i: i.dedup_count, reverse=sort_desc)
        message = request.query_params.get("message", "")
        return templates.TemplateResponse(
            request,
            "review_list.html",
            {
                "request": request,
                "items": items[offset : offset + limit],
                "tenant_id": tenant_id,
                "total": len(items),
                "limit": limit,
                "offset": offset,
                "has_prev": offset > 0,
                "has_next": offset + limit < len(items),
                "message": message,
                "risk_level": risk_level or "",
                "fact_type": fact_type or "",
                "review_state": review_state or "",
                "sort_by": sort_by,
                "sort_desc": sort_desc,
            },
        )

    @application.get("/ui/review-queue/{review_item_id}", response_class=HTMLResponse)
    def ui_review_detail(
        request: Request,
        review_item_id: UUID,
        tenant_id: UUID,
        container: AppContainer = Depends(get_container),
    ):
        item = container.repository.get_review_item(review_item_id, tenant_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Review item not found.")
        return templates.TemplateResponse(
            request,
            "review_detail.html",
            {"request": request, "item": item, "tenant_id": tenant_id},
        )

    @application.post("/ui/review-queue/{review_item_id}/approve")
    def ui_approve_review(
        review_item_id: UUID,
        tenant_id: UUID = Form(...),
        container: AppContainer = Depends(get_container),
    ):
        try:
            container.governance_service.approve_review(review_item_id, tenant_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RedirectResponse(
            f"/ui/review-queue?tenant_id={tenant_id}&message=Review+approved",
            status_code=303,
        )

    @application.post("/ui/review-queue/{review_item_id}/reject")
    def ui_reject_review(
        review_item_id: UUID,
        tenant_id: UUID = Form(...),
        container: AppContainer = Depends(get_container),
    ):
        try:
            container.governance_service.reject_review(review_item_id, tenant_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RedirectResponse(
            f"/ui/review-queue?tenant_id={tenant_id}&message=Review+rejected",
            status_code=303,
        )

    return application


app = create_app()


def main() -> None:
    uvicorn.run("lattice_jit.apps.api.main:app", host="0.0.0.0", port=8000, reload=False)
