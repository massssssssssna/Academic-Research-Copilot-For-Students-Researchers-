import os
import shutil
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request
from pydantic import BaseModel
from app.rag.document_loader import DocumentLoader
from app.rag.text_splitter import TextSplitterService
from app.rag.vector_store import VectorStoreRepository
from app.database.supabase import supabase_db

router = APIRouter(prefix="/api/documents", tags=["Documents"])

DOCS_DIR = ".data/documents"
os.makedirs(DOCS_DIR, exist_ok=True)

def get_session_id(request: Request) -> str:
    session_id = request.cookies.get("jarvis_session")
    if not session_id:
        return "default_jarvis_session"
    return session_id

@router.post("/upload")
async def upload_document(file: UploadFile = File(...), session_id: str = Depends(get_session_id)):
    session = supabase_db.get_user_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
        
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".docx", ".txt", ".md", ".markdown"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Supported: PDF, DOCX, TXT, MD")
        
    file_path = os.path.join(DOCS_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Ingestion Pipeline: Load -> Extract -> Chunk -> Embed -> Vector Store
        raw_chunks = DocumentLoader.load(file_path, filename=file.filename)
        splitter = TextSplitterService()
        split_chunks = splitter.split_chunks(raw_chunks)
        
        vector_repo = VectorStoreRepository()
        indexed_count = vector_repo.add_documents(split_chunks)
        
        return {
            "message": f"Successfully ingested '{file.filename}'",
            "filename": file.filename,
            "raw_chunks": len(raw_chunks),
            "split_chunks_indexed": indexed_count
        }
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")

@router.get("")
@router.get("/")
async def list_documents(session_id: str = Depends(get_session_id)):
    session = supabase_db.get_user_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
        
    vector_repo = VectorStoreRepository()
    return vector_repo.list_documents()

@router.delete("/{filename}")
async def delete_document(filename: str, session_id: str = Depends(get_session_id)):
    session = supabase_db.get_user_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
        
    vector_repo = VectorStoreRepository()
    deleted_chunks = vector_repo.delete_document(filename)
    
    file_path = os.path.join(DOCS_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        
    return {
        "message": f"Deleted document '{filename}'",
        "filename": filename,
        "deleted_chunks": deleted_chunks
    }
