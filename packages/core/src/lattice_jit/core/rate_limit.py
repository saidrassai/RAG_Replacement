from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from fastapi import Request, Response


class RateLimiter:
    def __init__(
        self,
        enabled: bool = False,
        max_per_minute: int = 60,
        window_seconds: int = 60,
        ingest_max_per_minute: int = 10,
        export_max_per_minute: int = 5,
    ) -> None:
        self.enabled = enabled
        self.max_per_minute = max_per_minute
        self.window_seconds = window_seconds
        self.ingest_max_per_minute = ingest_max_per_minute
        self.export_max_per_minute = export_max_per_minute
        self._windows: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, endpoint: str = "default") -> bool:
        if not self.enabled:
            return True
        bucket = f"{key}:{self._tier(endpoint)}"
        now = time.monotonic()
        cutoff = now - self.window_seconds
        timestamps = self._windows[bucket]
        timestamps[:] = [t for t in timestamps if t > cutoff]
        limit = self._limit_for_tier(endpoint)
        if len(timestamps) >= limit:
            return False
        timestamps.append(now)
        return True

    def _tier(self, endpoint: str) -> str:
        if "snapshot" in endpoint or "ingest" in endpoint:
            return "ingest"
        if "export" in endpoint:
            return "export"
        return "query"

    def _limit_for_tier(self, endpoint: str) -> int:
        tier = self._tier(endpoint)
        if tier == "ingest":
            return self.ingest_max_per_minute
        if tier == "export":
            return self.export_max_per_minute
        return self.max_per_minute

    def retry_after(self, key: str, endpoint: str = "default") -> int:
        bucket = f"{key}:{self._tier(endpoint)}"
        timestamps = self._windows.get(bucket, [])
        if not timestamps:
            return 1
        oldest = min(timestamps)
        return max(1, int(self.window_seconds - (time.monotonic() - oldest)))


def build_rate_limit_middleware(
    limiter: RateLimiter,
    excluded_paths: set[str] | None = None,
) -> Callable:
    excluded = excluded_paths or {"/healthz", "/v1/opa/health"}

    async def middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path in excluded:
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        key = str(tenant_id) if tenant_id else request.client.host if request.client else "unknown"

        if not limiter.is_allowed(key, request.url.path):
            retry_after = limiter.retry_after(key, request.url.path)
            return Response(
                content='{"detail":"Too many requests"}',
                status_code=429,
                headers={"Retry-After": str(retry_after), "Content-Type": "application/json"},
            )

        return await call_next(request)

    return middleware
