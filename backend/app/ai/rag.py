"""
RAG over knowledge_base/*.md (business glossary, model docs, operating
procedures) — section 22. Used for definitional/"how does X work" questions;
factual business-data questions go through app/ai/tools.py instead.

EMBEDDING CHOICE: Chroma's default embedding function is ONNX-based
(onnxruntime). On this project's Windows dev environment, onnxruntime's
native runtime conflicts with xgboost's when both are loaded in the same
process (see docs/decisions.md) — and the backend process needs xgboost for
ML inference. Rather than fight that, we use a small local TF-IDF embedding
(scikit-learn, already a dependency, pure numpy — no native runtime of its
own) fit once over the knowledge base corpus. For a corpus this size (a
handful of short internal documents), TF-IDF retrieval is perfectly
adequate and keeps the whole RAG path dependency-light and fully local
(no embedding API calls). A production system with a much larger corpus
would likely swap this for a hosted embeddings API instead.
"""

import glob
import hashlib
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.core.config import get_settings

settings = get_settings()
# Resolved via settings.project_root (repo root locally, /app in Docker —
# see app/core/config.py), NOT a hardcoded parents[N] path depth, since that
# depth differs between the unpacked repo and Docker's flattened /app layout.
KB_DIR = settings.resolved_knowledge_base_dir
VECTORIZER_PATH = KB_DIR / ".tfidf_vectorizer.joblib"
CHUNK_MAX_CHARS = 800


class TfidfEmbeddingFunction:
    """Satisfies chromadb's EmbeddingFunction protocol: callable, takes a
    list of strings, returns a list of fixed-length float vectors."""

    def __init__(self, vectorizer: TfidfVectorizer):
        self._vectorizer = vectorizer

    def __call__(self, input: list[str]) -> list[list[float]]:
        matrix = self._vectorizer.transform(input)
        return matrix.toarray().astype(float).tolist()

    def name(self) -> str:
        return "tfidf_local_v1"


def _chunk_markdown(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > CHUNK_MAX_CHARS and current:
            chunks.append(current.strip())
            current = ""
        current += para + "\n\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _load_corpus() -> list[tuple[str, str, str]]:
    """Returns (doc_id, source_file, chunk_text) tuples."""
    entries = []
    for path in sorted(glob.glob(str(KB_DIR / "*.md"))):
        text = Path(path).read_text(encoding="utf-8")
        source = Path(path).name
        for i, chunk in enumerate(_chunk_markdown(text)):
            doc_id = hashlib.md5(f"{source}:{i}".encode()).hexdigest()
            entries.append((doc_id, source, chunk))
    return entries


def _get_or_fit_vectorizer(corpus_texts: list[str]) -> TfidfVectorizer:
    if VECTORIZER_PATH.exists():
        vectorizer: TfidfVectorizer = joblib.load(VECTORIZER_PATH)
        try:
            vectorizer.transform(["healthcheck"])
            return vectorizer
        except Exception:
            pass  # fall through and refit if the persisted vectorizer is stale/incompatible
    vectorizer = TfidfVectorizer(max_features=512, stop_words="english")
    vectorizer.fit(corpus_texts)
    VECTORIZER_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(vectorizer, VECTORIZER_PATH)
    return vectorizer


_collection = None


def get_collection():
    global _collection
    if _collection is not None:
        return _collection

    import chromadb

    corpus = _load_corpus()
    texts = [c[2] for c in corpus]
    vectorizer = _get_or_fit_vectorizer(texts)
    embedding_fn = TfidfEmbeddingFunction(vectorizer)

    client = chromadb.PersistentClient(path=str(settings.resolved_vector_db_path))
    collection = client.get_or_create_collection(
        name=settings.vector_db_collection, embedding_function=embedding_fn
    )

    existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()
    new_entries = [c for c in corpus if c[0] not in existing_ids]
    if new_entries:
        collection.upsert(
            ids=[e[0] for e in new_entries],
            documents=[e[2] for e in new_entries],
            metadatas=[{"source": e[1]} for e in new_entries],
        )

    _collection = collection
    return _collection


def retrieve(query: str, k: int = 3) -> list[dict]:
    collection = get_collection()
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[query], n_results=min(k, collection.count()))
    hits = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results.get("distances", [[None]])[0]
    ):
        hits.append({"source": meta.get("source"), "text": doc, "distance": dist})
    return hits
