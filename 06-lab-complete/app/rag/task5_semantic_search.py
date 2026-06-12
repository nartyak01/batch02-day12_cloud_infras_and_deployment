"""
Task 5 — Semantic Search Module.
"""

from weaviate.classes.query import MetadataQuery

from .shared import COLLECTION_NAME, embed_texts, get_weaviate_client


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Tìm kiếm ngữ nghĩa sử dụng vector similarity trên Weaviate."""
    query_embedding = embed_texts([query])[0]

    client = get_weaviate_client()
    try:
        collection = client.collections.get(COLLECTION_NAME)
        response = collection.query.near_vector(
            near_vector=query_embedding,
            limit=top_k,
            return_metadata=MetadataQuery(distance=True),
        )

        results = []
        for obj in response.objects:
            distance = obj.metadata.distance if obj.metadata else 1.0
            score = max(0.0, 1.0 - distance)
            props = obj.properties
            results.append(
                {
                    "content": props.get("content", ""),
                    "score": float(score),
                    "metadata": {
                        "source": props.get("source", ""),
                        "type": props.get("doc_type", ""),
                        "chunk_index": props.get("chunk_index", 0),
                        "path": props.get("path", ""),
                    },
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results
    finally:
        client.close()


if __name__ == "__main__":
    results = semantic_search("hình phạt cho tội tàng trữ ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
