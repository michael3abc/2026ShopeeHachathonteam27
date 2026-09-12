"""Shared embedding boundary for Policy and Operational Memory RAG.

The Protocol keeps retrieval testable and avoids making a live OpenAI call from
contract or database tests.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from math import isfinite
from pathlib import Path
from typing import Protocol, runtime_checkable

POLICY_EMBEDDING_MODEL = "text-embedding-3-large"
POLICY_EMBEDDING_DIMENSIONS = 1536


class InvalidEmbeddingError(ValueError):
    """Raised when an embedding adapter returns an unusable vector."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Synchronous text embedding boundary used by Policy RAG."""

    model_name: str
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


def validate_embedding(vector: Sequence[float], *, dimensions: int) -> list[float]:
    """Return a finite vector of the exact contract dimension."""

    if len(vector) != dimensions:
        raise InvalidEmbeddingError(
            f"embedding must have {dimensions} dimensions, got {len(vector)}"
        )
    normalized = [float(value) for value in vector]
    if not all(isfinite(value) for value in normalized):
        raise InvalidEmbeddingError("embedding values must be finite")
    if not any(normalized):
        raise InvalidEmbeddingError("embedding must be nonzero")
    return normalized


class OpenAIEmbeddingProvider:
    """OpenAI-backed runtime adapter for 1536-dimension policy embeddings."""

    dimensions = POLICY_EMBEDDING_DIMENSIONS

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str = POLICY_EMBEDDING_MODEL,
        timeout_seconds: float = 25.0,
        client: object | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must be non-empty")
        if base_url is not None and not base_url.strip():
            raise ValueError("base_url must be non-empty when supplied")
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self.model_name = model_name
        if client is None:
            from openai import OpenAI

            kwargs: dict[str, object] = {
                "timeout": timeout_seconds, "max_retries": 0
            }
            resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
            if resolved_key is not None:
                kwargs["api_key"] = resolved_key
            if base_url is not None:
                kwargs["base_url"] = base_url
            client = OpenAI(**kwargs)
        self._client = client

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(
            model=self.model_name,
            input=text,
            dimensions=self.dimensions,
        )
        return validate_embedding(
            response.data[0].embedding,
            dimensions=self.dimensions,
        )


def embedding_provider_from_env() -> OpenAIEmbeddingProvider:
    """Build the deployment adapter without embedding secret values in code."""

    api_key = os.environ.get("RETURN_AGENT_EMBEDDING_API_KEY")
    key_file = os.environ.get("RETURN_AGENT_EMBEDDING_API_KEY_FILE")
    if not api_key and key_file:
        api_key = Path(key_file).read_text(encoding="utf-8").strip()
    if not api_key or not api_key.strip():
        raise ValueError(
            "RETURN_AGENT_EMBEDDING_API_KEY or "
            "RETURN_AGENT_EMBEDDING_API_KEY_FILE is required"
        )
    base_url = os.environ.get("RETURN_AGENT_EMBEDDING_BASE_URL")
    if not base_url or not base_url.strip():
        raise ValueError("RETURN_AGENT_EMBEDDING_BASE_URL is required")
    return OpenAIEmbeddingProvider(
        api_key=api_key,
        base_url=base_url,
        model_name=os.environ.get(
            "RETURN_AGENT_EMBEDDING_MODEL", POLICY_EMBEDDING_MODEL
        ),
        timeout_seconds=float(
            os.environ.get("RETURN_AGENT_EMBEDDING_TIMEOUT_SECONDS", "25")
        ),
    )
