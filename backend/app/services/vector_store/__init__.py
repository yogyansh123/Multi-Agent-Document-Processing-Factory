"""
services/vector_store/__init__.py
==================================
Vector database provider abstraction.

Used for RAG (Retrieval-Augmented Generation) document querying.
The active provider is selected via the VECTOR_DB_PROVIDER environment variable.

Planned providers:
- chromadb  — ChromaDB (local, no setup required)
- pinecone  — Pinecone (managed, production-ready)
- weaviate  — Weaviate (open source + managed)
- qdrant    — Qdrant (open source + managed)
- pgvector  — pgvector PostgreSQL extension (reuses existing DB)

Future interface will look like:
    class VectorStoreProvider(ABC):
        @abstractmethod
        async def upsert(self, documents: list[Document]) -> None: ...

        @abstractmethod
        async def search(self, query: str, top_k: int = 5) -> list[SearchResult]: ...

        @abstractmethod
        async def delete(self, document_id: str) -> None: ...
"""
