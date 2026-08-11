import os
import re
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class DocumentChunk:
    page_content: str
    metadata: Dict[str, Any]

class DocumentLoader:
    """
    Extensible Document Loader for PDF, DOCX, TXT, and Markdown files.
    Extracts raw text and rich metadata.
    """
    
    @staticmethod
    def load(file_path: str, filename: str = "") -> List[DocumentChunk]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        ext = os.path.splitext(file_path)[1].lower()
        fname = filename or os.path.basename(file_path)
        
        if ext == ".pdf":
            return DocumentLoader._load_pdf(file_path, fname)
        elif ext == ".docx":
            return DocumentLoader._load_docx(file_path, fname)
        elif ext in [".txt", ".md", ".markdown"]:
            return DocumentLoader._load_text(file_path, fname, ext)
        else:
            raise ValueError(f"Unsupported document format: '{ext}'. Supported formats: .pdf, .docx, .txt, .md")

    @staticmethod
    def _load_pdf(file_path: str, filename: str) -> List[DocumentChunk]:
        chunks = []
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append(DocumentChunk(
                        page_content=text.strip(),
                        metadata={
                            "source": filename,
                            "file_path": file_path,
                            "file_type": "pdf",
                            "page": page_num,
                            "total_pages": len(reader.pages)
                        }
                    ))
        except Exception:
            with open(file_path, "rb") as f:
                raw = f.read().decode("latin-1", errors="ignore")
                clean_text = re.sub(r'[^\x20-\x7E\n\t]', ' ', raw)
                chunks.append(DocumentChunk(
                    page_content=clean_text.strip(),
                    metadata={"source": filename, "file_path": file_path, "file_type": "pdf", "page": 1}
                ))
        return chunks

    @staticmethod
    def _load_docx(file_path: str, filename: str) -> List[DocumentChunk]:
        chunks = []
        try:
            import docx
            doc = docx.Document(file_path)
            full_text = []
            for p in doc.paragraphs:
                if p.text.strip():
                    full_text.append(p.text.strip())
            
            combined_text = "\n\n".join(full_text)
            if combined_text:
                chunks.append(DocumentChunk(
                    page_content=combined_text,
                    metadata={
                        "source": filename,
                        "file_path": file_path,
                        "file_type": "docx",
                        "paragraphs_count": len(full_text)
                    }
                ))
        except Exception:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
                chunks.append(DocumentChunk(
                    page_content=text,
                    metadata={"source": filename, "file_path": file_path, "file_type": "docx"}
                ))
        return chunks

    @staticmethod
    def _load_text(file_path: str, filename: str, ext: str) -> List[DocumentChunk]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        file_type = "markdown" if ext in [".md", ".markdown"] else "txt"
        return [DocumentChunk(
            page_content=content.strip(),
            metadata={
                "source": filename,
                "file_path": file_path,
                "file_type": file_type,
                "char_count": len(content)
            }
        )]
