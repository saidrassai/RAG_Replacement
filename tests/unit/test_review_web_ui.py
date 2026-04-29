from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from lattice_jit.apps.api.main import create_app
from lattice_jit.apps.api.main import get_container as api_get_container
from lattice_jit.contracts import ReviewItem, ReviewRiskLevel, ReviewState


def _build_client(container):
    api_get_container.cache_clear()
    app = create_app(settings=container.settings)
    app.dependency_overrides[api_get_container] = lambda: container
    return TestClient(app)


def test_ui_review_queue_renders_with_items(container) -> None:
    tenant_id = uuid4()
    container.repository.upsert_review_item(
        ReviewItem(
            tenant_id=tenant_id,
            fact_fingerprint="fp-1",
            fact_type="compliance",
            risk_level=ReviewRiskLevel.HIGH,
            sample_rate=0.1,
            evidence_count=3,
        )
    )
    client = _build_client(container)
    response = client.get(f"/ui/review-queue?tenant_id={tenant_id}")
    assert response.status_code == 200
    assert "compliance" in response.text
    assert "Review Queue" in response.text


def test_ui_review_queue_renders_empty_state(container) -> None:
    tenant_id = uuid4()
    client = _build_client(container)
    response = client.get(f"/ui/review-queue?tenant_id={tenant_id}")
    assert response.status_code == 200
    assert "No review items found" in response.text


def test_ui_review_detail_renders(container) -> None:
    tenant_id = uuid4()
    review_item_id = uuid4()
    container.repository.upsert_review_item(
        ReviewItem(
            review_item_id=review_item_id,
            tenant_id=tenant_id,
            fact_fingerprint="fp-detail",
            fact_type="security",
            risk_level=ReviewRiskLevel.MEDIUM,
            review_state=ReviewState.PENDING,
            sample_rate=0.05,
            evidence_count=2,
        )
    )
    client = _build_client(container)
    response = client.get(
        f"/ui/review-queue/{review_item_id}", params={"tenant_id": str(tenant_id)}
    )
    assert response.status_code == 200
    assert "fp-detail" in response.text
    assert "security" in response.text
    assert "Approve" in response.text
    assert "Reject" in response.text


def test_ui_review_detail_shows_already_reviewed_for_approved(container) -> None:
    tenant_id = uuid4()
    review_item_id = uuid4()
    container.repository.upsert_review_item(
        ReviewItem(
            review_item_id=review_item_id,
            tenant_id=tenant_id,
            fact_fingerprint="fp-approved",
            fact_type="general",
            risk_level=ReviewRiskLevel.LOW,
            review_state=ReviewState.APPROVED,
            sample_rate=0.0,
            evidence_count=1,
        )
    )
    client = _build_client(container)
    response = client.get(
        f"/ui/review-queue/{review_item_id}", params={"tenant_id": str(tenant_id)}
    )
    assert response.status_code == 200
    assert "Already reviewed" in response.text


def test_ui_review_detail_404_for_missing_item(container) -> None:
    tenant_id = uuid4()
    client = _build_client(container)
    response = client.get(
        f"/ui/review-queue/{uuid4()}", params={"tenant_id": str(tenant_id)}
    )
    assert response.status_code == 404


def test_ui_approve_review_redirects(container) -> None:
    tenant_id = uuid4()
    review_item_id = uuid4()
    container.repository.upsert_review_item(
        ReviewItem(
            review_item_id=review_item_id,
            tenant_id=tenant_id,
            fact_fingerprint="fp-to-approve",
            fact_type="compliance",
            risk_level=ReviewRiskLevel.HIGH,
            review_state=ReviewState.PENDING,
            sample_rate=0.0,
            evidence_count=1,
        )
    )
    client = _build_client(container)
    response = client.post(
        f"/ui/review-queue/{review_item_id}/approve",
        data={"tenant_id": str(tenant_id)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert f"tenant_id={tenant_id}" in response.headers["location"]


def test_ui_reject_review_redirects(container) -> None:
    tenant_id = uuid4()
    review_item_id = uuid4()
    container.repository.upsert_review_item(
        ReviewItem(
            review_item_id=review_item_id,
            tenant_id=tenant_id,
            fact_fingerprint="fp-to-reject",
            fact_type="compliance",
            risk_level=ReviewRiskLevel.HIGH,
            review_state=ReviewState.PENDING,
            sample_rate=0.0,
            evidence_count=1,
        )
    )
    client = _build_client(container)
    response = client.post(
        f"/ui/review-queue/{review_item_id}/reject",
        data={"tenant_id": str(tenant_id)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert f"tenant_id={tenant_id}" in response.headers["location"]
