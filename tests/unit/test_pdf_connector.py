from __future__ import annotations

import sys
from types import SimpleNamespace
from uuid import uuid4

from lattice_jit.connectors.pdf import PdfSnapshotService


def test_pymupdf4llm_ingestion_builds_markdown_page_nodes(container, tmp_path, monkeypatch) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    fake_pymupdf4llm = SimpleNamespace(
        to_markdown=lambda *_args, **_kwargs: [
            {"text": "# Revenue\n\n| Year | Revenue |\n| --- | ---: |\n| 2025 | 112.4 |", "metadata": {"page": 1}},
            {"text": "# Risk\n\nCybersecurity incidents must be reported within 4 business days.", "metadata": {"page": 2}},
        ]
    )
    monkeypatch.setitem(sys.modules, "pymupdf4llm", fake_pymupdf4llm)

    tenant_id = uuid4()
    response = PdfSnapshotService(container.repository).ingest_pymupdf4llm(
        tenant_id=tenant_id,
        pdf_path=str(pdf_path),
    )

    nodes = container.repository.list_snapshot_nodes(response.snapshot_id)
    page_nodes = [node for node in nodes if node.metadata.get("extractor") == "pymupdf4llm"]

    assert response.status.value == "completed"
    assert len(page_nodes) == 3
    assert any("112.4" in (node.body_text or "") for node in page_nodes)
    assert any(node.source_uri and "#page=2" in node.source_uri for node in page_nodes)
