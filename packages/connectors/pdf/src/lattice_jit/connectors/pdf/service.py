from __future__ import annotations

import json
import re
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


def _format_tables_as_grid(tables: list) -> str:
    """Fallback: convert pdfplumber table lists into ASCII grid format."""
    if not tables:
        return ""
    parts = ["\n\n--- TABLES ---"]
    for t_idx, table in enumerate(tables):
        if not table:
            continue
        col_widths: list[int] = []
        for row in table[:30]:
            for ci, cell in enumerate(row):
                w = len(str(cell or ""))
                if ci >= len(col_widths):
                    col_widths.append(w)
                else:
                    col_widths[ci] = max(col_widths[ci], w)
        col_widths = [max(w, 4) for w in col_widths]
        sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
        parts.append(f"\nTable {t_idx + 1}:")
        parts.append(sep)
        header = "|" + "|".join(f" {str(c or '').ljust(w)} " for c, w in zip(table[0], col_widths, strict=True)) + "|"
        parts.append(header)
        parts.append(sep)
        for row in table[1:30]:
            cells = []
            for ci, cell in enumerate(row):
                w = col_widths[ci] if ci < len(col_widths) else 8
                cells.append(f" {str(cell or '').ljust(w)} ")
            while len(cells) < len(col_widths):
                cells.append(f" {'':<{col_widths[len(cells)]}} ")
            parts.append("|" + "|".join(cells) + "|")
        parts.append(sep)
    return "\n".join(parts)


def _format_tables_as_markdown(tables: list) -> str:
    """Convert pdfplumber table lists into Markdown tables for LLM readability."""
    if not tables:
        return ""
    try:
        import pandas as pd
    except ImportError:
        # Fallback to ASCII grid if pandas unavailable
        return _format_tables_as_grid(tables)
    
    parts = ["\n\n### Extracted Tables"]
    for t_idx, table in enumerate(tables):
        if not table or len(table) < 2:
            continue
        try:
            df = pd.DataFrame(table[1:], columns=table[0])
            parts.append(f"\n**Table {t_idx + 1}:**\n{df.to_markdown(index=False)}")
        except Exception:
            parts.append(f"\n**Table {t_idx + 1} (raw):**\n{_format_tables_as_grid([table])}")
    return "\n".join(parts)


SECTION_HEADING_PATTERN = re.compile(
    r"^(PART\s+[IVX]+|Item\s+\d+[A-Z]?\.|[A-Z][A-Z\s]{10,}|"
    r"Note\s+\d+|Table of Contents|UNITED STATES.*COMMISSION|"
    r"Management.s\s+Discussion|Quantitative\s+and\s+Qualitative|"
    r"Financial\s+Statements|Consolidated\s+Balance|"
    r"Consolidated\s+Statements|Notes\s+to\s+Consolidated|"
    r"Report\s+of\s+Independent|Risk\s+Factors|Business\s*$|"
    r"Selected\s+Financial|Market\s+Risk)",
    re.MULTILINE | re.IGNORECASE,
)


