import os
import hashlib
import math
from abc import ABC, abstractmethod
from typing import List
from app.config import settings

class BaseEmbeddingService(ABC):
    """
    Abstract Base Class for Embedding Services.
    Allows easy swapping between OpenAI, Gemini, Voyage AI, or Local Fallback providers.
    """

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        pass


class OpenAIEmbeddingService(BaseEmbeddingService):
    """OpenAI Embedding Provider."""

    def __init__(self, api_key: str = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY
        self.model = model
        try:
            from langchain_openai import OpenAIEmbeddings
            self.client = OpenAIEmbeddings(openai_api_key=self.api_key, model=self.model)
        except Exception:
            self.client = None

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if self.client and self.api_key:
            try:
                return self.client.embed_documents(texts)
            except Exception as e:
                print(f"OpenAI embedding error, falling back to local: {e}")
        return FallbackEmbeddingService().embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        if self.client and self.api_key:
            try:
                return self.client.embed_query(text)
            except Exception as e:
                print(f"OpenAI query embedding error, falling back to local: {e}")
        return FallbackEmbeddingService().embed_query(text)


class GeminiEmbeddingService(BaseEmbeddingService):
    """Google Gemini Embedding Provider."""

    def __init__(self, api_key: str = None, model: str = "models/text-embedding-004"):
        self.api_key = api_key or settings.EMBEDDING_API_KEY
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            return FallbackEmbeddingService().embed_documents(texts)
        try:
            import requests
            url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents?key={self.api_key}"
            requests_body = {
                "requests": [{"model": self.model, "content": {"parts": [{"text": t}]}} for t in texts]
            }
            res = requests.post(url, json=requests_body, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return [emb["values"] for emb in data.get("embeddings", [])]
        except Exception as e:
            print(f"Gemini embedding error: {e}")
        return FallbackEmbeddingService().embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        results = self.embed_documents([text])
        return results[0] if results else FallbackEmbeddingService().embed_query(text)


class VoyageEmbeddingService(BaseEmbeddingService):
    """Voyage AI Embedding Provider."""

    def __init__(self, api_key: str = None, model: str = "voyage-2"):
        self.api_key = api_key or settings.EMBEDDING_API_KEY or os.getenv("VOYAGE_API_KEY", "")
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            return FallbackEmbeddingService().embed_documents(texts)
        try:
            import requests
            res = requests.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": texts, "model": self.model},
                timeout=10
            )
            if res.status_code == 200:
                return [d["embedding"] for d in res.json().get("data", [])]
        except Exception as e:
            print(f"Voyage AI embedding error: {e}")
        return FallbackEmbeddingService().embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        results = self.embed_documents([text])
        return results[0] if results else FallbackEmbeddingService().embed_query(text)


class FallbackEmbeddingService(BaseEmbeddingService):
    """
    Local, zero-dependency deterministic vector generator.
    Ensures RAG works locally even if no external embedding API keys are set.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _text_to_vector(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        words = text.lower().split()
        if not words:
            return vec
            
        for w in words:
            h = int(hashlib.md5(w.encode('utf-8')).hexdigest(), 16)
            idx = h % self.dim
            val = ((h >> 8) % 1000) / 1000.0 - 0.5
            vec[idx] += val
            
        # Normalize L2
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._text_to_vector(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._text_to_vector(text)


def get_embedding_service(provider: str = None) -> BaseEmbeddingService:
    """
    Factory method to retrieve configured embedding service instance.
    Defaults to local FallbackEmbeddingService so RAG works with zero API keys.
    """
    selected_provider = (provider or settings.EMBEDDING_PROVIDER or "local").lower()

    if selected_provider == "openai":
        svc = OpenAIEmbeddingService()
        # Only use if API key is actually available
        if svc.api_key:
            return svc
        print("[Embeddings] OpenAI provider selected but no API key found. Using local fallback.")
        return FallbackEmbeddingService()
    elif selected_provider == "gemini":
        svc = GeminiEmbeddingService()
        if svc.api_key:
            return svc
        print("[Embeddings] Gemini provider selected but no API key found. Using local fallback.")
        return FallbackEmbeddingService()
    elif selected_provider == "voyage":
        svc = VoyageEmbeddingService()
        if svc.api_key:
            return svc
        print("[Embeddings] Voyage provider selected but no API key found. Using local fallback.")
        return FallbackEmbeddingService()
    else:
        # 'local' or any unknown provider → guaranteed zero-dependency fallback
        return FallbackEmbeddingService()
