import os
import json
import math
import uuid
from typing import List, Dict, Any, Tuple
from app.config import settings
from app.rag.document_loader import DocumentChunk
from app.rag.embeddings import get_embedding_service, BaseEmbeddingService

class VectorStoreRepository:
    """
    Isolated Service/Repository Layer for Vector Database Operations.
    Abstracts vector storage (Qdrant & Local Vector Repository) from tools and agent.
    """

    def __init__(self, embedding_service: BaseEmbeddingService = None, storage_dir: str = ".data/vector_store"):
        self.embedding_service = embedding_service or get_embedding_service()
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.index_file = os.path.join(self.storage_dir, "vector_index.json")
        
        self.qdrant_client = None
        self.collection_name = "jarvis_documents"
        self._init_qdrant()
        self._init_local_store()

    def _init_qdrant(self):
        if settings.QDRANT_URL or os.getenv("QDRANT_URL"):
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import VectorParams, Distance
                
                url = settings.QDRANT_URL or os.getenv("QDRANT_URL")
                api_key = settings.QDRANT_API_KEY or os.getenv("QDRANT_API_KEY")
                self.qdrant_client = QdrantClient(url=url, api_key=api_key)
                
                # Ensure collection exists
                collections = [c.name for c in self.qdrant_client.get_collections().collections]
                if self.collection_name not in collections:
                    sample_vec = self.embedding_service.embed_query("test")
                    self.qdrant_client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(size=len(sample_vec), distance=Distance.COSINE)
                    )
            except Exception as e:
                print(f"Qdrant connection initialized with local fallback. Note: {e}")
                self.qdrant_client = None

    def _init_local_store(self):
        if not os.path.exists(self.index_file):
            self._save_local_index([])

    def _load_local_index(self) -> List[Dict[str, Any]]:
        try:
            if os.path.exists(self.index_file):
                with open(self.index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading local vector index: {e}")
        return []

    def _save_local_index(self, records: List[Dict[str, Any]]):
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving local vector index: {e}")

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 < 1e-9 or norm2 < 1e-9:
            return 0.0
        return dot / (norm1 * norm2)

    def add_documents(self, chunks: List[DocumentChunk]) -> int:
        """
        Embeds and stores document chunks in the vector repository.
        """
        if not chunks:
            return 0
            
        texts = [c.page_content for c in chunks]
        embeddings = self.embedding_service.embed_documents(texts)
        
        records = self._load_local_index()
        count = 0
        
        for chunk, emb in zip(chunks, embeddings):
            doc_id = str(uuid.uuid4())
            record = {
                "id": doc_id,
                "vector": emb,
                "page_content": chunk.page_content,
                "metadata": chunk.metadata
            }
            records.append(record)
            count += 1
            
        self._save_local_index(records)
        
        # If Qdrant is connected, sync records
        if self.qdrant_client:
            try:
                from qdrant_client.models import PointStruct
                points = [
                    PointStruct(
                        id=idx,
                        vector=emb,
                        payload={"page_content": chunk.page_content, **chunk.metadata}
                    )
                    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings))
                ]
                self.qdrant_client.upsert(collection_name=self.collection_name, points=points)
            except Exception as e:
                print(f"Qdrant upsert failed: {e}")
                
        return count

    def similarity_search_with_score(self, query: str, top_k: int = 4) -> List[Tuple[DocumentChunk, float]]:
        """
        Performs semantic similarity search against stored document vectors.
        Returns list of (DocumentChunk, similarity_score).
        """
        query_vec = self.embedding_service.embed_query(query)
        
        records = self._load_local_index()
        results = []
        
        for r in records:
            score = self._cosine_similarity(query_vec, r["vector"])
            doc_chunk = DocumentChunk(
                page_content=r["page_content"],
                metadata=r["metadata"]
            )
            results.append((doc_chunk, score))
            
        # Sort descending by similarity score
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def list_documents(self) -> List[Dict[str, Any]]:
        """
        Lists unique document sources stored in the vector repository.
        """
        records = self._load_local_index()
        sources = {}
        for r in records:
            meta = r.get("metadata", {})
            src = meta.get("source", "Unknown")
            if src not in sources:
                sources[src] = {
                    "source": src,
                    "file_type": meta.get("file_type", "unknown"),
                    "chunks_count": 0,
                    "sample_preview": r.get("page_content", "")[:100]
                }
            sources[src]["chunks_count"] += 1
            
        return list(sources.values())

    def delete_document(self, filename: str) -> int:
        """
        Deletes all vector chunks associated with a specific file source.
        """
        records = self._load_local_index()
        filtered = [r for r in records if r.get("metadata", {}).get("source") != filename]
        deleted_count = len(records) - len(filtered)
        self._save_local_index(filtered)
        return deleted_count

    def clear_all(self):
        """Clears all stored document vectors."""
        self._save_local_index([])
