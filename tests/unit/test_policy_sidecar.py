from __future__ import annotations

from uuid import UUID

import pytest
from lattice_jit.contracts import PhaseBMode
from lattice_jit.core.wiring import _policy_evaluator_config
from lattice_jit.policy import (
    OpaHttpPolicyEvaluator,
    PolicyEvaluator,
    PolicyEvaluatorConfig,
    build_policy_evaluator,
)


def test_policy_factory_defaults_to_inline() -> None:
    evaluator = build_policy_evaluator(PolicyEvaluatorConfig())

    assert isinstance(evaluator, PolicyEvaluator)


def test_policy_factory_selects_opa_http_mode() -> None:
    evaluator = build_policy_evaluator(PolicyEvaluatorConfig(mode="opa_http"))

    assert isinstance(evaluator, OpaHttpPolicyEvaluator)


def test_policy_factory_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unknown policy evaluator mode"):
        build_policy_evaluator(PolicyEvaluatorConfig(mode="unknown"))


def test_policy_wiring_config_uses_sidecar_settings_values() -> None:
    config = _policy_evaluator_config(
        mode="opa_http",
        opa_url="http://opa:8181",
        opa_policy_path="/v1/data/lattice_jit/policy",
        opa_timeout_seconds=1.5,
    )

    assert config.mode == "opa_http"
    assert config.opa_url == "http://opa:8181"
    assert config.opa_policy_path == "/v1/data/lattice_jit/policy"
    assert config.opa_timeout_seconds == 1.5


def test_opa_http_evaluator_maps_result_to_policy_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    evaluator = OpaHttpPolicyEvaluator()

    def fake_post_json(_self: OpaHttpPolicyEvaluator, payload: dict[str, object]) -> dict[str, object]:
        assert "input" in payload
        return {
            "result": {
                "query_class": "security",
                "tool_allowlist": ["git_local", "audit"],
                "redaction_rules": ["mask_identifiers"],
                "max_tokens": 11000,
                "phase_b_required": True,
                "human_gate_required": True,
            }
        }

    monkeypatch.setattr(OpaHttpPolicyEvaluator, "_post_json", fake_post_json)

    bundle = evaluator.evaluate(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        query="investigate security breach timeline",
        phase_b_mode=PhaseBMode.AUTO,
    )

    assert bundle.query_class == "security"
    assert bundle.tool_allowlist == ["git_local", "audit"]
    assert bundle.redaction_rules == ["mask_identifiers"]
    assert bundle.max_tokens == 11000
    assert bundle.phase_b_required is True
    assert bundle.human_gate_required is True


def test_fail_closed_raises_for_compliance_query_when_opa_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluator = OpaHttpPolicyEvaluator(fail_closed=True)

    def fake_post_json(_self: OpaHttpPolicyEvaluator, payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("OPA is down")

    monkeypatch.setattr(OpaHttpPolicyEvaluator, "_post_json", fake_post_json)

    with pytest.raises(RuntimeError, match="OPA sidecar unreachable"):
        evaluator.evaluate(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            query="What does our PCI policy require?",
            phase_b_mode=PhaseBMode.AUTO,
        )


def test_fail_closed_falls_back_for_general_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluator = OpaHttpPolicyEvaluator(fail_closed=True)

    def fake_post_json(_self: OpaHttpPolicyEvaluator, payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("OPA is down")

    monkeypatch.setattr(OpaHttpPolicyEvaluator, "_post_json", fake_post_json)

    bundle = evaluator.evaluate(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        query="How many files are in the repository?",
        phase_b_mode=PhaseBMode.AUTO,
    )
    assert bundle.query_class == "general"
    assert bundle.phase_b_required is False


def test_fail_closed_disabled_falls_back_for_compliance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluator = OpaHttpPolicyEvaluator(fail_closed=False)

    def fake_post_json(_self: OpaHttpPolicyEvaluator, payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("OPA is down")

    monkeypatch.setattr(OpaHttpPolicyEvaluator, "_post_json", fake_post_json)

    bundle = evaluator.evaluate(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        query="What does our PCI policy require?",
        phase_b_mode=PhaseBMode.AUTO,
    )
    assert bundle.query_class == "compliance"
    assert bundle.human_gate_required is True
    assert bundle.phase_b_required is True


def test_opa_health_check_returns_degraded_when_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluator = OpaHttpPolicyEvaluator()

    def fake_post_json(_self: OpaHttpPolicyEvaluator, payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("OPA is down")

    monkeypatch.setattr(OpaHttpPolicyEvaluator, "_post_json", fake_post_json)

    result = evaluator.health_check()
    assert result["status"] == "degraded"
    assert result["mode"] == "opa_http"


def test_inline_evaluator_health_check_is_always_healthy() -> None:
    evaluator = PolicyEvaluator()
    result = evaluator.health_check()
    assert result["status"] == "healthy"
    assert result["mode"] == "inline"


def test_wiring_config_includes_fail_closed() -> None:
    config = _policy_evaluator_config(
        mode="opa_http",
        opa_url="http://opa:8181",
        opa_policy_path="/v1/data/lattice_jit/policy",
        opa_timeout_seconds=1.5,
        opa_fail_closed=True,
    )
    assert config.opa_fail_closed is True


def test_wiring_config_fail_closed_defaults_to_false() -> None:
    config = _policy_evaluator_config(
        mode="opa_http",
        opa_url="http://opa:8181",
        opa_policy_path="/v1/data/lattice_jit/policy",
        opa_timeout_seconds=1.5,
    )
    assert config.opa_fail_closed is False


def test_health_check_healthy_when_opa_reachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluator = OpaHttpPolicyEvaluator()

    def fake_post_json(_self: OpaHttpPolicyEvaluator, payload: dict[str, object]) -> dict[str, object]:
        return {"result": {"query_class": "general", "max_tokens": 16000}}

    monkeypatch.setattr(OpaHttpPolicyEvaluator, "_post_json", fake_post_json)

    result = evaluator.health_check()
    assert result["status"] == "healthy"
    assert result["mode"] == "opa_http"