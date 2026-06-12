"""Shared configuration and utilities for the RAG pipeline."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LANDING_DIR = DATA_DIR / "landing"
STANDARDIZED_DIR = DATA_DIR / "standardized"

# Chunking: 500 chars ~ 1 legal paragraph; 50 overlap preserves cross-chunk context
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

# paraphrase-multilingual-MiniLM-L12-v2: multilingual, lighter than bge-m3, good for Vietnamese
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

VECTOR_STORE = "weaviate"
COLLECTION_NAME = "DrugLawDocs"

PAGEINDEX_DOC_IDS_FILE = DATA_DIR / "pageindex_doc_ids.json"


def get_weaviate_url() -> str:
    url = os.getenv("WEAVIATE_URL", "").strip()
    if url and not url.startswith("http"):
        url = f"https://{url}"
    return url


@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return [emb.tolist() for emb in embeddings]


def get_weaviate_client():
    import weaviate
    from weaviate.classes.init import AdditionalConfig, Auth, Timeout

    url = get_weaviate_url()
    api_key = os.getenv("WEAVIATE_API_KEY", "")
    if not url or not api_key:
        raise RuntimeError("WEAVIATE_URL and WEAVIATE_API_KEY must be set in .env")

    return weaviate.connect_to_weaviate_cloud(
        cluster_url=url,
        auth_credentials=Auth.api_key(api_key),
        skip_init_checks=True,
        additional_config=AdditionalConfig(
            timeout=Timeout(init=30, query=60, insert=120)
        ),
    )
