"""
Vector store service using pgvector (PostgreSQL extension)

TODO: Implement vector storage using pgvector
- Create embeddings table in PostgreSQL
- Store document chunks with vector embeddings
- Implement similarity search using pgvector operators
- Handle metadata filtering
"""
from typing import List, Dict, Any, Optional
import numpy as np
import os
from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.core.config import settings
from app.db.session import SessionLocal


class VectorStore:
    """pgvector-based vector store for document embeddings"""
    
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
        self.embeddings = self._initialize_embeddings()
        self._ensure_extension()
    
    def _initialize_embeddings(self):
        """
        Initialize embedding model based on LLM provider

        When using Gemini or Ollama, use HuggingFace (local) embeddings
        because these providers don't offer embeddings APIs.
        Only use OpenAI embeddings when explicitly using OpenAI provider.
        """
        llm_provider = os.getenv("LLM_PROVIDER", "openai").lower()

        # Use OpenAI embeddings only when explicitly using OpenAI provider
        if llm_provider == "openai" and settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "sk-your-api-key-here":
            print("Initializing OpenAI embeddings...")
            return OpenAIEmbeddings(
                model=settings.OPENAI_EMBEDDING_MODEL,
                openai_api_key=settings.OPENAI_API_KEY
            )
        else:
            # Use local HuggingFace embeddings for Gemini, Ollama, or when no valid OpenAI key
            print(f"Initializing HuggingFace embeddings (LLM provider: {llm_provider})...")
            return HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
    
    def _ensure_extension(self):
        """
        Ensure pgvector extension is enabled

        Creates document_embeddings table with appropriate vector dimensions:
        - 1536 for OpenAI embeddings
        - 384 for HuggingFace sentence-transformers
        """
        try:
            # Enable pgvector extension
            self.db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # Determine embedding dimension based on LLM provider
            llm_provider = os.getenv("LLM_PROVIDER", "openai").lower()
            dimension = 1536 if llm_provider == "openai" and settings.OPENAI_API_KEY != "sk-your-api-key-here" else 384
            
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS document_embeddings (
                id SERIAL PRIMARY KEY,
                document_id INTEGER,
                fund_id INTEGER,
                content TEXT NOT NULL,
                embedding vector({dimension}),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS document_embeddings_embedding_idx 
            ON document_embeddings USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
            """
            
            self.db.execute(text(create_table_sql))
            self.db.commit()
        except Exception as e:
            print(f"Error ensuring pgvector extension: {e}")
            self.db.rollback()
    
    async def add_document(self, content: str, metadata: Dict[str, Any]):
        """
        Add a document to the vector store

        - Generate embedding for content
        - Insert into document_embeddings table
        - Store metadata as JSONB
        """
        try:
            # Generate embedding (sync call, not async)
            embedding = self._get_embedding(content)
            embedding_list = embedding.tolist()

            # Convert metadata to JSON string
            import json
            metadata_json = json.dumps(metadata)

            # Insert into database
            insert_sql = text("""
                INSERT INTO document_embeddings (document_id, fund_id, content, embedding, metadata)
                VALUES (:document_id, :fund_id, :content, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
            """)

            self.db.execute(insert_sql, {
                "document_id": metadata.get("document_id"),
                "fund_id": metadata.get("fund_id"),
                "content": content,
                "embedding": str(embedding_list),
                "metadata": metadata_json
            })
            self.db.commit()
        except Exception as e:
            print(f"Error adding document: {e}")
            self.db.rollback()
            raise
    
    async def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents using cosine similarity

        - Generate query embedding
        - Use pgvector's <=> operator for cosine distance
        - Apply metadata filters if provided
        - Return top k results

        Args:
            query: Search query
            k: Number of results to return
            filter_metadata: Optional metadata filters (e.g., {"fund_id": 1})

        Returns:
            List of similar documents with scores
        """
        try:
            # Generate query embedding (sync call, not async)
            query_embedding = self._get_embedding(query)
            embedding_list = query_embedding.tolist()

            # Build query with optional filters
            where_clause = ""
            params = {
                "query_embedding": str(embedding_list),
                "k": k
            }

            if filter_metadata:
                conditions = []
                for key, value in filter_metadata.items():
                    if key in ["document_id", "fund_id"]:
                        conditions.append(f"{key} = :{key}")
                        params[key] = value
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

            # Search using cosine distance (<=> operator)
            search_sql = text(f"""
                SELECT
                    id,
                    document_id,
                    fund_id,
                    content,
                    metadata,
                    1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity_score
                FROM document_embeddings
                {where_clause}
                ORDER BY embedding <=> CAST(:query_embedding AS vector)
                LIMIT :k
            """)

            result = self.db.execute(search_sql, params)

            # Format results
            results = []
            for row in result:
                results.append({
                    "id": row[0],
                    "document_id": row[1],
                    "fund_id": row[2],
                    "content": row[3],
                    "metadata": row[4],
                    "score": float(row[5]) if row[5] is not None else 0.0
                })

            return results
        except Exception as e:
            print(f"Error in similarity search: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text (synchronous)"""
        if hasattr(self.embeddings, 'embed_query'):
            embedding = self.embeddings.embed_query(text)
        else:
            embedding = self.embeddings.encode(text)

        return np.array(embedding, dtype=np.float32)
    
    def clear(self, fund_id: Optional[int] = None):
        """
        Clear the vector store
        
        TODO: Implement this method
        - Delete all embeddings (or filter by fund_id)
        """
        try:
            if fund_id:
                delete_sql = text("DELETE FROM document_embeddings WHERE fund_id = :fund_id")
                self.db.execute(delete_sql, {"fund_id": fund_id})
            else:
                delete_sql = text("DELETE FROM document_embeddings")
                self.db.execute(delete_sql)
            
            self.db.commit()
        except Exception as e:
            print(f"Error clearing vector store: {e}")
            self.db.rollback()
