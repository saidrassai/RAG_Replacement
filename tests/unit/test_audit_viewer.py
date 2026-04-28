from __future__ import annotations

import csv
import io
import json
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from lattice_jit.apps.api.main import create_app
from lattice_jit.apps.api.main import get_container as api_get_container
from lattice_jit.contracts import AuditEvent


def _write_test_events(container, tenant_id: UUID, count: int = 5) -> None:
    for i in range(count):
        container.repository.store_audit_event(
            AuditEvent(
                tenant_id=tenant_id,
                event_type="snapshot_ingested" if i % 2 == 0 else "policy_evaluated",
                resource_type="snapshot" if i % 2 == 0 else "policy_bundle",
                resource_id=uuid4() if i < 4 else None,
                payload={"index": i},
            )
        )


def test_filtered_audit_events_by_event_type(container) -> None:
    tenant_id = uuid4()
    _write_test_events(container, tenant_id, count=10)

    items = container.repository.list_audit_events_filtered(
        tenant_id, event_type="snapshot_ingested"
    )
    assert len(items) == 5
    assert all(item.event_type == "snapshot_ingested" for item in items)


def test_filtered_audit_events_by_resource_type(container) -> None:
    tenant_id = uuid4()
    _write_test_events(container, tenant_id, count=10)

    items = container.repository.list_audit_events_filtered(
        tenant_id, resource_type="policy_bundle"
    )
    assert len(items) == 5
    assert all(item.resource_type == "policy_bundle" for item in items)


def test_filtered_audit_events_pagination(container) -> None:
    tenant_id = uuid4()
    _write_test_events(container, tenant_id, count=10)

    page1 = container.repository.list_audit_events_filtered(
        tenant_id, limit=3, offset=0
    )
    page2 = container.repository.list_audit_events_filtered(
        tenant_id, limit=3, offset=3
    )
    assert len(page1) == 3
    assert len(page2) == 3
    ids_page1 = {item.audit_event_id for item in page1}
    ids_page2 = {item.audit_event_id for item in page2}
    assert ids_page1.isdisjoint(ids_page2)


def test_count_audit_events(container) -> None:
    tenant_id = uuid4()
    _write_test_events(container, tenant_id, count=10)

    total = container.repository.count_audit_events(tenant_id)
    assert total == 10

    filtered = container.repository.count_audit_events(
        tenant_id, event_type="snapshot_ingested"
    )
    assert filtered == 5


def test_audit_events_api_returns_paginated_structure(test_settings) -> None:
    from lattice_jit.core import build_container

    container = build_container(test_settings)
    api_get_container.cache_clear()
    tenant_id = uuid4()
    _write_test_events(container, tenant_id, count=5)

    app = create_app()
    app.dependency_overrides[api_get_container] = lambda: container
    client = TestClient(app)

    response = client.get(
        "/v1/audit-events",
        params={"tenant_id": str(tenant_id), "limit": 3, "offset": 0},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 3
    assert payload["total"] == 5
    assert payload["limit"] == 3
    assert payload["offset"] == 0


def test_audit_events_export_csv(test_settings) -> None:
    from lattice_jit.core import build_container

    container = build_container(test_settings)
    api_get_container.cache_clear()
    tenant_id = uuid4()
    _write_test_events(container, tenant_id, count=3)

    app = create_app()
    app.dependency_overrides[api_get_container] = lambda: container
    client = TestClient(app)

    response = client.get(
        "/v1/audit-events/export",
        params={"tenant_id": str(tenant_id), "format": "csv"},
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    reader = csv.reader(io.StringIO(response.text))
    header = next(reader)
    assert "audit_event_id" in header
    assert "event_type" in header
    rows = list(reader)
    assert len(rows) == 3


def test_audit_events_export_json(test_settings) -> None:
    from lattice_jit.core import build_container

    container = build_container(test_settings)
    api_get_container.cache_clear()
    tenant_id = uuid4()
    _write_test_events(container, tenant_id, count=3)

    app = create_app()
    app.dependency_overrides[api_get_container] = lambda: container
    client = TestClient(app)

    response = client.get(
        "/v1/audit-events/export",
        params={"tenant_id": str(tenant_id), "format": "json"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = json.loads(response.text)
    assert len(data) == 3


def test_audit_events_api_with_event_type_filter(test_settings) -> None:
    from lattice_jit.core import build_container

    container = build_container(test_settings)
    api_get_container.cache_clear()
    tenant_id = uuid4()
    _write_test_events(container, tenant_id, count=6)

    app = create_app()
    app.dependency_overrides[api_get_container] = lambda: container
    client = TestClient(app)

    response = client.get(
        "/v1/audit-events",
        params={
            "tenant_id": str(tenant_id),
            "event_type": "policy_evaluated",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert all(item["event_type"] == "policy_evaluated" for item in payload["items"])
