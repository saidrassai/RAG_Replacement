from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import Request, Response

logger = logging.getLogger(__name__)

EXCLUDED_AUTH_PATHS: set[str] = {"/healthz", "/v1/opa/health"}


def parse_api_keys(raw: str) -> dict[str, UUID]:
    """Parse a comma-separated string of key=tenant_id pairs into a dict."""
    keys: dict[str, UUID] = {}
    if not raw.strip():
        return keys
    for pair in raw.split(","):
        pair = pair.strip()
        if "=" not in pair:
            continue
        key, tenant_str = pair.split("=", 1)
        try:
            keys[key.strip()] = UUID(tenant_str.strip())
        except ValueError:
            logger.warning("Invalid tenant_id in auth_api_keys: %s", tenant_str.strip())
    return keys


def build_auth_middleware(
    enabled: bool = False,
    api_keys: dict[str, UUID] | None = None,
    excluded_paths: set[str] | None = None,
) -> Callable:
    excluded = excluded_paths or EXCLUDED_AUTH_PATHS
    keys = api_keys or {}

    async def middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not enabled or request.url.path in excluded:
            response = await call_next(request)
            return response

        auth_header: str | None = request.headers.get("X-API-Key")
        if auth_header is None:
            return Response(
                content='{"detail":"Missing X-API-Key header"}',
                status_code=401,
                headers={"Content-Type": "application/json"},
            )

        tenant_id = keys.get(auth_header)
        if tenant_id is None:
            return Response(
                content='{"detail":"Invalid API key"}',
                status_code=401,
                headers={"Content-Type": "application/json"},
            )

        request.state.tenant_id = tenant_id
        response = await call_next(request)
        return response

    return middleware


def get_tenant_id(request: Request, tenant_id: UUID | None = None) -> UUID:
    """Dependency that resolves tenant_id from auth middleware state or query param."""
    from_auth: UUID | None = getattr(request.state, "tenant_id", None)
    if from_auth is not None:
        return from_auth
    if tenant_id is not None:
        return tenant_id
    from lattice_jit.core.settings import get_settings

    return get_settings().default_tenant_id
