from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from lattice_jit.contracts import (
    CompiledContextItem,
    CompiledContextManifest,
    CompiledContextRole,
    CompiledContextStatus,
    KnowledgeNode,
    PolicyBundle,
)
from lattice_jit.core import Settings, stable_hash, utcnow
from lattice_jit.storage import CacheStore, StorageRepository


@dataclass(slots=True)
class ContextCompiler:
    repository: StorageRepository
    cache_store: CacheStore
    settings: Settings

    def compile(
        self,
        *,
        tenant_id: UUID,
        query: str,
        selected_nodes: list[KnowledgeNode],
        policy_bundle: PolicyBundle,
    ) -> CompiledContextManifest:
        query_hash = stable_hash(tenant_id, query.lower().strip(), *(node.node_id for node in selected_nodes))
        cache_key = f"manifest:{query_hash}"
        cached = self.cache_store.get_json(cache_key)
        if cached is not None:
            manifest_id = cast(str | None, cached.get("manifest_id"))
            manifest = self.repository.get_manifest(UUID(manifest_id)) if manifest_id else None
            if manifest is not None:
                return manifest
        persisted = self.repository.find_manifest_by_query_hash(tenant_id, query_hash)
        if persisted is not None:
            self.cache_store.set_json(
                cache_key,
                {"manifest_id": str(persisted.manifest_id)},
                self.settings.cache_ttl_seconds,
            )
            return persisted

        # Section expansion: include sibling pages from same SECTION parent
        expanded_nodes = list(selected_nodes)
        seen_ids = {n.node_id for n in expanded_nodes}
        for node in selected_nodes:
            section_meta = node.metadata.get("section", "") if node.metadata else ""
            if not section_meta:
                continue
            try:
                edges = self.repository.list_edges_for_nodes([node.node_id])
                parent_ids = [e.to_node_id for e in edges if e.edge_type.value == "belongs_to"]
                if parent_ids:
                    # Find siblings — all nodes that BELONG_TO the same parent
                    sibling_edges = self.repository.list_edges_for_nodes(parent_ids)
                    sibling_ids = {
                        e.from_node_id for e in sibling_edges
                        if e.edge_type.value == "belongs_to" and e.to_node_id in parent_ids
                    }
                    siblings = self.repository.get_nodes_by_ids(sibling_ids - seen_ids)
                    # Only include siblings with same section metadata
                    for sib in siblings:
                        sib_section = sib.metadata.get("section", "") if sib.metadata else ""
                        if sib_section == section_meta:
                            expanded_nodes.append(sib)
                            seen_ids.add(sib.node_id)
            except Exception:
                pass

        items: list[CompiledContextItem] = []
        actual_tokens = 0
        for ordinal, node in enumerate(expanded_nodes):
            snippet_source = (node.body_text or node.title).strip()
            snippet = snippet_source[: self.settings.context_item_char_budget]
            token_count = max(1, len(snippet) // 4)
            remaining_tokens = policy_bundle.max_tokens - actual_tokens
            if remaining_tokens <= 0:
                break
            if token_count > remaining_tokens:
                snippet = snippet[: max(4, remaining_tokens * 4)]
                token_count = max(1, len(snippet) // 4)
            score = node.serving_confidence
            items.append(
                CompiledContextItem(
                    tenant_id=tenant_id,
                    manifest_id=UUID(int=0),
                    ordinal=ordinal,
                    node_id=node.node_id,
                    role=CompiledContextRole.EVIDENCE,
                    token_count=token_count,
                    score=score,
                    snippet=snippet,
                )
            )
            actual_tokens += token_count

        context_hash = stable_hash(query_hash, *(item.node_id for item in items), policy_bundle.policy_bundle_id)
        manifest = CompiledContextManifest(
            tenant_id=tenant_id,
            query_hash=query_hash,
            policy_bundle_id=policy_bundle.policy_bundle_id,
            context_hash=context_hash,
            budget_tokens=policy_bundle.max_tokens,
            actual_tokens=actual_tokens,
            status=CompiledContextStatus.ACTIVE,
            created_at=utcnow(),
            items=[],
        )
        manifest.items = [
            item.model_copy(update={"manifest_id": manifest.manifest_id})
            for item in items
        ]
        self.repository.store_manifest(manifest)
        self.cache_store.set_json(
            cache_key,
            {"manifest_id": str(manifest.manifest_id)},
            self.settings.cache_ttl_seconds,
        )
        return manifest
