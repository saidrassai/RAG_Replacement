from __future__ import annotations

from fastapi.testclient import TestClient
from lattice_jit.apps.api.main import create_app
from lattice_jit.core.rate_limit import RateLimiter
from lattice_jit.core.settings import Settings


def test_rate_limiter_disabled_always_allows() -> None:
    limiter = RateLimiter(enabled=False)
    for _ in range(200):
        assert limiter.is_allowed("tenant-1", "/v1/queries") is True


def test_rate_limiter_enabled_blocks_after_limit() -> None:
    limiter = RateLimiter(enabled=True, max_per_minute=5, window_seconds=60)
    for _ in range(5):
        assert limiter.is_allowed("tenant-1", "/v1/queries") is True
    assert limiter.is_allowed("tenant-1", "/v1/queries") is False


def test_rate_limiter_different_tenants_separate_buckets() -> None:
    limiter = RateLimiter(enabled=True, max_per_minute=2, window_seconds=60)
    assert limiter.is_allowed("tenant-a", "/v1/queries") is True
    assert limiter.is_allowed("tenant-a", "/v1/queries") is True
    assert limiter.is_allowed("tenant-a", "/v1/queries") is False
    assert limiter.is_allowed("tenant-b", "/v1/queries") is True


def test_rate_limiter_ingest_tier_uses_separate_limit() -> None:
    limiter = RateLimiter(enabled=True, max_per_minute=100, ingest_max_per_minute=2)
    for _ in range(2):
        assert limiter.is_allowed("tenant-1", "/v1/snapshots/git") is True
    assert limiter.is_allowed("tenant-1", "/v1/snapshots/git") is False
    assert limiter.is_allowed("tenant-1", "/v1/queries") is True


def test_rate_limiter_health_endpoint_excluded() -> None:
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_max_per_minute=1,
    )
    app = create_app(settings=settings)
    client = TestClient(app)
    # Health endpoint should never be rate limited
    for _ in range(10):
        r = client.get("/healthz")
        assert r.status_code == 200


def test_rate_limit_returns_429() -> None:
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_max_per_minute=1,
        rate_limit_window_seconds=60,
    )
    app = create_app(settings=settings)
    client = TestClient(app, headers={"X-API-Key": "dummy"})
    # First request to a non-excluded path passes (no DB needed for 429 test)
    r1 = client.get("/v1/worker/health")
    assert r1.status_code == 200
    # Second request should be rate limited
    r2 = client.get("/v1/worker/health")
    assert r2.status_code == 429
