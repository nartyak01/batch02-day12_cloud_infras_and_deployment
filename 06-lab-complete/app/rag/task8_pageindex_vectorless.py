"""
Task 8 — PageIndex Vectorless RAG.
"""

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
LANDING_LEGAL_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
DOC_IDS_FILE = Path(__file__).parent.parent / "data" / "pageindex_doc_ids.json"

API_BASE = "https://api.pageindex.ai"


def _load_doc_ids() -> list[str]:
    if DOC_IDS_FILE.exists():
        data = json.loads(DOC_IDS_FILE.read_text(encoding="utf-8"))
        return data.get("doc_ids", [])
    return []


def _save_doc_ids(doc_ids: list[str]):
    DOC_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DOC_IDS_FILE.write_text(
        json.dumps({"doc_ids": doc_ids}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _submit_file(filepath: Path) -> str | None:
    """Submit a document to PageIndex; return doc_id."""
    with open(filepath, "rb") as f:
        response = requests.post(
            f"{API_BASE}/doc/",
            headers={"api_key": PAGEINDEX_API_KEY},
            files={"file": (filepath.name, f)},
            timeout=120,
        )
    if response.status_code not in (200, 201):
        print(f"  ✗ Upload failed {filepath.name}: {response.status_code} {response.text[:200]}")
        return None
    data = response.json()
    return data.get("doc_id")


def _wait_for_completion(doc_id: str, max_wait: int = 300):
    """Poll until document processing completes."""
    for _ in range(max_wait // 5):
        resp = requests.get(
            f"{API_BASE}/doc/{doc_id}/",
            headers={"api_key": PAGEINDEX_API_KEY},
            timeout=30,
        )
        if resp.status_code == 200:
            status = resp.json().get("status", "")
            if status == "completed":
                return True
            if status == "failed":
                return False
        time.sleep(5)
    return False


def upload_documents():
    """Upload documents lên PageIndex (PDF ưu tiên, fallback markdown)."""
    if not PAGEINDEX_API_KEY:
        raise RuntimeError("PAGEINDEX_API_KEY chưa được cấu hình trong .env")

    existing = _load_doc_ids()
    if existing:
        print(f"  ✓ Đã có {len(existing)} doc_ids trong cache")
        return existing

    files_to_upload: list[Path] = []
    if LANDING_LEGAL_DIR.exists():
        files_to_upload.extend(
            sorted(LANDING_LEGAL_DIR.glob("*.pdf"))[:3]
        )
    if not files_to_upload and STANDARDIZED_DIR.exists():
        files_to_upload.extend(sorted(STANDARDIZED_DIR.rglob("*.md"))[:3])

    doc_ids = []
    for filepath in files_to_upload:
        print(f"  Uploading: {filepath.name}")
        doc_id = _submit_file(filepath)
        if doc_id:
            print(f"    doc_id={doc_id}, waiting for processing...")
            if _wait_for_completion(doc_id):
                doc_ids.append(doc_id)
                print(f"    ✓ Completed")
            else:
                print(f"    ✗ Processing failed or timed out")

    if doc_ids:
        _save_doc_ids(doc_ids)
    return doc_ids


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Vectorless retrieval sử dụng PageIndex retrieval API."""
    if not PAGEINDEX_API_KEY:
        return []

    doc_ids = _load_doc_ids()
    if not doc_ids:
        try:
            doc_ids = upload_documents()
        except Exception:
            return []

    if not doc_ids:
        return []

    results = []
    for doc_id in doc_ids[:3]:
        try:
            resp = requests.post(
                f"{API_BASE}/retrieval/",
                headers={"api_key": PAGEINDEX_API_KEY, "Content-Type": "application/json"},
                json={"doc_id": doc_id, "query": query, "thinking": False},
                timeout=60,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            retrieval_id = data.get("retrieval_id")
            if not retrieval_id:
                continue

            # Poll retrieval result
            for _ in range(20):
                r = requests.get(
                    f"{API_BASE}/retrieval/{retrieval_id}/",
                    headers={"api_key": PAGEINDEX_API_KEY},
                    timeout=30,
                )
                if r.status_code != 200:
                    break
                result_data = r.json()
                if result_data.get("status") == "completed":
                    nodes = result_data.get("result", {}).get("nodes", [])
                    for i, node in enumerate(nodes[:top_k]):
                        content = node.get("text", node.get("content", str(node)))
                        results.append(
                            {
                                "content": content,
                                "score": float(1.0 - i * 0.1),
                                "metadata": {"doc_id": doc_id, "node_id": node.get("node_id", "")},
                                "source": "pageindex",
                            }
                        )
                    break
                time.sleep(2)
        except Exception:
            continue

        if len(results) >= top_k:
            break

    # Fallback: use Chat API if retrieval returns nothing
    if not results:
        try:
            from pageindex import PageIndexClient

            client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
            response = client.chat_completions(
                messages=[{"role": "user", "content": query}],
                doc_id=doc_ids[0] if len(doc_ids) == 1 else doc_ids[:2],
            )
            answer = response["choices"][0]["message"]["content"]
            results.append(
                {
                    "content": answer,
                    "score": 0.5,
                    "metadata": {"doc_ids": doc_ids},
                    "source": "pageindex",
                }
            )
        except Exception:
            pass

    return results[:top_k]


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env")
    else:
        print("Uploading documents...")
        upload_documents()

        print("\nTest query:")
        results = pageindex_search("hình phạt sử dụng ma tuý", top_k=3)
        for r in results:
            print(f"[{r['score']:.3f}] {r['content'][:100]}...")
