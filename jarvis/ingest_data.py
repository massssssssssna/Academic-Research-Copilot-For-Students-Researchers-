import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.rag.document_loader import DocumentLoader
from app.rag.text_splitter import TextSplitterService
from app.rag.vector_store import VectorStoreRepository

DATA_DIRS = ["data", ".data/documents"]

def ingest_all_documents():
    """
    Scans data folders, loads documents (PDF, DOCX, TXT, MD),
    splits them into chunks, embeds them, and updates vector index.
    """
    vector_repo = VectorStoreRepository()
    splitter = TextSplitterService()
    
    total_files = 0
    total_indexed = 0
    
    for ddir in DATA_DIRS:
        if not os.path.exists(ddir):
            continue
            
        for fname in os.listdir(ddir):
            ext = os.path.splitext(fname)[1].lower()
            if ext in [".pdf", ".docx", ".txt", ".md", ".markdown"]:
                fpath = os.path.join(ddir, fname)
                try:
                    # Check if already indexed
                    existing = [d["source"] for d in vector_repo.list_documents()]
                    if fname in existing:
                        continue
                        
                    raw_chunks = DocumentLoader.load(fpath, filename=fname)
                    split_chunks = splitter.split_chunks(raw_chunks)
                    count = vector_repo.add_documents(split_chunks)
                    
                    total_files += 1
                    total_indexed += count
                    print(f"[INGESTED] '{fname}' -> {count} chunk(s) stored.")
                except Exception as e:
                    print(f"[ERROR] Ingesting '{fname}': {e}")
                    
    return total_files, total_indexed

if __name__ == "__main__":
    print("[START] Ingesting documents into Jarvis Vector Repository...")
    files, chunks = ingest_all_documents()
    print(f"[SUCCESS] Ingestion complete: {files} file(s), {chunks} chunk(s) indexed.")
