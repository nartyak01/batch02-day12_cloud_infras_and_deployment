"""
Task 9 — Retrieval Pipeline Hoàn Chỉnh.
"""

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank, rerank_rrf
from .task8_pageindex_vectorless import pageindex_search

SCORE_THRESHOLD = 0.3
DEFAULT_TOP_K = 5
RERANK_METHOD = "cross_encoder"


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """Retrieval pipeline hoàn chỉnh với fallback logic."""
    fetch_k = top_k * 2
    final_results: list[dict] = []

    try:
        dense_results = semantic_search(query, top_k=fetch_k)
    except Exception:
        dense_results = []

    try:
        sparse_results = lexical_search(query, top_k=fetch_k)
    except Exception:
        sparse_results = []

    if dense_results or sparse_results:
        merged = rerank_rrf(
            [r for r in [dense_results, sparse_results] if r],
            top_k=fetch_k,
        )
        for item in merged:
            item["source"] = "hybrid"
            if "metadata" not in item:
                item["metadata"] = {}

        if use_reranking and merged:
            try:
                final_results = rerank(query, merged, top_k=top_k, method=RERANK_METHOD)
            except Exception:
                final_results = merged[:top_k]
        else:
            final_results = merged[:top_k]

        for item in final_results:
            item["source"] = "hybrid"

        best_score = final_results[0]["score"] if final_results else 0.0
        if final_results and best_score >= score_threshold:
            return final_results[:top_k]

    try:
        fallback = pageindex_search(query, top_k=top_k)
        if fallback:
            return fallback
    except Exception:
        pass

    return final_results[:top_k]


if __name__ == "__main__":
    test_queries = [
        "Hình phạt cho tội tàng trữ trái phép chất ma tuý",
        "Nghệ sĩ nào bị bắt vì sử dụng ma tuý năm 2024",
        "Luật phòng chống ma tuý 2021 quy định gì về cai nghiện",
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        print("-" * 60)
        results = retrieve(q, top_k=3)
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r['score']:.3f}] [{r.get('source', '?')}] {r['content'][:80]}...")
