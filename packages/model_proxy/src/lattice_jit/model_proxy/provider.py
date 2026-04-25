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

        context = "\n\n".join(
            f"{node.title}\n{item.snippet}"
            for item, node in zip(manifest.items, nodes, strict=False)
        )
        response = completion(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Answer with clear provenance awareness. "
                        f"Policy class: {policy_bundle.query_class}. "
                        "Do not invent facts outside the context."
                    ),
                },
                {"role": "user", "content": f"Query:\n{query}\n\nContext:\n{context}"},
            ],
        )
        return response.choices[0].message.content or ""
