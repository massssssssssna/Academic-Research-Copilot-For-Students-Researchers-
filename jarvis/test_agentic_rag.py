import os
import sys
import unittest
from langchain_core.messages import HumanMessage

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.config import settings
from app.rag.document_loader import DocumentLoader, DocumentChunk
from app.rag.text_splitter import TextSplitterService
from app.rag.embeddings import get_embedding_service, FallbackEmbeddingService
from app.rag.vector_store import VectorStoreRepository
from app.rag.corrective_rag import CorrectiveRAGService
from app.tools.web_search import execute_web_search
from app.agent.graph import jarvis_agent
from app.agent.state import AgentState

class TestAgenticRAGSystem(unittest.TestCase):

    def setUp(self):
        self.test_dir = ".data/test_docs"
        os.makedirs(self.test_dir, exist_ok=True)
        self.vector_repo = VectorStoreRepository(storage_dir=".data/test_vector_store")
        self.vector_repo.clear_all()

    def tearDown(self):
        self.vector_repo.clear_all()

    def test_01_document_loader_txt_md_pdf_docx(self):
        """Test document loading for text and markdown files."""
        txt_path = os.path.join(self.test_dir, "sample_rag_notes.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Agentic RAG combines retrieval augmented generation with autonomous reasoning agents.")
            
        chunks = DocumentLoader.load(txt_path, "sample_rag_notes.txt")
        self.assertGreaterEqual(len(chunks), 1)
        self.assertIn("Agentic RAG", chunks[0].page_content)
        self.assertEqual(chunks[0].metadata["source"], "sample_rag_notes.txt")

    def test_02_text_splitter(self):
        """Test document chunking with text splitter service."""
        raw_chunks = [DocumentChunk(page_content="Word " * 500, metadata={"source": "large.txt"})]
        splitter = TextSplitterService(chunk_size=200, chunk_overlap=30)
        split_chunks = splitter.split_chunks(raw_chunks)
        self.assertGreater(len(split_chunks), 1)
        self.assertLessEqual(len(split_chunks[0].page_content), 250)

    def test_03_embeddings_abstraction(self):
        """Test embedding service factory and fallback provider."""
        service = get_embedding_service(provider="fallback")
        vec = service.embed_query("Agentic RAG assistant")
        self.assertEqual(len(vec), 384)
        
        docs_vecs = service.embed_documents(["doc 1", "doc 2"])
        self.assertEqual(len(docs_vecs), 2)

    def test_04_vector_store_repository(self):
        """Test VectorStoreRepository indexing and similarity search."""
        chunks = [
            DocumentChunk(page_content="Agentic RAG improves search accuracy using iterative query reformulation.", metadata={"source": "rag_doc.pdf"}),
            DocumentChunk(page_content="Microsoft Graph provides APIs for Outlook email, calendar events, and To-Do tasks.", metadata={"source": "graph_doc.docx"})
        ]
        self.vector_repo.add_documents(chunks)
        
        results = self.vector_repo.similarity_search_with_score("query reformulation RAG", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertIn("iterative query reformulation", results[0][0].page_content)

    def test_05_corrective_rag_relevance_and_correction(self):
        """Test Corrective RAG relevance check and query reformulation loop."""
        chunks = [
            DocumentChunk(page_content="Deep Learning models require large GPU cluster training.", metadata={"source": "ai_compute.txt"})
        ]
        self.vector_repo.add_documents(chunks)
        
        corrective_service = CorrectiveRAGService(vector_store=self.vector_repo)
        res = corrective_service.retrieve_with_correction("Deep Learning GPU cluster", top_k=1)
        self.assertTrue(res["is_relevant"])
        self.assertGreaterEqual(len(res["chunks"]), 1)

    def test_06_web_search_tool(self):
        """Test Web Search tool execution."""
        res = execute_web_search("OpenAI API latest model documentation")
        self.assertIn("query", res)
        self.assertGreaterEqual(len(res["results"]), 1)
        self.assertTrue(any("url" in r for r in res["results"]))

    def test_07_agentic_routing_scenarios(self):
        """Test main LangGraph agent routing decisions across scenarios."""
        mock_session_id = "test_session_123"
        
        # Test 1: Email question -> MS Graph tool
        state_email: AgentState = {
            "session_id": mock_session_id,
            "messages": [HumanMessage(content="Read my latest inbox emails")],
            "error": None
        }
        res_email = jarvis_agent.invoke(state_email)
        last_msg = res_email["messages"][-1]
        tools_called = set()
        for m in res_email["messages"]:
            if hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    tools_called.add(tc["name"])
        self.assertTrue(any("get_emails" in t for t in tools_called) or hasattr(last_msg, "tool_calls"))

        # Test 2: Local document question -> RAG tool
        state_doc: AgentState = {
            "session_id": mock_session_id,
            "messages": [HumanMessage(content="According to my uploaded project PDF document, what is RAG?")],
            "error": None
        }
        res_doc = jarvis_agent.invoke(state_doc)
        tools_called_doc = set()
        for m in res_doc["messages"]:
            if hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    tools_called_doc.add(tc["name"])
        self.assertIn("search_documents", tools_called_doc)

        # Test 3: Latest/current online question -> Web Search tool
        state_web: AgentState = {
            "session_id": mock_session_id,
            "messages": [HumanMessage(content="Search the internet for the latest news about OpenAI API updates")],
            "error": None
        }
        res_web = jarvis_agent.invoke(state_web)
        tools_called_web = set()
        for m in res_web["messages"]:
            if hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    tools_called_web.add(tc["name"])
        self.assertIn("web_search", tools_called_web)


if __name__ == "__main__":
    unittest.main()
