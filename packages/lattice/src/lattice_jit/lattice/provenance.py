from __future__ import annotations

from lattice_jit.contracts import CompiledContextManifest, KnowledgeNode, ProvenanceRef


def build_provenance(
    manifest: CompiledContextManifest,
    evidence_nodes: list[KnowledgeNode],
) -> list[ProvenanceRef]:
    return [
        ProvenanceRef(
            node_id=node.node_id,
            title=node.title,
            source_uri=node.source_uri,
            snapshot_id=node.snapshot_id,
            snapshot_ref=node.snapshot_ref,
            content_hash=node.content_hash,
            score=item.score,
            snippet=item.snippet,
        )
        for item, node in zip(manifest.items, evidence_nodes, strict=False)
    ]
