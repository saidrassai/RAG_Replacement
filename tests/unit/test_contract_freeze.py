from __future__ import annotations

from fastapi.routing import APIRoute
from lattice_jit.apps.api.main import create_app
from lattice_jit.apps.cli.main import app as cli_app
from lattice_jit.contracts import (
    AnswerEnvelope,
    QueryRequest,
    QueryResponse,
    ReviewQueueResponse,
    SnapshotGitRequest,
    SnapshotResponse,
)
from typer.testing import CliRunner


def test_api_route_surface_matches_plan() -> None:
    app = create_app()
    routes = {
        (next(iter(route.methods or [])), route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    assert ("POST", "/v1/snapshots/git") in routes
    assert ("POST", "/v1/queries") in routes
    assert ("GET", "/v1/answers/{answer_id}") in routes
    assert ("GET", "/v1/review-queue") in routes


def test_snapshot_request_contract_fields_are_stable() -> None:
    assert set(SnapshotGitRequest.model_fields) == {
        "tenant_id",
        "repo_path",
        "git_ref",
        "include_globs",
        "exclude_globs",
    }


def test_query_request_contract_fields_are_stable() -> None:
    assert set(QueryRequest.model_fields) == {
        "tenant_id",
        "query",
        "snapshot_id",
        "subgraph_ids",
        "phase_b_mode",
    }


def test_query_response_contract_fields_are_stable() -> None:
    assert set(QueryResponse.model_fields) == {
        "answer_id",
        "phase_a",
        "phase_b_status",
        "manifest_id",
    }


def test_snapshot_response_contract_fields_are_stable() -> None:
    assert set(SnapshotResponse.model_fields) == {
        "tenant_id",
        "snapshot_id",
        "root_node_id",
        "status",
    }


def test_review_queue_response_contract_fields_are_stable() -> None:
    assert set(ReviewQueueResponse.model_fields) == {"items"}


def test_answer_envelope_contract_fields_are_stable() -> None:
    assert set(AnswerEnvelope.model_fields) == {
        "answer_id",
        "tenant_id",
        "phase",
        "status",
        "answer_text",
        "confidence_band",
        "provisional",
        "provenance",
        "conflict_flags",
        "manifest_id",
        "phase_b_status",
        "created_at",
    }


def test_cli_command_surface_matches_plan() -> None:
    runner = CliRunner()

    root_help = runner.invoke(cli_app, ["--help"])
    assert root_help.exit_code == 0
    assert "query" in root_help.stdout

    ingest_help = runner.invoke(cli_app, ["ingest", "--help"])
    answer_help = runner.invoke(cli_app, ["answer", "--help"])
    review_help = runner.invoke(cli_app, ["review", "--help"])

    assert ingest_help.exit_code == 0
    assert answer_help.exit_code == 0
    assert review_help.exit_code == 0

    assert "git" in ingest_help.stdout
    assert "get" in answer_help.stdout
    assert "list" in review_help.stdout