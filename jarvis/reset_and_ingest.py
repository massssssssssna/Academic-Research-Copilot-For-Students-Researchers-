import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.rag.vector_store import VectorStoreRepository
from app.rag.document_loader import DocumentLoader
from app.rag.text_splitter import TextSplitterService

DATA_DIR = "data"
DOCS_DIR = ".data/documents"

DOC_1_CONTENT = """Jarvis Academic Research Demo

Document Purpose
This is a fictional academic research document created for testing a Jarvis assistant with Retrieval-Augmented Generation (RAG). The information is intentionally self-contained so that a local document retriever can answer questions from it.

Research Project
Project Title: Intelligent Academic Assistant for University Students
The project explores how an AI assistant can help university students manage academic information, research notes, deadlines, and routine productivity tasks.

Research Objectives
Objective 1: Evaluate whether an AI assistant can retrieve accurate information from private academic documents.
Objective 2: Compare ordinary retrieval with corrective retrieval when irrelevant document chunks are returned.
Objective 3: Study whether an agent can select between local document retrieval and external web search.

Proposed System
The proposed assistant contains a main reasoning agent, a local document RAG system, a web-search tool, and productivity tools. The main agent decides which source is appropriate for each request.
The local RAG system contains university notes, research documents, project reports, and academic guidelines.

Research Method
Documents are loaded, split into smaller chunks, converted into embeddings, and stored in a vector database. When a student asks a question, relevant chunks are retrieved and passed to the reasoning model.
For corrective RAG, retrieved chunks are checked for relevance. If the context is weak or unrelated, the system reformulates the query and performs another retrieval attempt.

Evaluation Metrics
Retrieval accuracy measures whether the correct document information was retrieved. Answer faithfulness measures whether the generated answer is supported by retrieved context. Tool-selection accuracy measures whether the agent selected an appropriate tool.

Test Facts
The fictional research team has four students. The project review meeting is scheduled for Thursday at 2:00 PM. The literature review is planned for Week 3, the prototype for Week 5, and the final evaluation for Week 8.
The preferred vector search strategy for the demo is semantic similarity using embeddings. The demo should keep source metadata with every retrieved chunk.
"""

DOC_2_CONTENT = """Jarvis Student Academic Guidelines Demo

Document Purpose
This fictional document represents a university academic guide that can be uploaded into Jarvis as a private knowledge source.

Assignment Workflow
Students should first read the assignment requirements, identify deliverables, divide the work into smaller tasks, and record important deadlines.
A research assignment normally includes a topic definition, literature search, source evaluation, notes, draft writing, review, and final submission.

Research Source Evaluation
Students should prefer credible academic sources and verify important claims. Useful checks include the author's expertise, publication venue, publication date, evidence quality, and whether other reliable sources support the claim.

AI Assistant Guidelines
An AI assistant may help students organize notes, retrieve information from their private documents, summarize supplied material, and identify missing information. Students should verify important academic claims before submitting work.
When the question concerns information inside uploaded university documents, Jarvis should prefer the local RAG knowledge base. When the user asks for current external information, Jarvis may use web search.

Jarvis Tool Routing Examples
Question: 'According to my research guide, what should I check before using a source?' -> Use RAG.
Question: 'What is the latest research about agentic RAG?' -> Use Web Search.
Question: 'Read my research notes and compare them with current online information.' -> Use RAG and Web Search.
Question: 'Show my upcoming academic meeting.' -> Use Microsoft Graph Calendar.

Demo Schedule
Monday: collect research sources and update notes.
Wednesday: complete the literature review draft.
Thursday: attend the 2:00 PM project review meeting.
Friday: revise the project document based on feedback.

Expected RAG Answers
If asked which week the prototype is planned for, the correct answer from the research document is Week 5.
If asked when the fictional project review meeting occurs, the correct answer is Thursday at 2:00 PM.
If asked what the assignment workflow includes, the answer should mention requirements, task breakdown, research, notes, drafting, review, and submission.
"""

def reset_and_reingest():
    print("[RESET] Clearing previous vector store index and document cache...")
    vector_repo = VectorStoreRepository()
    vector_repo.clear_all()
    
    # Clean data & .data/documents directories
    for d in [DATA_DIR, DOCS_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
        
    # Write clean document files
    file1_data = os.path.join(DATA_DIR, "Jarvis_Academic_Research_Demo.txt")
    file2_data = os.path.join(DATA_DIR, "Jarvis_Student_Academic_Guidelines_Demo.txt")
    
    file1_docs = os.path.join(DOCS_DIR, "Jarvis_Academic_Research_Demo.txt")
    file2_docs = os.path.join(DOCS_DIR, "Jarvis_Student_Academic_Guidelines_Demo.txt")
    
    for fpath in [file1_data, file1_docs]:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(DOC_1_CONTENT)
            
    for fpath in [file2_data, file2_docs]:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(DOC_2_CONTENT)
            
    print("[INGEST] Chunking and embedding fresh demo documents...")
    splitter = TextSplitterService()
    
    chunks_indexed = 0
    for fname in ["Jarvis_Academic_Research_Demo.txt", "Jarvis_Student_Academic_Guidelines_Demo.txt"]:
        fpath = os.path.join(DATA_DIR, fname)
        raw_chunks = DocumentLoader.load(fpath, filename=fname)
        split_chunks = splitter.split_chunks(raw_chunks)
        count = vector_repo.add_documents(split_chunks)
        chunks_indexed += count
        print(f"  + Indexed '{fname}' -> {count} chunk(s).")
        
    print(f"[SUCCESS] Clean re-ingestion finished! Total chunks indexed: {chunks_indexed}")

if __name__ == "__main__":
    reset_and_reingest()
