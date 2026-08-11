from typing import List
from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import settings
from app.rag.document_loader import DocumentChunk

class TextSplitterService:
    """
    Configurable text chunking service using LangChain's RecursiveCharacterTextSplitter.
    """
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.RAG_CHUNK_OVERLAP
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )

    def split_chunks(self, document_chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """
        Splits raw document chunks into smaller, overlapping text chunks.
        """
        lc_docs = [
            LCDocument(page_content=chunk.page_content, metadata=chunk.metadata)
            for chunk in document_chunks
        ]
        
        split_docs = self.splitter.split_documents(lc_docs)
        
        result = []
        for idx, doc in enumerate(split_docs):
            meta = dict(doc.metadata)
            meta["chunk_id"] = idx
            result.append(DocumentChunk(
                page_content=doc.page_content,
                metadata=meta
            ))
            
        return result
