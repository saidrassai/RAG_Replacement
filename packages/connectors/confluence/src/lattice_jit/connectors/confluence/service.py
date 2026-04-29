from __future__ import annotations

from dataclasses import dataclass
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
class ConfluenceSnapshotService:
    repository: StorageRepository

    def ingest(
        self,
        *,
        tenant_id: UUID,
        confluence_url: str,
        space_key: str,
        username: str = "",
        api_token: str = "",
        page_limit: int = 500,
    ) -> SnapshotResponse:
        """Ingest all pages from a Confluence space.

        Args:
            tenant_id: Tenant identifier.
            confluence_url: Base URL of the Confluence instance (e.g. https://my-domain.atlassian.net).
            space_key: Confluence space key to ingest.
            username: Confluence username (email) for Basic Auth.
            api_token: Confluence API token for Basic Auth.
            page_limit: Maximum number of pages to fetch per request.
        """
        snapshot_id = self.create_pending_snapshot(
            tenant_id=tenant_id,
            confluence_url=confluence_url,
            space_key=space_key,
            page_limit=page_limit,
        )
        return self.continue_ingest(
            snapshot_id,
            username=username,
            api_token=api_token,
        )

    def create_pending_snapshot(
        self,
        *,
        tenant_id: UUID,
        confluence_url: str,
        space_key: str,
        page_limit: int = 500,
    ) -> UUID:
        """Create a pending snapshot record and SOURCE node.

        Args:
            tenant_id: Tenant identifier.
            confluence_url: Base URL of the Confluence instance.
            space_key: Confluence space key to ingest.
            page_limit: Maximum number of pages to fetch per request.
        """
        snapshot_id = generate_id()
        root_node = KnowledgeNode(
            tenant_id=tenant_id,
            snapshot_id=snapshot_id,
            node_type=NodeType.SOURCE,
            title=f"Confluence space: {space_key}",
            source_uri=confluence_url,
            body_ptr=f"{confluence_url}/spaces/{space_key}",
            content_hash=stable_hash(confluence_url, space_key, str(page_limit)),
            source_confidence=1.0,
            serving_confidence=1.0,
        )

        snapshot_record = SourceSnapshotRecord(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            repo_path=confluence_url,
            git_ref=space_key,
            include_globs=[str(page_limit)],
            exclude_globs=[],
            status=SnapshotStatus.PENDING,
            root_node_id=root_node.node_id,
            created_at=utcnow(),
        )
        self.repository.create_source_snapshot(snapshot_record)
        self.repository.upsert_nodes([root_node])
        return snapshot_id

    def continue_ingest(
        self,
        snapshot_id: UUID,
        *,
        username: str = "",
        api_token: str = "",
    ) -> SnapshotResponse:
        """Continue ingestion by fetching all pages from the Confluence space.

        Args:
            snapshot_id: The snapshot ID returned by create_pending_snapshot.
            username: Confluence username (email) for Basic Auth.
            api_token: Confluence API token for Basic Auth.
        """
        snapshot = self.repository.get_source_snapshot(snapshot_id)
        if snapshot is None:
            raise ValueError(f"Snapshot {snapshot_id} was not found.")
        if snapshot.status == SnapshotStatus.COMPLETED and snapshot.root_node_id is not None:
            return SnapshotResponse(
                tenant_id=snapshot.tenant_id,
                snapshot_id=snapshot.snapshot_id,
                root_node_id=snapshot.root_node_id,
                status=snapshot.status,
            )
        if snapshot.root_node_id is None:
            raise ValueError(f"Snapshot {snapshot_id} is missing a root node.")

        root_node = self.repository.get_node(snapshot.root_node_id)
        if root_node is None:
            raise ValueError(
                f"Root node {snapshot.root_node_id} was not found for snapshot {snapshot_id}."
            )

        confluence_url = snapshot.repo_path
        space_key = snapshot.git_ref or ""
        page_limit = int(snapshot.include_globs[0]) if snapshot.include_globs else 500

        nodes: list[KnowledgeNode] = [root_node]
        edges: list[KnowledgeEdge] = []

        for page in self._iter_pages(confluence_url, space_key, page_limit, username, api_token):
            page_node = KnowledgeNode(
                tenant_id=snapshot.tenant_id,
                snapshot_id=snapshot.snapshot_id,
                node_type=NodeType.SECTION,
                title=page["title"],
                source_uri=page.get("source_uri") or confluence_url,
                body_ptr=f"{confluence_url}/spaces/{space_key}/pages/{page['id']}",
                body_text=page["text"],
                content_hash=stable_hash(page["id"], page.get("version", ""), page["text"][:500]),
                snapshot_ref=str(page.get("version", "")),
                source_confidence=1.0,
                serving_confidence=1.0,
            )
            nodes.append(page_node)
            edges.append(
                KnowledgeEdge(
                    tenant_id=snapshot.tenant_id,
                    from_node_id=page_node.node_id,
                    to_node_id=root_node.node_id,
                    edge_type=EdgeType.BELONGS_TO,
                    evidence_spans=[{"path": page["source_uri"], "page_id": page["id"]}],
                )
            )

        self.repository.upsert_nodes(nodes)
        self.repository.upsert_edges(edges)
        self.repository.mark_snapshot_completed(snapshot.snapshot_id, root_node.node_id)

        return SnapshotResponse(
            tenant_id=snapshot.tenant_id,
            snapshot_id=snapshot.snapshot_id,
            root_node_id=root_node.node_id,
            status=SnapshotStatus.COMPLETED,
        )

    def _iter_pages(
        self,
        confluence_url: str,
        space_key: str,
        page_limit: int,
        username: str,
        api_token: str,
    ) -> list[dict[str, str]]:
        """Fetch all pages from a Confluence space via the REST API.

        Returns a list of dicts with keys: id, title, version, source_uri, text.
        """
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "requests is not installed. Install it with: pip install requests"
            ) from exc

        try:
            import html2text  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "html2text is not installed. Install it with: pip install html2text"
            ) from exc

        auth = (username, api_token) if username and api_token else None

        results: list[dict[str, str]] = []
        url = (
            f"{confluence_url.rstrip('/')}/rest/api/content/search"
            f"?cql=space={space_key}&limit={page_limit}&expand=body.storage"
        )

        while url:
            resp = requests.get(url, auth=auth, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", []):
                title = item.get("title", "(untitled)")
                page_id = item.get("id", "")
                version = item.get("version", {})
                version_str = str(version.get("number", "")) if isinstance(version, dict) else ""

                body = item.get("body", {})
                storage = body.get("storage", {}) if isinstance(body, dict) else {}
                raw_html = storage.get("value", "") if isinstance(storage, dict) else ""

                text = self._html_to_text(raw_html)

                links = item.get("_links", {}) or {}
                webui = links.get("webui", "")
                source_uri = (
                    f"{confluence_url.rstrip('/')}{webui}"
                    if webui
                    else f"{confluence_url.rstrip('/')}/spaces/{space_key}/pages/{page_id}"
                )

                results.append(
                    {
                        "id": page_id,
                        "title": title,
                        "version": version_str,
                        "source_uri": source_uri,
                        "text": text,
                    }
                )

            links = data.get("_links", {}) or {}
            next_url = links.get("next")
            if next_url and isinstance(next_url, str):
                base = confluence_url.rstrip("/")
                url = base + next_url if next_url.startswith("/") else next_url
            else:
                url = ""

        return results

    def _html_to_text(self, raw_html: str) -> str:
        """Convert Confluence Storage Format HTML to plain text using html2text."""
        import html2text

        converter = html2text.HTML2Text()
        converter.body_width = 0
        converter.ignore_links = False
        converter.ignore_images = False
        converter.ignore_emphasis = False
        converter.protect_links = True
        converter.unicode_snob = True
        return converter.handle(raw_html).strip()
