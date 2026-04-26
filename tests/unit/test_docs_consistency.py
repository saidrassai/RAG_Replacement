from __future__ import annotations

from pathlib import Path

from fastapi.routing import APIRoute
from lattice_jit.apps.api.main import create_app
from lattice_jit.apps.cli.main import app as cli_app
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[2]


def _read_repo_file(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_interfaces_doc_matches_http_and_cli_surface() -> None:
    interfaces_doc = _read_repo_file("docs/interfaces.md")

    expected_http_routes = {
        ("POST", "/v1/snapshots/git"),
        ("POST", "/v1/queries"),
        ("GET", "/v1/answers/{answer_id}"),
        ("GET", "/v1/review-queue"),
    }

    app = create_app()
    actual_http_routes = {
        (next(iter(route.methods or [])), route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    assert expected_http_routes.issubset(actual_http_routes)
    for _, path in expected_http_routes:
        assert path in interfaces_doc

    # Keep request/response examples aligned with current contract fields in docs.
    for expected_field in (
        '"tenant_id"',
        '"repo_path"',
        '"git_ref"',
        '"include_globs"',
        '"exclude_globs"',
        '"query"',
        '"snapshot_id"',
        '"subgraph_ids"',
        '"phase_b_mode"',
    ):
        assert expected_field in interfaces_doc

    runner = CliRunner()
    root_help = runner.invoke(cli_app, ["--help"])
    ingest_help = runner.invoke(cli_app, ["ingest", "--help"])
    answer_help = runner.invoke(cli_app, ["answer", "--help"])
    review_help = runner.invoke(cli_app, ["review", "--help"])

    assert root_help.exit_code == 0
    assert ingest_help.exit_code == 0
    assert answer_help.exit_code == 0
    assert review_help.exit_code == 0

    assert "query" in root_help.stdout
    assert "git" in ingest_help.stdout
    assert "get" in answer_help.stdout
    assert "list" in review_help.stdout

    for expected_cli_doc_fragment in (
        "ljit ingest git",
        "ljit query",
        "ljit answer get",
        "ljit review list",
    ):
        assert expected_cli_doc_fragment in interfaces_doc


def test_architecture_doc_matches_declared_runtime_components() -> None:
    architecture_doc = _read_repo_file("docs/architecture.md")

    for expected_route in (
        "/v1/snapshots/git",
        "/v1/queries",
        "/v1/answers/{answer_id}",
        "/v1/review-queue",
    ):
        assert expected_route in architecture_doc

    for package_name in (
        "contracts",
        "core",
        "storage",
        "connectors/git_local",
        "lattice",
        "runtime",
        "policy",
        "governance",
        "model_proxy",
    ):
        assert f"packages/{package_name}" in architecture_doc
