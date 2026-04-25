from __future__ import annotations

from functools import lru_cache
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from lattice_jit.contracts import (
    AnswerEnvelope,
    QueryRequest,
    QueryResponse,
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
        container: AppContainer = Depends(get_container),
    ) -> AnswerEnvelope:
        try:
            return container.query_service.get_answer(answer_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/v1/review-queue", response_model=ReviewQueueResponse)
    def get_review_queue(
        tenant_id: UUID,
        container: AppContainer = Depends(get_container),
    ) -> ReviewQueueResponse:
        return ReviewQueueResponse(items=container.governance_service.list_review_queue(tenant_id))

    return application


app = create_app()


def main() -> None:
    uvicorn.run("lattice_jit.apps.api.main:app", host="0.0.0.0", port=8000, reload=False)
