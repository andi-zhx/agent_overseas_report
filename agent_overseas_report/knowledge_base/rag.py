"""Local RAG embeddings and vector retrieval for parsed knowledge chunks."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class VectorDocument:
    """One vectorized knowledge-base chunk with source-preserving metadata."""

    id: str
    text: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VectorSearchResult:
    """Similarity search result returned by local vector stores."""

    id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class EmbeddingService(ABC):
    """Abstract embedding service used to vectorize knowledge-base chunks."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector for each input text."""

    def embed_text(self, text: str) -> list[float]:
        """Return the embedding vector for a single text input."""

        return self.embed_texts([text])[0]


class HashingEmbeddingService(EmbeddingService):
    """Deterministic local default embedding implementation.

    This implementation avoids external model/network dependencies for local tests
    and deployments. It uses hashed character n-grams with L2 normalization, which
    is sufficient for lightweight semantic-ish recall and can later be swapped for
    an OpenAI/sentence-transformer implementation behind the same abstraction.
    """

    def __init__(self, dimensions: int = 384, ngram_range: tuple[int, int] = (1, 3)) -> None:
        self.dimensions = dimensions
        self.ngram_range = ngram_range

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        normalized = "".join(str(text or "").lower().split())
        vector = [0.0] * self.dimensions
        if not normalized:
            return vector
        min_n, max_n = self.ngram_range
        for ngram_size in range(min_n, max_n + 1):
            if len(normalized) < ngram_size:
                continue
            for index in range(0, len(normalized) - ngram_size + 1):
                token = normalized[index : index + ngram_size]
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                bucket = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


class VectorStore(ABC):
    """Abstract local vector store for upserting and searching chunk vectors."""

    @abstractmethod
    def upsert(self, documents: list[VectorDocument]) -> None:
        """Insert or replace vector documents."""

    @abstractmethod
    def search(
        self, query_vector: list[float], *, top_k: int = 5, filters: dict[str, Any] | None = None
    ) -> list[VectorSearchResult]:
        """Return top matching documents for a query vector and optional metadata filters."""

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """Delete vector documents by id."""


class LocalFAISSVectorStore(VectorStore):
    """Persistent local FAISS vector store with a dependency-free fallback.

    When ``faiss`` is installed, the store builds an in-memory ``IndexFlatIP`` for
    candidate scoring. If FAISS is unavailable, cosine/dot-product scoring is
    performed in pure Python while preserving the same public behavior.
    """

    def __init__(self, index_dir: Path | str) -> None:
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.documents_path = self.index_dir / "documents.json"
        self._documents: dict[str, VectorDocument] = {}
        self._load()

    def upsert(self, documents: list[VectorDocument]) -> None:
        for document in documents:
            self._documents[document.id] = document
        self._persist()

    def search(
        self, query_vector: list[float], *, top_k: int = 5, filters: dict[str, Any] | None = None
    ) -> list[VectorSearchResult]:
        if top_k <= 0 or not self._documents:
            return []
        candidates = [
            document for document in self._documents.values() if _metadata_matches(document.metadata, filters or {})
        ]
        if not candidates:
            return []
        if importlib.util.find_spec("faiss") is not None and importlib.util.find_spec("numpy") is not None:
            return self._search_with_faiss(candidates, query_vector, top_k)
        scored = [
            VectorSearchResult(
                id=document.id, text=document.text, score=_dot(query_vector, document.vector), metadata=document.metadata
            )
            for document in candidates
        ]
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

    def delete(self, ids: list[str]) -> None:
        for document_id in ids:
            self._documents.pop(document_id, None)
        self._persist()

    def _search_with_faiss(
        self, candidates: list[VectorDocument], query_vector: list[float], top_k: int
    ) -> list[VectorSearchResult]:
        faiss = importlib.import_module("faiss")
        np = importlib.import_module("numpy")
        vectors = np.array([document.vector for document in candidates], dtype="float32")
        if vectors.size == 0:
            return []
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        query = np.array([query_vector], dtype="float32")
        scores, indexes = index.search(query, min(top_k, len(candidates)))
        results: list[VectorSearchResult] = []
        for score, candidate_index in zip(scores[0], indexes[0], strict=False):
            if candidate_index < 0:
                continue
            document = candidates[int(candidate_index)]
            results.append(
                VectorSearchResult(id=document.id, text=document.text, score=float(score), metadata=document.metadata)
            )
        return results

    def _load(self) -> None:
        if not self.documents_path.exists():
            return
        payload = json.loads(self.documents_path.read_text(encoding="utf-8"))
        self._documents = {
            item["id"]: VectorDocument(
                id=item["id"],
                text=item["text"],
                vector=[float(value) for value in item["vector"]],
                metadata=item.get("metadata") or {},
            )
            for item in payload.get("documents", [])
        }

    def _persist(self) -> None:
        payload = {
            "documents": [
                {
                    "id": document.id,
                    "text": document.text,
                    "vector": document.vector,
                    "metadata": document.metadata,
                }
                for document in self._documents.values()
            ]
        }
        self.documents_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def build_chunk_vector_document(chunk: dict[str, Any], file_payload: dict[str, Any], vector: list[float]) -> VectorDocument:
    """Convert a parsed chunk and parent file metadata into a vector document."""

    metadata = {
        **(chunk.get("metadata") or {}),
        "chunk_id": chunk["id"],
        "file_id": chunk["file_id"],
        "file_name": file_payload.get("file_name"),
        "page_number": chunk.get("page_number"),
        "sheet_name": chunk.get("sheet_name"),
        "slide_number": chunk.get("slide_number"),
        "enterprise_id": file_payload.get("enterprise_id"),
        "product_id": file_payload.get("product_id"),
        "industry": file_payload.get("industry"),
        "country": file_payload.get("country"),
        "source_type": file_payload.get("source_type"),
    }
    return VectorDocument(id=chunk["id"], text=chunk["text"], vector=vector, metadata=metadata)


def _metadata_matches(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        if expected is None or expected == "":
            continue
        actual = metadata.get(key)
        if actual is None:
            return False
        if _normalize(actual) != _normalize(expected):
            return False
    return True


def _normalize(value: Any) -> str:
    return str(value).strip().casefold()


def _dot(left: list[float], right: list[float]) -> float:
    return float(sum(a * b for a, b in zip(left, right, strict=False)))
