from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol
from urllib import request
from urllib.error import URLError
from uuid import UUID

from lattice_jit.contracts import PhaseBMode, PolicyBundle
from lattice_jit.core import stable_hash

logger = logging.getLogger(__name__)


class PolicyEvaluatorProtocol(Protocol):
    def evaluate(self, tenant_id: UUID, query: str, phase_b_mode: PhaseBMode) -> PolicyBundle:
        ...

    def health_check(self) -> dict[str, str]:
        ...


@dataclass(slots=True, frozen=True)
class PolicyEvaluatorConfig:
    mode: str = "inline"
    opa_url: str = "http://localhost:8181"
    opa_policy_path: str = "/v1/data/lattice_jit/policy"
    opa_timeout_seconds: float = 2.0
    opa_fail_closed: bool = False


class PolicyEvaluator:
    def evaluate(self, tenant_id: UUID, query: str, phase_b_mode: PhaseBMode) -> PolicyBundle:
        lowered = query.lower()
        query_class = self._classify(lowered)
        phase_b_required = phase_b_mode.value == "force" or (
            phase_b_mode.value == "auto" and query_class in {"compliance", "security", "governance"}
        )
        human_gate_required = query_class in {"compliance", "security"}
        redaction_rules = ["mask_identifiers"] if human_gate_required else []
        return PolicyBundle(
            tenant_id=tenant_id,
            query_class=query_class,
            tool_allowlist=["git_local"],
            redaction_rules=redaction_rules,
            max_tokens=12_000 if human_gate_required else 16_000,
            phase_b_required=phase_b_required,
            human_gate_required=human_gate_required,
            opa_decision_hash=stable_hash(tenant_id, query_class, phase_b_mode),
        )

    def _classify(self, lowered_query: str) -> str:
        if any(term in lowered_query for term in ("hipaa", "pci", "gdpr", "ccpa", "policy", "compliance")):
            return "compliance"
        if any(term in lowered_query for term in ("security", "incident", "breach")):
            return "security"
        if any(term in lowered_query for term in ("cost", "budget", "price")):
            return "cost"
        return "general"

    def health_check(self) -> dict[str, str]:
        return {"status": "healthy", "mode": "inline"}


@dataclass(slots=True)
class OpaHttpPolicyEvaluator:
    opa_url: str = "http://localhost:8181"
    opa_policy_path: str = "/v1/data/lattice_jit/policy"
    timeout_seconds: float = 2.0
    fail_closed: bool = False
    inline_fallback: PolicyEvaluator = PolicyEvaluator()

    def evaluate(self, tenant_id: UUID, query: str, phase_b_mode: PhaseBMode) -> PolicyBundle:
        fallback = self.inline_fallback.evaluate(tenant_id, query, phase_b_mode)
        is_regulated = fallback.query_class in {"compliance", "security"}
        payload: dict[str, object] = {
            "input": {
                "tenant_id": str(tenant_id),
                "query": query,
                "query_class": fallback.query_class,
                "phase_b_mode": phase_b_mode.value,
            }
        }

        try:
            response = self._post_json(payload)
            result = response.get("result") if isinstance(response, dict) else None
            result_obj = result if isinstance(result, dict) else {}
        except (RuntimeError, URLError, TimeoutError, ValueError, TypeError):
            logger.warning(
                "OPA HTTP evaluator unreachable at %s — falling back to inline policy. "
                "Policy decisions may be less precise.",
                self.opa_url,
            )
            if self.fail_closed and is_regulated:
                raise RuntimeError(
                    f"OPA sidecar unreachable at {self.opa_url} and fail_closed is enabled "
                    f"for regulated query class '{fallback.query_class}'. Query rejected."
                ) from None
            result_obj = {}

        return PolicyBundle(
            tenant_id=tenant_id,
            query_class=_as_str(result_obj.get("query_class"), fallback.query_class),
            tool_allowlist=_as_str_list(result_obj.get("tool_allowlist"), fallback.tool_allowlist),
            redaction_rules=_as_str_list(result_obj.get("redaction_rules"), fallback.redaction_rules),
            max_tokens=_as_int(result_obj.get("max_tokens"), fallback.max_tokens),
            phase_b_required=_as_bool(result_obj.get("phase_b_required"), fallback.phase_b_required),
            human_gate_required=_as_bool(result_obj.get("human_gate_required"), fallback.human_gate_required),
            opa_decision_hash=stable_hash(
                tenant_id,
                phase_b_mode.value,
                query,
                response_signature(result_obj, fallback),
            ),
        )

    def health_check(self) -> dict[str, str]:
        try:
            self._post_json({"input": {"query_class": "general", "phase_b_mode": "auto"}})
            return {"status": "healthy", "mode": "opa_http"}
        except (RuntimeError, URLError, TimeoutError, ValueError, TypeError):
            return {"status": "degraded", "mode": "opa_http"}

    def _post_json(self, payload: dict[str, object]) -> dict[str, object]:
        raw = json.dumps(payload).encode("utf-8")
        url = f"{self.opa_url.rstrip('/')}/{self.opa_policy_path.lstrip('/')}"
        req = request.Request(
            url=url,
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise RuntimeError("OPA response must be a JSON object")
        return parsed


def build_policy_evaluator(config: PolicyEvaluatorConfig) -> PolicyEvaluatorProtocol:
    mode = config.mode.strip().lower()
    if mode == "inline":
        return PolicyEvaluator()
    if mode == "opa_http":
        return OpaHttpPolicyEvaluator(
            opa_url=config.opa_url,
            opa_policy_path=config.opa_policy_path,
            timeout_seconds=config.opa_timeout_seconds,
            fail_closed=config.opa_fail_closed,
        )
    raise ValueError(f"Unknown policy evaluator mode: {config.mode}")


def _as_bool(value: object, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback


def _as_int(value: object, fallback: int) -> int:
    return value if isinstance(value, int) else fallback


def _as_str(value: object, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback


def _as_str_list(value: object, fallback: list[str]) -> list[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return fallback


def response_signature(result_obj: dict[str, object], fallback: PolicyBundle) -> str:
    if not result_obj:
        return "fallback"
    return stable_hash(
        _as_str(result_obj.get("query_class"), fallback.query_class),
        _as_int(result_obj.get("max_tokens"), fallback.max_tokens),
        _as_bool(result_obj.get("phase_b_required"), fallback.phase_b_required),
        _as_bool(result_obj.get("human_gate_required"), fallback.human_gate_required),
        *_as_str_list(result_obj.get("tool_allowlist"), fallback.tool_allowlist),
        *_as_str_list(result_obj.get("redaction_rules"), fallback.redaction_rules),
    )
