from __future__ import annotations

from uuid import uuid4

from lattice_jit.contracts import (
    AnswerEnvelope,
    AnswerPhase,
    AnswerStatus,
    CompiledContextItem,
    CompiledContextManifest,
    CompiledContextRole,
    CompiledContextStatus,
    ConfidenceBand,
    EdgeType,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    ProvenanceRef,
    ReviewItem,
)


def test_repository_roundtrip(container) -> None:
    tenant_id = uuid4()
    node = KnowledgeNode(
        tenant_id=tenant_id,
        node_type=NodeType.SECTION,
        title="auth.py",
        body_text="return user.is_active",
        content_hash="node-hash",
    )
    edge = KnowledgeEdge(
        tenant_id=tenant_id,
        from_node_id=node.node_id,
        to_node_id=node.node_id,
        edge_type=EdgeType.BELONGS_TO,
    )
    container.repository.upsert_nodes([node])
    container.repository.upsert_edges([edge])

    manifest = CompiledContextManifest(
        tenant_id=tenant_id,
        query_hash="query-hash",
        policy_bundle_id=uuid4(),
        context_hash="context-hash",
        budget_tokens=100,
        actual_tokens=20,
        status=CompiledContextStatus.ACTIVE,
        items=[
            CompiledContextItem(
                manifest_id=uuid4(),
                ordinal=0,
                node_id=node.node_id,
                role=CompiledContextRole.EVIDENCE,
                token_count=20,
                score=0.9,
                snippet="return user.is_active",
            )
        ],
    )
    manifest.items = [manifest.items[0].model_copy(update={"manifest_id": manifest.manifest_id})]
    container.repository.store_manifest(manifest)

    answer = AnswerEnvelope(
        answer_id=uuid4(),
        tenant_id=tenant_id,
        phase=AnswerPhase.A,
        status=AnswerStatus.COMPLETE,
        answer_text="Phase A provisional answer",
        confidence_band=ConfidenceBand.MEDIUM,
        provisional=True,
        provenance=[
            ProvenanceRef(
                node_id=node.node_id,
                title=node.title,
                source_uri=node.source_uri,
                snapshot_id=node.snapshot_id,
                snapshot_ref=node.snapshot_ref,
                content_hash=node.content_hash,
                score=0.9,
                snippet="return user.is_active",
            )
        ],
        manifest_id=manifest.manifest_id,
    )
    container.repository.store_answer_event(answer)
    container.repository.upsert_review_item(
        ReviewItem(
            tenant_id=tenant_id,
            fact_fingerprint="fact",
            fact_type="owner",
            canonical_node_id=node.node_id,
            evidence_count=1,
        )
    )

    stored_manifest = container.repository.get_manifest(manifest.manifest_id)
    stored_answer = container.repository.get_latest_answer(answer.answer_id)
    reviews = container.repository.list_review_items(tenant_id)

    assert stored_manifest is not None
    assert stored_manifest.items[0].node_id == node.node_id
    assert stored_answer is not None
    assert stored_answer.answer_text == answer.answer_text
    assert len(reviews) == 1
