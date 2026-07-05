"""
Simple embedding providers for long-term memory.
Used by app/memory/long_memory.py for semantic fact retrieval.
"""
import os
from typing import List


class StubEmbeddings:
    """Deterministic stub embeddings for testing."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return deterministic vectors based on text length."""
        return [[float(len(t)) / 100.0] * 384 for t in texts]


class LocalEmbeddings:
    """Local sentence-transformers embeddings (if available)."""

    def __init__(self):
        self.model = None
        try:
            from sentence_transformers import SentenceTransformer

            model_name = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            self.model = SentenceTransformer(model_name)
        except Exception:
            # Fallback to stub if sentence-transformers not available
            pass

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Encode texts to vectors."""
        if self.model is None:
            # Fallback to stub
            return StubEmbeddings().embed(texts)
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return [emb.tolist() for emb in embeddings]
        except Exception:
            return StubEmbeddings().embed(texts)


class OpenAIEmbeddings:
    """OpenAI embeddings via API."""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Call OpenAI embeddings API."""
        if not self.api_key:
            # Fallback to stub if no API key
            return StubEmbeddings().embed(texts)

        try:
            import openai

            client = openai.OpenAI(api_key=self.api_key)
            response = client.embeddings.create(input=texts, model=self.model)
            return [item.embedding for item in response.data]
        except Exception:
            # Fallback on error
            return StubEmbeddings().embed(texts)
