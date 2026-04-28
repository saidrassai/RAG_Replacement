from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from lattice_jit.contracts import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    SnapshotResponse,
    SnapshotStatus,
)
from lattice_jit.core import generate_id, stable_hash, utcnow
from lattice_jit.storage import SourceSnapshotRecord, StorageRepository


@dataclass(slots=True)
class PdfSnapshotService:
    repository: StorageRepository

    def ingest(self, *, tenant_id: UUID, pdf_path: str, page_mode: str = "document") -> SnapshotResponse:
        """Ingest a PDF file or directory of PDFs.

        Args:
            tenant_id: Tenant identifier.
            pdf_path: Path to a PDF file or directory of PDFs.
            page_mode: 'document' (one node per file) or 'page' (one node per page).
        """
        # Create pending snapshot record
        snapshot_id = generate_id()
        root_node = KnowledgeNode(
            tenant_id=tenant_id,
            snapshot_id=snapshot_id,
            node_type=NodeType.SOURCE,
            title=f"PDF Snapshot of {pdf_path}",
            source_uri=pdf_path,
            body_ptr=pdf_path,
            content_hash=stable_hash(pdf_path),
            source_confidence=1.0,
            serving_confidence=1.0,
        )

        record = SourceSnapshotRecord(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            repo_path=pdf_path,
            git_ref=None,
            include_globs=["*.pdf"],
            exclude_globs=[],
            status=SnapshotStatus.PENDING,
            root_node_id=root_node.node_id,
            created_at=utcnow(),
        )
        self.repository.create_source_snapshot(record)
        self.repository.upsert_nodes([root_node])

        # Extract PDFs
        nodes = [root_node]
        edges: list[KnowledgeEdge] = []
        path = Path(pdf_path).expanduser().resolve()

        pdf_files: list[Path] = []
        if path.is_file() and path.suffix.lower() == ".pdf":
            pdf_files = [path]
        elif path.is_dir():
            pdf_files = sorted(path.rglob("*.pdf"))
        else:
            pass  # No PDFs found

        for pdf_file in pdf_files:
            try:
                doc_text, pages = self._extract_pdf(pdf_file, page_mode)
            except Exception:
                continue

            source_uri = str(pdf_file)
            if page_mode == "page" and pages:
                doc_node = KnowledgeNode(
                    tenant_id=tenant_id,
                    snapshot_id=snapshot_id,
                    node_type=NodeType.SOURCE,
                    title=pdf_file.name,
                    source_uri=source_uri,
                    body_ptr=str(pdf_file.relative_to(path.parent if path.is_dir() else path.parent)),
                    body_text=doc_text[:2000],
                    content_hash=stable_hash(source_uri, doc_text[:2000]),
                    source_confidence=1.0,
                    serving_confidence=1.0,
                )
                nodes.append(doc_node)
                edges.append(
                    KnowledgeEdge(
                        tenant_id=tenant_id,
                        from_node_id=doc_node.node_id,
                        to_node_id=root_node.node_id,
                        edge_type=EdgeType.BELONGS_TO,
                        evidence_spans=[{"path": source_uri}],
                    )
                )
                for i, page_text in enumerate(pages):
                    page_node = KnowledgeNode(
                        tenant_id=tenant_id,
                        snapshot_id=snapshot_id,
                        node_type=NodeType.SECTION,
                        title=f"{pdf_file.name} -- page {i + 1}",
                        source_uri=source_uri,
                        body_ptr=(
                            f"{pdf_file.relative_to(path.parent) if path.is_dir() else pdf_file.name}"
                            f"#page={i + 1}"
                        ),
                        body_text=page_text[:2000],
                        content_hash=stable_hash(source_uri, str(i), page_text[:500]),
                        source_confidence=1.0,
                        serving_confidence=1.0,
                    )
                    nodes.append(page_node)
                    edges.append(
                        KnowledgeEdge(
                            tenant_id=tenant_id,
                            from_node_id=page_node.node_id,
                            to_node_id=doc_node.node_id,
                            edge_type=EdgeType.BELONGS_TO,
                            evidence_spans=[{"path": source_uri, "page": i + 1}],
                        )
                    )
            else:
                doc_node = KnowledgeNode(
                    tenant_id=tenant_id,
                    snapshot_id=snapshot_id,
                    node_type=NodeType.SECTION,
                    title=pdf_file.name,
                    source_uri=source_uri,
                    body_ptr=str(pdf_file.relative_to(path.parent if path.is_dir() else path.parent)),
                    body_text=doc_text[:2000],
                    content_hash=stable_hash(source_uri, doc_text[:2000]),
                    source_confidence=1.0,
                    serving_confidence=1.0,
                )
                nodes.append(doc_node)
                edges.append(
                    KnowledgeEdge(
                        tenant_id=tenant_id,
                        from_node_id=doc_node.node_id,
                        to_node_id=root_node.node_id,
                        edge_type=EdgeType.BELONGS_TO,
                        evidence_spans=[{"path": source_uri}],
                    )
                )

        self.repository.upsert_nodes(nodes)
        self.repository.upsert_edges(edges)
        self.repository.mark_snapshot_completed(snapshot_id, root_node.node_id)
        return SnapshotResponse(
            tenant_id=tenant_id,
            snapshot_id=snapshot_id,
            root_node_id=root_node.node_id,
            status=SnapshotStatus.COMPLETED,
        )

    def _extract_pdf(self, pdf_path: Path, page_mode: str) -> tuple[str, list[str]]:
        try:
            from pypdf2 import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "pypdf2 is not installed. Install it with: pip install pypdf2"
            ) from exc

        reader = PdfReader(str(pdf_path))
        pages: list[str] = []
        full_text_parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            full_text_parts.append(text)
            if page_mode == "page":
                pages.append(text)
        return "\n".join(full_text_parts), pages
