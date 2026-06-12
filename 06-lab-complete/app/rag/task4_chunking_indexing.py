"""
Task 4 — Chunking & Indexing vào Vector Store (Weaviate Cloud).
"""

from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .shared import (
    CHUNKING_METHOD,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    STANDARDIZED_DIR,
    VECTOR_STORE,
    embed_texts,
    get_weaviate_client,
)

# Re-export for tests
__all__ = [
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "CHUNKING_METHOD",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIM",
    "VECTOR_STORE",
    "load_documents",
    "chunk_documents",
    "embed_chunks",
    "index_to_vectorstore",
    "run_pipeline",
]


def load_documents() -> list[dict]:
    """Đọc toàn bộ markdown files từ data/standardized/."""
    documents = []
    if not STANDARDIZED_DIR.exists():
        return documents

    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        doc_type = "legal" if "legal" in md_file.parts else "news"
        documents.append(
            {
                "content": content,
                "metadata": {
                    "source": md_file.name,
                    "type": doc_type,
                    "path": str(md_file.relative_to(STANDARDIZED_DIR)),
                },
            }
        )
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chunk documents bằng RecursiveCharacterTextSplitter."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = []
    for doc in documents:
        splits = splitter.split_text(doc["content"])
        for i, chunk_text in enumerate(splits):
            if not chunk_text.strip():
                continue
            chunks.append(
                {
                    "content": chunk_text,
                    "metadata": {**doc["metadata"], "chunk_index": i},
                }
            )
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Embed toàn bộ chunks bằng sentence-transformers."""
    texts = [c["content"] for c in chunks]
    embeddings = embed_texts(texts)
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb
    return chunks


def _ensure_collection(client, recreate: bool = False):
    from weaviate.classes.config import Configure, DataType, Property

    if recreate and client.collections.exists(COLLECTION_NAME):
        client.collections.delete(COLLECTION_NAME)

    if client.collections.exists(COLLECTION_NAME):
        return client.collections.get(COLLECTION_NAME)

    return client.collections.create(
        name=COLLECTION_NAME,
        vectorizer_config=Configure.Vectorizer.none(),
        properties=[
            Property(name="content", data_type=DataType.TEXT),
            Property(name="source", data_type=DataType.TEXT),
            Property(name="doc_type", data_type=DataType.TEXT),
            Property(name="chunk_index", data_type=DataType.INT),
            Property(name="path", data_type=DataType.TEXT),
        ],
    )


def index_to_vectorstore(chunks: list[dict]):
    """Lưu chunks vào Weaviate Cloud."""
    client = get_weaviate_client()
    try:
        collection = _ensure_collection(client, recreate=True)

        with collection.batch.dynamic() as batch:
            for i, chunk in enumerate(chunks):
                meta = chunk["metadata"]
                batch.add_object(
                    properties={
                        "content": chunk["content"],
                        "source": meta.get("source", ""),
                        "doc_type": meta.get("type", ""),
                        "chunk_index": meta.get("chunk_index", 0),
                        "path": meta.get("path", ""),
                    },
                    vector=chunk["embedding"],
                    uuid=None,
                )
    finally:
        client.close()


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n✓ Loaded {len(docs)} documents")
    if not docs:
        print("⚠ Không có documents. Chạy Task 1-3 trước.")
        return

    chunks = chunk_documents(docs)
    print(f"✓ Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"✓ Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("✓ Indexed to vector store")


if __name__ == "__main__":
    run_pipeline()
