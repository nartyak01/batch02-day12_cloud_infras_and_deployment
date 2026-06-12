"""
Task 7 — Reranking Module.
"""

import os
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

JINA_API_KEY = os.getenv("JINA_API_KEY", "")


def rerank_cross_encoder(
    query: str, candidates: list[dict], top_k: int = 5
) -> list[dict]:
    """Rerank candidates sử dụng Jina Reranker API (fallback: score sort)."""
    if not candidates:
        return []

    if not JINA_API_KEY:
        sorted_cands = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
        return sorted_cands[:top_k]

    try:
        response = requests.post(
            "https://api.jina.ai/v1/rerank",
            headers={
                "Authorization": f"Bearer {JINA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "jina-reranker-v2-base-multilingual",
                "query": query,
                "documents": [c["content"] for c in candidates],
                "top_n": min(top_k, len(candidates)),
            },
            timeout=30,
        )
        response.raise_for_status()
        reranked = response.json().get("results", [])

        results = []
        for r in reranked:
            item = candidates[r["index"]].copy()
            item["score"] = float(r["relevance_score"])
            results.append(item)
        return results
    except Exception:
        sorted_cands = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
        return sorted_cands[:top_k]


def _cosine_sim(a: list[float], b: list[float]) -> float:
    import numpy as np

    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    """Maximal Marginal Relevance — chọn candidates vừa relevant vừa diverse."""
    if not candidates:
        return []

    selected: list[int] = []
    remaining = list(range(len(candidates)))

    for _ in range(min(top_k, len(candidates))):
        best_idx = None
        best_score = float("-inf")

        for idx in remaining:
            emb = candidates[idx].get("embedding")
            if emb:
                relevance = _cosine_sim(query_embedding, emb)
            else:
                relevance = candidates[idx].get("score", 0)

            max_sim_to_selected = 0.0
            for sel_idx in selected:
                sel_emb = candidates[sel_idx].get("embedding")
                if emb and sel_emb:
                    sim = _cosine_sim(emb, sel_emb)
                    max_sim_to_selected = max(max_sim_to_selected, sim)

            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        if best_idx is not None:
            selected.append(best_idx)
            remaining.remove(best_idx)

    results = []
    for idx in selected:
        item = candidates[idx].copy()
        item["score"] = float(best_score if idx == selected[-1] else item.get("score", 0))
        results.append(item)
    return results


def rerank_rrf(
    ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60
) -> list[dict]:
    """Reciprocal Rank Fusion — gộp kết quả từ nhiều ranker."""
    rrf_scores: dict[str, float] = {}
    content_map: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):
            key = item["content"]
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k + rank)
            content_map[key] = item

    sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for content, score in sorted_items[:top_k]:
        item = content_map[content].copy()
        item["score"] = float(score)
        results.append(item)
    return results


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    method: str = "cross_encoder",
) -> list[dict]:
    """Unified reranking interface."""
    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    elif method == "mmr":
        from .shared import embed_texts

        query_embedding = embed_texts([query])[0]
        return rerank_mmr(query_embedding, candidates, top_k)
    elif method == "rrf":
        return rerank_rrf([candidates], top_k)
    else:
        raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    dummy_candidates = [
        {"content": "Điều 248: Tội tàng trữ trái phép chất ma tuý", "score": 0.8, "metadata": {}},
        {"content": "Nghệ sĩ X bị bắt vì sử dụng ma tuý", "score": 0.7, "metadata": {}},
        {"content": "Hình phạt tù từ 2-7 năm cho tội tàng trữ", "score": 0.6, "metadata": {}},
    ]
    results = rerank("hình phạt tàng trữ ma tuý", dummy_candidates, top_k=2)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content']}")
