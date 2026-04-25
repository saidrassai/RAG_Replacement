from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from lattice_jit.contracts import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    SnapshotGitRequest,
    SnapshotResponse,
    SnapshotStatus,
)
from lattice_jit.core import generate_id, stable_hash, utcnow
from lattice_jit.storage import SourceSnapshotRecord, StorageRepository


@dataclass(slots=True)
class GitLocalSnapshotService:
    repository: StorageRepository

    def ingest(self, request: SnapshotGitRequest) -> SnapshotResponse:
        snapshot_id = self.create_pending_snapshot(request)
        return self.continue_ingest(snapshot_id)

    def create_pending_snapshot(self, request: SnapshotGitRequest) -> UUID:
        snapshot_id = self._new_snapshot_id(request)
        root_node = KnowledgeNode(
            tenant_id=request.tenant_id,
            snapshot_id=snapshot_id,
            node_type=NodeType.SOURCE,
            title=f"Snapshot of {request.repo_path}",
            source_uri=request.repo_path,
            body_ptr=request.repo_path,
            content_hash=stable_hash(request.repo_path, request.git_ref or "working-tree"),
            snapshot_ref=request.git_ref,
            source_confidence=1.0,
            serving_confidence=1.0,
        )

        snapshot_record = SourceSnapshotRecord(
            snapshot_id=snapshot_id,
            tenant_id=request.tenant_id,
            repo_path=request.repo_path,
            git_ref=request.git_ref,
            include_globs=request.include_globs,
            exclude_globs=request.exclude_globs,
            status=SnapshotStatus.PENDING,
            root_node_id=root_node.node_id,
            created_at=utcnow(),
        )
        self.repository.create_source_snapshot(snapshot_record)
        self.repository.upsert_nodes([root_node])
        return snapshot_id

    def continue_ingest(self, snapshot_id: UUID) -> SnapshotResponse:
        snapshot = self.repository.get_source_snapshot(snapshot_id)
        if snapshot is None:
            raise ValueError(f"Snapshot {snapshot_id} was not found.")
        if snapshot.status == SnapshotStatus.COMPLETED and snapshot.root_node_id is not None:
            return SnapshotResponse(
                snapshot_id=snapshot.snapshot_id,
                root_node_id=snapshot.root_node_id,
                status=snapshot.status,
            )
        if snapshot.root_node_id is None:
            raise ValueError(f"Snapshot {snapshot_id} is missing a root node.")

        root_node = self.repository.get_node(snapshot.root_node_id)
        if root_node is None:
            raise ValueError(f"Root node {snapshot.root_node_id} was not found for snapshot {snapshot_id}.")

        request = SnapshotGitRequest(
            tenant_id=snapshot.tenant_id,
            repo_path=snapshot.repo_path,
            git_ref=snapshot.git_ref,
            include_globs=snapshot.include_globs,
            exclude_globs=snapshot.exclude_globs,
        )

        nodes = [root_node]
        edges: list[KnowledgeEdge] = []
        for relative_path, content, snapshot_ref in self._iter_files(request):
            source_uri = str(Path(snapshot.repo_path) / relative_path)
            node = KnowledgeNode(
                tenant_id=snapshot.tenant_id,
                snapshot_id=snapshot.snapshot_id,
                node_type=NodeType.SECTION,
                title=relative_path,
                source_uri=source_uri,
                body_ptr=relative_path,
                body_text=content,
                content_hash=stable_hash(relative_path, content, snapshot_ref or "working-tree"),
                snapshot_ref=snapshot_ref,
                source_confidence=1.0,
                serving_confidence=1.0,
            )
            nodes.append(node)
            edges.append(
                KnowledgeEdge(
                    tenant_id=request.tenant_id,
                    from_node_id=node.node_id,
                    to_node_id=root_node.node_id,
                    edge_type=EdgeType.BELONGS_TO,
                    evidence_spans=[{"path": relative_path}],
                )
            )

        self.repository.upsert_nodes(nodes)
        self.repository.upsert_edges(edges)
        self.repository.mark_snapshot_completed(snapshot.snapshot_id, root_node.node_id)
        return SnapshotResponse(
            snapshot_id=snapshot.snapshot_id,
            root_node_id=root_node.node_id,
            status=SnapshotStatus.COMPLETED,
        )

    def _iter_files(self, request: SnapshotGitRequest) -> Iterable[tuple[str, str, str | None]]:
        root_path = Path(request.repo_path).expanduser().resolve()
        if request.git_ref and self._is_git_repo(root_path):
            files = self._git_files_at_ref(root_path, request.git_ref)
            for relative_path in files:
                if not self._should_include(relative_path, request.include_globs, request.exclude_globs):
                    continue
                content = self._git_show_text(root_path, request.git_ref, relative_path)
                if content is not None:
                    yield relative_path, content, request.git_ref
            return

        for path in sorted(root_path.rglob("*")):
            if not path.is_file():
                continue
            relative_path = path.relative_to(root_path).as_posix()
            if not self._should_include(relative_path, request.include_globs, request.exclude_globs):
                continue
            content = self._read_text(path)
            if content is not None:
                yield relative_path, content, None

    def _should_include(self, relative_path: str, include_globs: list[str], exclude_globs: list[str]) -> bool:
        path = Path(relative_path)
        if include_globs and not any(path.match(glob) for glob in include_globs):
            return False
        if any(path.match(glob) for glob in exclude_globs):
            return False
        return True

    def _is_git_repo(self, root_path: Path) -> bool:
        result = subprocess.run(
            ["git", "-C", str(root_path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def _git_files_at_ref(self, root_path: Path, git_ref: str) -> list[str]:
        result = subprocess.run(
            ["git", "-C", str(root_path), "ls-tree", "-r", "--name-only", git_ref],
            capture_output=True,
            text=True,
            check=True,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _git_show_text(self, root_path: Path, git_ref: str, relative_path: str) -> str | None:
        result = subprocess.run(
            ["git", "-C", str(root_path), "show", f"{git_ref}:{relative_path}"],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        try:
            return result.stdout.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def _read_text(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return None

    def _new_snapshot_id(self, request: SnapshotGitRequest) -> UUID:
        del request
        return generate_id()
