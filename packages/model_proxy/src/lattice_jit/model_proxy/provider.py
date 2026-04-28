from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lattice_jit.contracts import CompiledContextManifest, KnowledgeNode, PolicyBundle


class ModelProvider(Protocol):
    def generate(
        self,
        query: str,
        manifest: CompiledContextManifest,
        nodes: list[KnowledgeNode],
        policy_bundle: PolicyBundle,
    ) -> str:
        ...


@dataclass(slots=True, frozen=True)
class ModelProviderConfig:
    provider: str = "stub"
    litellm_model: str = "gpt-4o-mini"
    litellm_temperature: float = 0.0
    litellm_max_output_tokens: int | None = None
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    prompt_caching_enabled: bool = False


@dataclass(slots=True)
class StubModelProvider:
    def generate(
        self,
        query: str,
        manifest: CompiledContextManifest,
        nodes: list[KnowledgeNode],
        policy_bundle: PolicyBundle,
    ) -> str:
        evidence_lines = []
        for item, node in zip(manifest.items[:3], nodes[:3], strict=False):
            evidence_lines.append(
                f"- {node.title}: {item.snippet.strip().replace(chr(10), ' ')[:180]}"
            )
        if not evidence_lines:
            evidence_lines.append("- No evidence matched the query in the active snapshot.")
        policy_line = f"policy_class={policy_bundle.query_class}, max_tokens={policy_bundle.max_tokens}"
        return "\n".join(
            [
                "Phase A provisional answer",
                f"Query: {query}",
                policy_line,
                "Evidence:",
                *evidence_lines,
                "Recommendation: inspect the cited files before taking irreversible action.",
            ]
        )


@dataclass(slots=True)
class LiteLLMModelProvider:
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_output_tokens: int | None = None
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    prompt_caching_enabled: bool = False

    def generate(
        self,
        query: str,
        manifest: CompiledContextManifest,
        nodes: list[KnowledgeNode],
        policy_bundle: PolicyBundle,
    ) -> str:
        try:
            from litellm import completion
        except ImportError as exc:
            raise RuntimeError("litellm is not installed; use the stub provider or install litellm.") from exc

        context_parts: list[str] = []
        for item, node in zip(manifest.items, nodes, strict=False):
            context_parts.append(
                f"[{item.role.value}] {node.title} (score={item.score:.2f}, "
                f"source={node.source_uri or 'unknown'})\n{item.snippet}"
            )
        context = "\n\n".join(context_parts) if context_parts else "- No evidence matched the query."

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are a financial knowledge assistant analyzing compiled context with provenance awareness. "
                    f"Policy class: {policy_bundle.query_class}. "
                    "Cite source URIs when referencing facts. "
                    "Do not invent facts outside the provided context. "
                    "If the context is insufficient, state so clearly."
                ),
            },
            {"role": "user", "content": f"Query:\n{query}\n\nContext:\n{context}"},
        ]

        completion_kwargs: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.max_output_tokens is not None:
            completion_kwargs["max_tokens"] = self.max_output_tokens
        if self.prompt_caching_enabled:
            completion_kwargs["cache"] = {"type": "ephemeral"}

        if self.model.startswith("deepseek/"):
            import os

            api_key = self.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")
            if api_key:
                completion_kwargs["api_key"] = api_key
            completion_kwargs["api_base"] = self.deepseek_base_url

        response = completion(**completion_kwargs)
        return response.choices[0].message.content or ""


def build_model_provider(config: ModelProviderConfig) -> ModelProvider:
    provider_name = config.provider.strip().lower()
    if provider_name == "stub":
        return StubModelProvider()
    if provider_name == "litellm":
        return LiteLLMModelProvider(
            model=config.litellm_model,
            temperature=config.litellm_temperature,
            max_output_tokens=config.litellm_max_output_tokens,
            deepseek_api_key=config.deepseek_api_key,
            deepseek_base_url=config.deepseek_base_url,
            prompt_caching_enabled=config.prompt_caching_enabled,
        )
    raise ValueError(f"Unknown model provider: {config.provider}")
