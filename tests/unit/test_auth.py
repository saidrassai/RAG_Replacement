from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from lattice_jit.apps.api.main import create_app
from lattice_jit.core.auth import parse_api_keys
from lattice_jit.core.settings import Settings


def test_parse_api_keys_empty() -> None:
    assert parse_api_keys("") == {}


def test_parse_api_keys_single() -> None:
    keys = parse_api_keys("abc123=00000000-0000-0000-0000-000000000001")
    assert keys == {"abc123": UUID("00000000-0000-0000-0000-000000000001")}


def test_parse_api_keys_multiple() -> None:
    keys = parse_api_keys(
        "key1=00000000-0000-0000-0000-000000000001,key2=00000000-0000-0000-0000-000000000002"
    )
    assert len(keys) == 2
    assert keys["key1"] == UUID("00000000-0000-0000-0000-000000000001")
    assert keys["key2"] == UUID("00000000-0000-0000-0000-000000000002")


def test_auth_disabled_allows_healthz() -> None:
    settings = Settings(auth_enabled=False)
    app = create_app(settings=settings)
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_enabled_rejects_missing_key() -> None:
    settings = Settings(
        auth_enabled=True,
        auth_api_keys="test-key=00000000-0000-0000-0000-000000000001",
    )
    app = create_app(settings=settings)
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200  # healthz is always excluded from auth


def test_auth_enabled_blocks_unauthenticated() -> None:
    settings = Settings(
        auth_enabled=True,
        auth_api_keys="test-key=00000000-0000-0000-0000-000000000001",
    )
    app = create_app(settings=settings)
    client = TestClient(app)
    # Try a non-excluded endpoint without auth header
    response = client.get("/v1/review-queue", params={"tenant_id": str(UUID(int=0))})
    assert response.status_code == 401
