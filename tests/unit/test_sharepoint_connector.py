from __future__ import annotations

from uuid import uuid4

from lattice_jit.connectors.sharepoint import SharePointSnapshotService
from lattice_jit.storage import StorageRepository, build_database


def _make_repo() -> StorageRepository:
    db = build_database("sqlite+pysqlite:///:memory:")
    repo = StorageRepository(db)
    repo.create_schema()
    return repo


def test_sharepoint_service_imports() -> None:
    from lattice_jit.connectors.sharepoint import SharePointSnapshotService as Svc
    assert Svc is not None


def test_sharepoint_creates_pending_snapshot() -> None:
    repo = _make_repo()
    service = SharePointSnapshotService(repo)
    snapshot_id = service.create_pending_snapshot(
        tenant_id=uuid4(),
        site_url="https://example.sharepoint.com/sites/Policies",
        drive_name="Documents",
        folder_path="/Compliance",
    )
    snapshot = repo.get_source_snapshot(snapshot_id)
    assert snapshot is not None
    assert snapshot.status.value == "pending"


def test_sharepoint_node_creation_pattern() -> None:
    repo = _make_repo()
    service = SharePointSnapshotService(repo)
    tenant_id = uuid4()
    snapshot_id = service.create_pending_snapshot(
        tenant_id=tenant_id,
        site_url="https://example.sharepoint.com/sites/Policies",
        drive_name="Docs",
        folder_path="/",
    )
    nodes = repo.list_snapshot_nodes(snapshot_id)
    assert len(nodes) >= 1
    root = nodes[0]
    assert root.tenant_id == tenant_id
    assert root.node_type.value == "source"


def test_sharepoint_connector_importable() -> None:
    from lattice_jit.connectors.sharepoint import SharePointSnapshotService

    repo = _make_repo()
    service = SharePointSnapshotService(repo)
    assert service is not None
    assert hasattr(service, "ingest")
    assert hasattr(service, "create_pending_snapshot")
    assert hasattr(service, "continue_ingest")
