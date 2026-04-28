from __future__ import annotations

import logging

from lattice_jit.contracts import CompiledContextManifest, KnowledgeNode, ProvenanceRef

logger = logging.getLogger(__name__)


def build_provenance(
    manifest: CompiledContextManifest,
    evidence_nodes: list[KnowledgeNode],
) -> list[ProvenanceRef]:
    node_by_id = {node.node_id: node for node in evidence_nodes}
    result: list[ProvenanceRef] = []
    for item in manifest.items:
        node = node_by_id.get(item.node_id)
        if node is None:
            logger.warning(
                "Provenance gap: node %s referenced in manifest %s but not found in evidence_nodes. "
                "Provenance will be incomplete for this item.",
                item.node_id,
                manifest.manifest_id,
            )
            continue
        result.append(
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
        )
    return result
