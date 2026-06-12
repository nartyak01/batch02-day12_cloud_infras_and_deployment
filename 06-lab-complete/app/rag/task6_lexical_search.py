"""
Task 6 — Lexical Search Module (BM25).
"""

from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from .shared import STANDARDIZED_DIR

CORPUS: list[dict] = []
_BM25_INDEX = None


def _load_corpus() -> list[dict]:
    """Load chunk-level corpus from standardized markdown files."""
    corpus = []
    if not STANDARDIZED_DIR.exists():
        return corpus

    from langchain_text_splitters import RecursiveCharacterTextSplitter

    from .shared import CHUNK_OVERLAP, CHUNK_SIZE

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        doc_type = "legal" if "legal" in md_file.parts else "news"
        for i, chunk_text in enumerate(splitter.split_text(content)):
            if chunk_text.strip():
                corpus.append(
                    {
                        "content": chunk_text,
                        "metadata": {
                            "source": md_file.name,
                            "type": doc_type,
                            "chunk_index": i,
                        },
                    }
                )
    return corpus


def build_bm25_index(corpus: list[dict]):
    """Xây dựng BM25 index từ corpus."""
    tokenized_corpus = [doc["content"].lower().split() for doc in corpus]
    return BM25Okapi(tokenized_corpus)


def _get_bm25():
    global _BM25_INDEX, CORPUS
    if _BM25_INDEX is None:
        CORPUS = _load_corpus()
        if CORPUS:
            _BM25_INDEX = build_bm25_index(CORPUS)
    return _BM25_INDEX


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Tìm kiếm từ khóa sử dụng BM25."""
    bm25 = _get_bm25()
    if bm25 is None or not CORPUS:
        return []

    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        if scores[idx] <= 0:
            continue
        results.append(
            {
                "content": CORPUS[idx]["content"],
                "score": float(scores[idx]),
                "metadata": CORPUS[idx]["metadata"],
            }
        )
    return results


if __name__ == "__main__":
    results = lexical_search("Điều 248 tàng trữ trái phép chất ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