@dataclass(slots=True)
class PdfSnapshotService:
    repository: StorageRepository

    # ── Original pypdf2 ingestion (backward compatible) ─────────────────

    def ingest(self, *, tenant_id: UUID, pdf_path: str, page_mode: str = "document") -> SnapshotResponse:
        normalized_mode = page_mode.strip().lower()
        if normalized_mode in {"pymupdf4llm", "markdown", "cpu"}:
            return self.ingest_pymupdf4llm(tenant_id=tenant_id, pdf_path=pdf_path)
        if normalized_mode in {"structured", "pdfplumber"}:
            return self.ingest_structured(tenant_id=tenant_id, pdf_path=pdf_path)
        if normalized_mode == "docling":
            return self.ingest_docling(tenant_id=tenant_id, pdf_path=pdf_path)
        return self._ingest_impl(tenant_id=tenant_id, pdf_path=pdf_path, page_mode=page_mode, structured=False)

    # ── Structured pdfplumber ingestion (table-preserving, section hierarchy) ─

    def ingest_structured(self, *, tenant_id: UUID, pdf_path: str) -> SnapshotResponse:
        return self._ingest_impl(tenant_id=tenant_id, pdf_path=pdf_path, page_mode="page", structured=True)

    # ── CPU-first PyMuPDF4LLM ingestion (Markdown/page chunks) ───────────

    def ingest_pymupdf4llm(self, *, tenant_id: UUID, pdf_path: str) -> SnapshotResponse:
        return self._ingest_impl(tenant_id=tenant_id, pdf_path=pdf_path, page_mode="page", structured="pymupdf4llm")

    def ingest_docling(self, *, tenant_id: UUID, pdf_path: str) -> SnapshotResponse:
        """Ingest using IBM Docling for layout-aware extraction."""
        return self._ingest_impl(tenant_id=tenant_id, pdf_path=pdf_path, page_mode="page", structured="docling")

    # ── Shared implementation ──────────────────────────────────────────

    def _ingest_impl(
        self, *, tenant_id: UUID, pdf_path: str, page_mode: str, structured: bool | str
    ) -> SnapshotResponse:
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

        nodes = [root_node]
        edges: list[KnowledgeEdge] = []
        path = Path(pdf_path).expanduser().resolve()

        pdf_files: list[Path] = []
        if path.is_file() and path.suffix.lower() == ".pdf":
            pdf_files = [path]
        elif path.is_dir():
            pdf_files = sorted(path.rglob("*.pdf"))
        else:
            pass

        for pdf_file in pdf_files:
            try:
                if structured == "pymupdf4llm":
                    self._ingest_pymupdf4llm_pdf(pdf_file, path, snapshot_id, tenant_id, nodes, edges)
                elif structured == "docling":
                    self._ingest_docling_pdf(pdf_file, path, snapshot_id, tenant_id, nodes, edges)
                elif structured:
                    self._ingest_structured_pdf(pdf_file, path, snapshot_id, tenant_id, nodes, edges)
                else:
                    doc_text, pages = self._extract_pdf_pypdf2(pdf_file)
                    self._build_flat_nodes(
                        pdf_file, path, doc_text, pages, snapshot_id, tenant_id, nodes, edges, page_mode
                    )
            except Exception as exc:
                # Fallback: if structured (pdfplumber) failed, try pypdf2
                if structured and not isinstance(structured, str):
                    try:
                        doc_text, pages = self._extract_pdf_pypdf2(pdf_file)
                        self._build_flat_nodes(
                            pdf_file, path, doc_text, pages, snapshot_id, tenant_id, nodes, edges, page_mode
                        )
                    except Exception:
                        pass
                    continue
                # Non-structured path: don't swallow — re-raise so we see the real error
                raise RuntimeError(f"Failed to ingest {pdf_file}: {exc}") from exc

        self.repository.upsert_nodes(nodes)
        self.repository.upsert_edges(edges)
        self.repository.mark_snapshot_completed(snapshot_id, root_node.node_id)
        return SnapshotResponse(
            tenant_id=tenant_id,
            snapshot_id=snapshot_id,
            root_node_id=root_node.node_id,
            status=SnapshotStatus.COMPLETED,
        )

    # ── Structured PDF ingestion with pdfplumber ────────────────────────

    def _ingest_structured_pdf(
        self,
        pdf_file: Path,
        base_path: Path,
        snapshot_id: UUID,
        tenant_id: UUID,
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
    ) -> None:
        pages_data = self._extract_pdf_structured(pdf_file)
        if not pages_data:
            return

        source_uri = str(pdf_file)
        doc_name = pdf_file.name

        # Document-level node
        doc_node = KnowledgeNode(
            tenant_id=tenant_id,
            snapshot_id=snapshot_id,
            node_type=NodeType.SOURCE,
            title=doc_name,
            source_uri=source_uri,
            body_ptr=str(pdf_file.relative_to(base_path.parent if base_path.is_dir() else base_path.parent)),
            body_text=pages_data[0]["text"][:3000] if pages_data else "",
            content_hash=stable_hash(source_uri),
            source_confidence=1.0,
            serving_confidence=1.0,
        )
        doc_idx = len(nodes)
        nodes.append(doc_node)
        edges.append(KnowledgeEdge(
            tenant_id=tenant_id, from_node_id=doc_node.node_id,
            to_node_id=nodes[0].node_id, edge_type=EdgeType.BELONGS_TO,
            evidence_spans=[{"path": source_uri}],
        ))

        # Detect sections from page headings
        sections: dict[str, list[int]] = {}
        current_section = "Front Matter"
        for pd_ in pages_data:
            page_num = pd_["page"]
            text = pd_["text"]
            heading_match = SECTION_HEADING_PATTERN.search(text[:500])
            if heading_match:
                current_section = heading_match.group(0).strip()[:120]
            sections.setdefault(current_section, []).append(page_num)

        # Create section-level nodes
        section_nodes: dict[str, int] = {}
        for sec_title, sec_pages in sections.items():
            sec_text_parts = []
            sec_tables = []
            for pg in sec_pages:
                pd_ = pages_data[pg - 1]  # 0-indexed
                sec_text_parts.append(pd_["text"])
                sec_tables.extend(pd_.get("tables", []))

            sec_body = f"Pages: {min(sec_pages)}-{max(sec_pages)}\n\n" + "\n".join(sec_text_parts)
            sec_metadata = {
                "page_range": [min(sec_pages), max(sec_pages)],
                "tables": sec_tables[:50],  # Cap table count
            }

            sec_node = KnowledgeNode(
                tenant_id=tenant_id,
                snapshot_id=snapshot_id,
                node_type=NodeType.SECTION,
                title=f"{doc_name} — {sec_title}",
                source_uri=f"{source_uri}#pages={min(sec_pages)}-{max(sec_pages)}",
                body_ptr=f"{doc_name}#section={sec_title[:80]}",
                body_text=sec_body,
                content_hash=stable_hash(source_uri, sec_title),
                source_confidence=1.0,
                serving_confidence=1.0,
                metadata={"structured_section": True, "tables_json": json.dumps(sec_metadata["tables"])},
            )
            section_nodes[sec_title] = len(nodes)
            nodes.append(sec_node)
            edges.append(KnowledgeEdge(
                tenant_id=tenant_id, from_node_id=sec_node.node_id,
                to_node_id=doc_node.node_id, edge_type=EdgeType.BELONGS_TO,
                evidence_spans=[{"path": source_uri, "section": sec_title[:80]}],
            ))

        # Create page-level nodes (children of sections)
        for pd_ in pages_data:
            page_num = pd_["page"]
            # Find which section this page belongs to
            parent_sec = "Front Matter"
            for sec_title, sec_pages in sections.items():
                if page_num in sec_pages:
                    parent_sec = sec_title
                    break

            parent_node_idx = section_nodes.get(parent_sec, doc_idx)
            tables_str = _format_tables_as_markdown(pd_.get("tables", []))
            page_text = pd_["text"] + tables_str
            page_node = KnowledgeNode(
                tenant_id=tenant_id,
                snapshot_id=snapshot_id,
                node_type=NodeType.SECTION,
                title=f"{doc_name} — page {page_num} [{parent_sec[:60]}]",
                source_uri=source_uri,
                body_ptr=f"{doc_name}#page={page_num}",
                body_text=page_text,
                content_hash=stable_hash(source_uri, str(page_num), pd_["text"][:500]),
                source_confidence=1.0,
                serving_confidence=1.0,
                metadata={"page": page_num, "section": parent_sec[:80], "has_tables": bool(pd_.get("tables"))},
            )
            nodes.append(page_node)
            edges.append(KnowledgeEdge(
                tenant_id=tenant_id, from_node_id=page_node.node_id,
                to_node_id=nodes[parent_node_idx].node_id, edge_type=EdgeType.BELONGS_TO,
                evidence_spans=[{"path": source_uri, "page": page_num, "section": parent_sec[:80]}],
            ))

    # ── PDF Extraction ─────────────────────────────────────────────────

    def _extract_pdf_structured(self, pdf_path: Path) -> list[dict]:
        """Extract PDF pages with pdfplumber, preserving tables."""
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError("pdfplumber is not installed. Install it with: pip install pdfplumber") from exc

        pages_data = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []
                pages_data.append({
                    "page": page_num,
                    "text": text,
                    "tables": tables,
                })
        return pages_data

    def _ingest_pymupdf4llm_pdf(
        self, pdf_file: Path, base_path: Path, snapshot_id: UUID,
        tenant_id: UUID, nodes: list[KnowledgeNode], edges: list[KnowledgeEdge],
    ) -> None:
        """Ingest PDF using PyMuPDF4LLM Markdown chunks on CPU."""
        pages_data = self._extract_pdf_pymupdf4llm(pdf_file)
        if not pages_data:
            return

        source_uri = str(pdf_file)
        doc_node = KnowledgeNode(
            tenant_id=tenant_id,
            snapshot_id=snapshot_id,
            node_type=NodeType.SOURCE,
            title=pdf_file.name,
            source_uri=source_uri,
            body_ptr=str(pdf_file.relative_to(base_path.parent if base_path.is_dir() else base_path.parent)),
            body_text="\n\n".join(page["text"] for page in pages_data)[:3000],
            content_hash=stable_hash(source_uri, "pymupdf4llm", pages_data[0]["text"][:2000]),
            source_confidence=1.0,
            serving_confidence=1.0,
            metadata={"extractor": "pymupdf4llm", "format": "markdown"},
        )
        nodes.append(doc_node)
        edges.append(KnowledgeEdge(
            tenant_id=tenant_id, from_node_id=doc_node.node_id,
            to_node_id=nodes[0].node_id, edge_type=EdgeType.BELONGS_TO,
            evidence_spans=[{"path": source_uri, "extractor": "pymupdf4llm"}],
        ))

        for page in pages_data:
            page_num = int(page["page"])
            page_text = page["text"]
            page_node = KnowledgeNode(
                tenant_id=tenant_id,
                snapshot_id=snapshot_id,
                node_type=NodeType.SECTION,
                title=f"{pdf_file.name} -- page {page_num} [PyMuPDF4LLM]",
                source_uri=f"{source_uri}#page={page_num}",
                body_ptr=f"{pdf_file.name}#pymupdf4llm-page={page_num}",
                body_text=page_text,
                content_hash=stable_hash(source_uri, "pymupdf4llm", str(page_num), page_text[:500]),
                source_confidence=1.0,
                serving_confidence=1.0,
                metadata={"page": page_num, "extractor": "pymupdf4llm", "format": "markdown"},
            )
            nodes.append(page_node)
            edges.append(KnowledgeEdge(
                tenant_id=tenant_id, from_node_id=page_node.node_id,
                to_node_id=doc_node.node_id, edge_type=EdgeType.BELONGS_TO,
                evidence_spans=[{"path": source_uri, "page": page_num, "extractor": "pymupdf4llm"}],
            ))

    def _ingest_docling_pdf(
        self, pdf_file: Path, base_path: Path, snapshot_id: UUID,
        tenant_id: UUID, nodes: list[KnowledgeNode], edges: list[KnowledgeEdge],
    ) -> None:
        """Ingest PDF using docling: one document node with full markdown."""
        pages_data = self._extract_pdf_docling(pdf_file)
        if not pages_data:
            return
        source_uri = str(pdf_file)
        doc_node = KnowledgeNode(
            tenant_id=tenant_id, snapshot_id=snapshot_id, node_type=NodeType.SOURCE,
            title=pdf_file.name, source_uri=source_uri,
            body_ptr=str(pdf_file.relative_to(base_path.parent if base_path.is_dir() else base_path.parent)),
            body_text=pages_data[0]["text"][:3000],
            content_hash=stable_hash(source_uri, pages_data[0]["text"][:2000]),
            source_confidence=1.0, serving_confidence=1.0,
        )
        nodes.append(doc_node)
        edges.append(KnowledgeEdge(
            tenant_id=tenant_id, from_node_id=doc_node.node_id,
            to_node_id=nodes[0].node_id, edge_type=EdgeType.BELONGS_TO,
            evidence_spans=[{"path": source_uri}],
        ))
        section_node = KnowledgeNode(
            tenant_id=tenant_id, snapshot_id=snapshot_id, node_type=NodeType.SECTION,
            title=f"{pdf_file.name} — Full Document (Docling)",
            source_uri=source_uri,
            body_ptr=f"{pdf_file.name}#docling",
            body_text=pages_data[0]["text"],
            content_hash=stable_hash(source_uri, "docling", pages_data[0]["text"][:500]),
            source_confidence=1.0, serving_confidence=1.0,
        )
        nodes.append(section_node)
        edges.append(KnowledgeEdge(
            tenant_id=tenant_id, from_node_id=section_node.node_id,
            to_node_id=doc_node.node_id, edge_type=EdgeType.BELONGS_TO,
            evidence_spans=[{"path": source_uri, "extractor": "docling"}],
        ))

    # ── PDF Extraction Backends ──────────────────────────────────────────

    def _extract_pdf_pymupdf4llm(self, pdf_path: Path) -> list[dict]:
        """Extract Markdown page chunks with PyMuPDF4LLM.

        PyMuPDF4LLM is the default CPU-friendly parser for RAG tests. It avoids
        the Docling/Torch/OCR dependency chain while preserving Markdown useful
        for chunking and citation snippets.
        """
        try:
            import pymupdf4llm
        except ImportError as exc:
            raise RuntimeError("pymupdf4llm is not installed. Install it with: pip install pymupdf4llm") from exc

        try:
            chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True, show_progress=False)
        except TypeError:
            chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)

        if isinstance(chunks, str):
            text = chunks.strip()
            return [{"page": 1, "text": text, "tables": []}] if text else []

        pages_data: list[dict] = []
        for idx, chunk in enumerate(chunks, start=1):
            if isinstance(chunk, dict):
                text_obj = chunk.get("text") or chunk.get("md") or chunk.get("content") or ""
                text = str(text_obj).strip()
                metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
                page_raw = chunk.get("page") or metadata.get("page") or metadata.get("page_number")
                page_num = idx
                if isinstance(page_raw, int) and page_raw >= 1:
                    page_num = page_raw
                elif isinstance(page_raw, str) and page_raw.isdigit() and int(page_raw) >= 1:
                    page_num = int(page_raw)
            else:
                text = str(chunk).strip()
                page_num = idx
            if text:
                pages_data.append({"page": page_num, "text": text, "tables": []})

        return pages_data

    def _extract_pdf_docling(self, pdf_path: Path) -> list[dict]:
        """Extract PDF with IBM Docling — one page node with full markdown + table structure."""
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise RuntimeError("docling is not installed. Install it with: pip install docling") from exc

        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        full_md = result.document.export_to_markdown()
        return [{"page": 1, "text": full_md, "tables": []}]

    def _extract_pdf_pypdf2(self, pdf_path: Path) -> tuple[str, list[str]]:
        """Legacy extraction using pypdf2."""
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            try:
                from pypdf2 import PdfReader  # older package name
            except ImportError as exc:
                raise RuntimeError("pypdf2/PyPDF2 is not installed. Install it with: pip install PyPDF2") from exc

        reader = PdfReader(str(pdf_path))
        pages: list[str] = []
        full_text_parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            full_text_parts.append(text)
            pages.append(text)
        return "\n".join(full_text_parts), pages

    # ── Flat node builder (original behavior) ──────────────────────────

    def _build_flat_nodes(
        self, pdf_file: Path, base_path: Path, doc_text: str, pages: list[str],
        snapshot_id: UUID, tenant_id: UUID, nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge], page_mode: str,
    ) -> None:
        source_uri = str(pdf_file)
        if page_mode == "page" and pages:
            doc_node = KnowledgeNode(
                tenant_id=tenant_id, snapshot_id=snapshot_id, node_type=NodeType.SOURCE,
                title=pdf_file.name, source_uri=source_uri,
                body_ptr=str(pdf_file.relative_to(base_path.parent if base_path.is_dir() else base_path.parent)),
                body_text=doc_text[:2000], content_hash=stable_hash(source_uri, doc_text[:2000]),
                source_confidence=1.0, serving_confidence=1.0,
            )
            nodes.append(doc_node)
            edges.append(KnowledgeEdge(
                tenant_id=tenant_id, from_node_id=doc_node.node_id,
                to_node_id=nodes[0].node_id, edge_type=EdgeType.BELONGS_TO,
                evidence_spans=[{"path": source_uri}],
            ))
            for i, page_text in enumerate(pages):
                page_node = KnowledgeNode(
                    tenant_id=tenant_id, snapshot_id=snapshot_id, node_type=NodeType.SECTION,
                    title=f"{pdf_file.name} -- page {i + 1}", source_uri=source_uri,
                    body_ptr=f"{pdf_file.name}#page={i + 1}", body_text=page_text[:2000],
                    content_hash=stable_hash(source_uri, str(i), page_text[:500]),
                    source_confidence=1.0, serving_confidence=1.0,
                )
                nodes.append(page_node)
                edges.append(KnowledgeEdge(
                    tenant_id=tenant_id, from_node_id=page_node.node_id,
                    to_node_id=doc_node.node_id, edge_type=EdgeType.BELONGS_TO,
                    evidence_spans=[{"path": source_uri, "page": i + 1}],
                ))
        else:
            doc_node = KnowledgeNode(
                tenant_id=tenant_id, snapshot_id=snapshot_id, node_type=NodeType.SECTION,
                title=pdf_file.name, source_uri=source_uri,
                body_ptr=str(pdf_file.relative_to(base_path.parent if base_path.is_dir() else base_path.parent)),
                body_text=doc_text[:2000], content_hash=stable_hash(source_uri, doc_text[:2000]),
                source_confidence=1.0, serving_confidence=1.0,
            )
            nodes.append(doc_node)
            edges.append(KnowledgeEdge(
                tenant_id=tenant_id, from_node_id=doc_node.node_id,
                to_node_id=nodes[0].node_id, edge_type=EdgeType.BELONGS_TO,
                evidence_spans=[{"path": source_uri}],
            ))
