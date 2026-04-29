from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


def _lazy_load_model2vec() -> Any:
    try:
        from model2vec import StaticModel
        return StaticModel
    except ImportError:
        return None


@dataclass(slots=True)
class EmbeddingService:
    model_name: str = "minishlab/potion-base-8M"
    enabled: bool = False

    _model: Any | None = field(default=None, init=False)

    def _ensure_model(self) -> Any:
        if not self.enabled:
            return None
        if self._model is not None:
            return self._model
        StaticModel = _lazy_load_model2vec()
        if StaticModel is None:
            logger.warning(
                "model2vec is not installed. Install with: pip install model2vec. "
                "Falling back to lexical similarity."
            )
            self.enabled = False
            return None
        try:
            self._model = StaticModel.from_pretrained(self.model_name)
            logger.info("Loaded embedding model: %s", self.model_name)
        except Exception:
            logger.warning(
                "Failed to load embedding model '%s'. Falling back to lexical similarity.",
                self.model_name,
                exc_info=True,
            )
            self.enabled = False
            return None
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        if model is None:
            return [[0.0]] * len(texts)
        result = model.encode(texts)
        return [vec.tolist() if hasattr(vec, "tolist") else list(vec) for vec in result]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
