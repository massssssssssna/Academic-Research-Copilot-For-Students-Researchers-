"""
Corrective RAG Pipeline - Robust retrieval with multi-key Groq failover,
adaptive relevance grading, and automated query reformulation.
"""
from typing import List, Dict, Any, Tuple
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from app.config import settings
from app.rag.vector_store import VectorStoreRepository
from app.rag.document_loader import DocumentChunk


class CorrectiveRAGService:
    """
    Corrective RAG Pipeline with lightweight relevance grading and automated
    query reformulation. Works even when Groq is rate-limited using multi-key
    failover and score-based fallback.
    """

    # Similarity threshold: chunks above this score are accepted without LLM grading
    ACCEPT_SCORE = 0.25
    # Chunks above this score are always returned even if LLM says not relevant
    MIN_RETURN_SCORE = 0.15

    def __init__(self, vector_store: VectorStoreRepository = None):
        self.vector_store = vector_store or VectorStoreRepository()
        self.max_retries = settings.CORRECTIVE_RAG_MAX_RETRIES

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _get_groq_llm(self, fast: bool = True):
        """Returns a ChatGroq instance, cycling through all available API keys."""
        keys = settings.get_groq_api_keys()
        models = (
            [settings.LLM_FAST_MODEL, "llama3-8b-8192", "gemma2-9b-it"]
            if fast
            else [settings.LLM_PRIMARY_MODEL, "llama3-70b-8192", "llama3-8b-8192"]
        )
        last_error = None
        for key in keys:
            for model in models:
                try:
                    return ChatGroq(
                        groq_api_key=key,
                        model_name=model,
                        temperature=0.0,
                        max_tokens=60,
                        max_retries=0,
                    )
                except Exception as e:
                    last_error = e
                    continue
        return None

    def _grade_relevance(
        self, query: str, chunks: List[Tuple[DocumentChunk, float]]
    ) -> bool:
        """
        Evaluates whether retrieved chunks are relevant to the user query.
        Priority: score threshold → LLM grading → lenient score fallback.
        """
        if not chunks:
            return False

        best_score = max(score for _, score in chunks)

        # Fast-accept: high-confidence similarity score
        if best_score >= self.ACCEPT_SCORE:
            return True

        # LLM-based relevance grading (skip if keys unavailable)
        try:
            llm = self._get_groq_llm(fast=True)
            if llm is None:
                return best_score >= self.MIN_RETURN_SCORE

            context_snippet = "\n\n".join(
                c.page_content[:200] for c, _ in chunks[:2]
            )
            prompt = (
                f"Query: {query}\n"
                f"Context: {context_snippet}\n"
                "Is this context useful for answering the query? "
                "Reply ONLY with 'yes' or 'no'."
            )
            res = llm.invoke([HumanMessage(content=prompt)]).content.strip().lower()
            return "yes" in res

        except Exception as e:
            print(f"[CorrectiveRAG] Relevance grading error: {e}")
            return best_score >= self.MIN_RETURN_SCORE

    def _reformulate_query(self, original_query: str, attempt: int) -> str:
        """
        Reformulates the query using LLM to improve vector retrieval on retry.
        Falls back to keyword extraction if LLM is unavailable.
        """
        try:
            llm = self._get_groq_llm(fast=True)
            if llm:
                prompt = (
                    f"The search query '{original_query}' did not retrieve relevant local document chunks.\n"
                    f"Rephrase or extract key technical terms to better search a vector document database.\n"
                    f"Reply ONLY with the refined query (no quotes, no explanation)."
                )
                res = llm.invoke([HumanMessage(content=prompt)]).content.strip()
                if res and res != original_query and len(res) < 200:
                    print(f"[CorrectiveRAG] Attempt {attempt}: Reformulated query → '{res}'")
                    return res
        except Exception as e:
            print(f"[CorrectiveRAG] Query reformulation error: {e}")

        # Keyword fallback
        words = [w for w in original_query.split() if len(w) > 3]
        fallback = " ".join(words) if words else original_query
        print(f"[CorrectiveRAG] Attempt {attempt}: Keyword fallback query → '{fallback}'")
        return fallback

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def retrieve_with_correction(
        self, query: str, top_k: int = 4
    ) -> Dict[str, Any]:
        """
        Retrieves document chunks with the Corrective RAG loop.
        Returns relevant chunks even when the LLM grader is unavailable by
        falling back to the best-scored chunks from the final attempt.
        """
        current_query = query
        attempts_log = []
        final_chunks: List[Tuple[DocumentChunk, float]] = []
        is_relevant = False

        for attempt in range(1, self.max_retries + 2):
            retrieved = self.vector_store.similarity_search_with_score(
                current_query, top_k=top_k
            )
            is_relevant = self._grade_relevance(query, retrieved)

            best_score = max((s for _, s in retrieved), default=0.0)
            attempts_log.append(
                {
                    "attempt": attempt,
                    "query": current_query,
                    "chunks_retrieved": len(retrieved),
                    "is_relevant": is_relevant,
                    "best_score": round(best_score, 3),
                }
            )

            print(
                f"[CorrectiveRAG] Attempt {attempt}: query='{current_query[:60]}' "
                f"chunks={len(retrieved)} best_score={round(best_score,3)} relevant={is_relevant}"
            )

            if is_relevant:
                final_chunks = retrieved
                break

            if attempt > self.max_retries:
                # Even if not graded as relevant, return best available chunks
                # so the LLM can at least try to answer from local documents
                final_chunks = retrieved if best_score >= self.MIN_RETURN_SCORE else []
                break

            # Query reformulation for next attempt
            current_query = self._reformulate_query(query, attempt)

        return {
            "query": query,
            "final_query_used": current_query,
            "is_relevant": is_relevant,
            "retries": len(attempts_log) - 1,
            "attempts_log": attempts_log,
            "chunks": final_chunks,
        }
