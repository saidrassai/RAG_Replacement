from __future__ import annotations

from uuid import uuid4

from lattice_jit.connectors.confluence import ConfluenceSnapshotService
from lattice_jit.storage import StorageRepository, build_database


def _make_repo() -> StorageRepository:
    db = build_database("sqlite+pysqlite:///:memory:")
    repo = StorageRepository(db)
    repo.create_schema()
    return repo


def test_confluence_service_imports() -> None:
    from lattice_jit.connectors.confluence import ConfluenceSnapshotService as Svc
    assert Svc is not None


def test_confluence_creates_pending_snapshot() -> None:
    repo = _make_repo()
    service = ConfluenceSnapshotService(repo)
    snapshot_id = service.create_pending_snapshot(
        tenant_id=uuid4(),
        confluence_url="https://example.atlassian.net",
        space_key="SEC",
        page_limit=100,
    )
    snapshot = repo.get_source_snapshot(snapshot_id)
    assert snapshot is not None
    assert snapshot.status.value == "pending"


def test_confluence_node_creation_pattern() -> None:
    repo = _make_repo()
    service = ConfluenceSnapshotService(repo)
    tenant_id = uuid4()
    snapshot_id = service.create_pending_snapshot(
        tenant_id=tenant_id,
        confluence_url="https://example.atlassian.net",
        space_key="SEC",
        page_limit=50,
    )
    nodes = repo.list_snapshot_nodes(snapshot_id)
    assert len(nodes) >= 1
    root = nodes[0]
    assert root.tenant_id == tenant_id
    assert root.node_type.value == "source"


def test_confluence_connector_importable() -> None:
    from lattice_jit.connectors.confluence import ConfluenceSnapshotService

    repo = _make_repo()
    service = ConfluenceSnapshotService(repo)
    assert service is not None
    assert hasattr(service, "ingest")
    assert hasattr(service, "create_pending_snapshot")
    assert hasattr(service, "continue_ingest")
