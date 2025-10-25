"""
Document processing service using pdfplumber

Implements the document processing pipeline:
- Extract tables from PDF using pdfplumber
- Classify tables (capital calls, distributions, adjustments)
- Extract and chunk text for vector storage
- Handle errors and edge cases
"""
from typing import Dict, List, Any
import pdfplumber
from app.core.config import settings
from app.services.table_parser import TableParser
from app.services.vector_store import VectorStore
from app.models.transaction import CapitalCall, Distribution, Adjustment
from app.models.document import Document
from sqlalchemy.orm import Session
import re


class DocumentProcessor:
    """Process PDF documents and extract structured data"""

    def __init__(self, db: Session):
        self.db = db
        self.table_parser = TableParser()
        self.vector_store = VectorStore(db)

    async def process_document(self, file_path: str, document_id: int, fund_id: int) -> Dict[str, Any]:
        """
        Process a PDF document

        - Open PDF with pdfplumber
        - Extract tables from each page
        - Parse and classify tables using TableParser
        - Extract text and create chunks
        - Store chunks in vector database
        - Return processing statistics

        Args:
            file_path: Path to the PDF file
            document_id: Database document ID
            fund_id: Fund ID

        Returns:
            Processing result with statistics
        """
        stats = {
            "pages_processed": 0,
            "tables_found": 0,
            "capital_calls": 0,
            "distributions": 0,
            "adjustments": 0,
            "text_chunks": 0,
            "errors": []
        }

        # Update document status to processing
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.parsing_status = "processing"
            self.db.commit()

        try:
            # Open PDF with pdfplumber
            with pdfplumber.open(file_path) as pdf:
                all_text_content = []

                # Process each page
                for page_num, page in enumerate(pdf.pages, start=1):
                    try:
                        # Extract tables
                        tables = page.extract_tables()
                        if tables:
                            stats["tables_found"] += len(tables)

                            for table in tables:
                                # Parse and classify table
                                result = self.table_parser.parse_table(table, fund_id)

                                # Store parsed data in database
                                if result["type"] == "capital_call":
                                    for call_data in result["data"]:
                                        capital_call = CapitalCall(**call_data)
                                        self.db.add(capital_call)
                                        stats["capital_calls"] += 1

                                elif result["type"] == "distribution":
                                    for dist_data in result["data"]:
                                        distribution = Distribution(**dist_data)
                                        self.db.add(distribution)
                                        stats["distributions"] += 1

                                elif result["type"] == "adjustment":
                                    for adj_data in result["data"]:
                                        adjustment = Adjustment(**adj_data)
                                        self.db.add(adjustment)
                                        stats["adjustments"] += 1

                            # Commit after each page
                            self.db.commit()

                        # Extract text from page
                        text = page.extract_text()
                        if text:
                            all_text_content.append({
                                "text": text,
                                "page_number": page_num,
                                "document_id": document_id,
                                "fund_id": fund_id
                            })

                        stats["pages_processed"] += 1

                    except Exception as e:
                        error_msg = f"Error processing page {page_num}: {str(e)}"
                        print(error_msg)
                        stats["errors"].append(error_msg)
                        continue

                # Chunk text and store in vector database
                if all_text_content:
                    chunks = self._chunk_text(all_text_content)
                    for chunk in chunks:
                        try:
                            await self.vector_store.add_document(
                                content=chunk["text"],
                                metadata={
                                    "document_id": chunk["document_id"],
                                    "fund_id": chunk["fund_id"],
                                    "page_number": chunk["page_number"],
                                    "chunk_index": chunk.get("chunk_index", 0)
                                }
                            )
                            stats["text_chunks"] += 1
                        except Exception as e:
                            error_msg = f"Error storing text chunk: {str(e)}"
                            print(error_msg)
                            stats["errors"].append(error_msg)

            # Update document status to completed
            if doc:
                doc.parsing_status = "completed"
                self.db.commit()

            return stats

        except Exception as e:
            # Update document status to failed
            if doc:
                doc.parsing_status = "failed"
                doc.error_message = str(e)
                self.db.commit()

            error_msg = f"Error processing document: {str(e)}"
            print(error_msg)
            stats["errors"].append(error_msg)
            raise

    def _chunk_text(self, text_content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunk text content for vector storage

        - Split text into semantic chunks
        - Maintain context overlap
        - Preserve sentence boundaries
        - Add metadata to each chunk

        Args:
            text_content: List of text content with metadata

        Returns:
            List of text chunks with metadata
        """
        chunks = []
        chunk_size = settings.CHUNK_SIZE
        chunk_overlap = settings.CHUNK_OVERLAP

        for content in text_content:
            text = content["text"]
            page_number = content["page_number"]
            document_id = content["document_id"]
            fund_id = content["fund_id"]

            # Skip empty or very short text
            if not text or len(text.strip()) < 50:
                continue

            # Clean text
            text = self._clean_text(text)

            # Split into sentences for better chunking
            sentences = self._split_into_sentences(text)

            # Create chunks
            current_chunk = []
            current_length = 0
            chunk_index = 0

            for sentence in sentences:
                sentence_length = len(sentence)

                # If adding this sentence exceeds chunk size, save current chunk
                if current_length + sentence_length > chunk_size and current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append({
                        "text": chunk_text,
                        "page_number": page_number,
                        "document_id": document_id,
                        "fund_id": fund_id,
                        "chunk_index": chunk_index
                    })
                    chunk_index += 1

                    # Start new chunk with overlap
                    overlap_text = chunk_text[-chunk_overlap:] if len(chunk_text) > chunk_overlap else chunk_text
                    overlap_sentences = self._split_into_sentences(overlap_text)
                    current_chunk = overlap_sentences
                    current_length = len(overlap_text)

                # Add sentence to current chunk
                current_chunk.append(sentence)
                current_length += sentence_length

            # Add remaining chunk
            if current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "text": chunk_text,
                    "page_number": page_number,
                    "document_id": document_id,
                    "fund_id": fund_id,
                    "chunk_index": chunk_index
                })

        return chunks

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove page numbers and common PDF artifacts
        text = re.sub(r'\bPage\s+\d+\s+of\s+\d+\b', '', text, flags=re.IGNORECASE)

        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        return text.strip()

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting (can be improved with NLTK or spaCy)
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences
