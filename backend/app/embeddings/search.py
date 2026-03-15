"""FAISS cross-modal search — query the WealthRadar embedding index.

All vectors are stored L2-normalised so IndexFlatIP returns cosine-similarity
scores in [-1, 1].  Higher = more similar.

Public API:

    search(query_text, top_k=5, client_id=None, type_filter=None)
        → list[SearchResult]

    cross_modal_search(query_text, modality_filter=None, top_k=5)
        → list[SearchResult]

    search_documents(query, client_id=None, top_k=3)
        → list[dict]   # for backward-compat with doc_agent.py

The module maintains a singleton index handle.  Call load() once at startup
(or let it auto-load from DEFAULT_INDEX_DIR on first query).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.embeddings.indexer import DEFAULT_INDEX_DIR, EMBEDDING_DIM, EmbeddingIndexer

logger = logging.getLogger(__name__)

# Valid modality / type filters for cross_modal_search
DOCUMENT_TYPES = frozenset({
    "client_profile",
    "holding",
    "market_event",
    "document_page",
    "action_item",
    "advisor_notes",
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    id: str
    score: float                        # cosine similarity [-1, 1]
    type: str
    client_id: str | None
    source_file: str
    page_num: int | None
    text_preview: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":           self.id,
            "score":        round(self.score, 4),
            "type":         self.type,
            "client_id":    self.client_id,
            "source_file":  self.source_file,
            "page_num":     self.page_num,
            "text_preview": self.text_preview,
        }


# ---------------------------------------------------------------------------
# Singleton index handle
# ---------------------------------------------------------------------------

_indexer: EmbeddingIndexer | None = None


def load(index_dir: str | Path = DEFAULT_INDEX_DIR, use_mock: bool = False) -> None:
    """Explicitly load (or reload) the FAISS index into memory.

    Called automatically on first query if not yet loaded.

    Args:
        index_dir: Directory containing index.faiss + metadata.json.
        use_mock:  Skip Bedrock initialisation (for offline / test use).
    """
    global _indexer
    _indexer = EmbeddingIndexer.load_index(index_dir, use_mock=use_mock)
    logger.info("search: loaded %d vectors from %s", _indexer.total_vectors, index_dir)


def _get_indexer(index_dir: str | Path = DEFAULT_INDEX_DIR) -> EmbeddingIndexer:
    """Return the singleton indexer, auto-loading if necessary."""
    global _indexer
    if _indexer is None:
        try:
            load(index_dir)
        except FileNotFoundError:
            raise RuntimeError(
                f"No FAISS index found at {index_dir}. "
                "Run scripts/index_documents.py first."
            )
    return _indexer


# ---------------------------------------------------------------------------
# Embedding helper (mirrors indexer but without adding to index)
# ---------------------------------------------------------------------------

def _embed_query(text: str, indexer: EmbeddingIndexer) -> np.ndarray:
    """Embed a query string using the same method as the indexer."""
    # Access indexer's internal embed — reuses Bedrock / mock logic
    return indexer._embed(text)


# ---------------------------------------------------------------------------
# Core search function
# ---------------------------------------------------------------------------

def search(
    query_text: str,
    top_k: int = 5,
    client_id: str | None = None,
    type_filter: str | None = None,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
) -> list[SearchResult]:
    """Semantic search over the FAISS index.

    Args:
        query_text:  Natural-language search query.
        top_k:       Maximum number of results to return.
        client_id:   If set, restrict results to this client.
        type_filter: If set, restrict to this record type
                     (e.g. "document_page", "holding", "market_event").
        index_dir:   Where to auto-load the index from if not yet loaded.

    Returns:
        List of SearchResult objects sorted by cosine similarity descending.
    """
    indexer = _get_indexer(index_dir)

    if indexer.total_vectors == 0:
        logger.warning("search: index is empty")
        return []

    query_vec = _embed_query(query_text, indexer)
    query_vec = query_vec.reshape(1, -1).astype(np.float32)

    # When filtering by type or client, scan the full index so small
    # filtered subsets (e.g. 10 document pages in 1 432 vectors) are never missed.
    fetch_k = indexer.total_vectors if (client_id or type_filter) else top_k
    fetch_k = max(fetch_k, top_k)

    scores_arr, indices_arr = indexer._index.search(query_vec, fetch_k)
    scores: list[float] = scores_arr[0].tolist()
    indices: list[int] = indices_arr[0].tolist()

    results: list[SearchResult] = []
    for idx, score in zip(indices, scores):
        if idx < 0 or idx >= len(indexer.metadata):
            continue
        meta = indexer.metadata[idx]

        # Apply filters
        if client_id and meta.get("client_id") != client_id:
            continue
        if type_filter and meta.get("type") != type_filter:
            continue

        results.append(SearchResult(
            id=meta.get("id", str(idx)),
            score=score,
            type=meta.get("type", "unknown"),
            client_id=meta.get("client_id"),
            source_file=meta.get("source_file", ""),
            page_num=meta.get("page_num"),
            text_preview=meta.get("text_preview", ""),
            metadata=meta,
        ))

        if len(results) >= top_k:
            break

    return results


# ---------------------------------------------------------------------------
# Cross-modal search
# ---------------------------------------------------------------------------

def cross_modal_search(
    query_text: str,
    modality_filter: str | None = None,
    top_k: int = 5,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
) -> list[SearchResult]:
    """Search across all record types, optionally filtered to a modality group.

    Modality groups:
      "documents"      → document_page
      "client_data"    → client_profile, action_item, advisor_notes
      "financial"      → holding, market_event
      None / any other → all types

    Args:
        query_text:       Natural-language query.
        modality_filter:  Modality group name or None for all.
        top_k:            Maximum results.
        index_dir:        Index directory.

    Returns:
        List of SearchResult sorted by similarity descending.
    """
    type_map: dict[str, list[str]] = {
        "documents":   ["document_page"],
        "client_data": ["client_profile", "action_item", "advisor_notes"],
        "financial":   ["holding", "market_event"],
    }

    target_types = type_map.get(modality_filter or "", [])

    if not target_types:
        # No filter — search everything
        return search(query_text, top_k=top_k, index_dir=index_dir)

    # Search once with a generous fetch and then filter by allowed types
    indexer = _get_indexer(index_dir)
    if indexer.total_vectors == 0:
        return []

    query_vec = _embed_query(query_text, indexer)
    query_vec = query_vec.reshape(1, -1).astype(np.float32)

    fetch_k = min(top_k * 20, indexer.total_vectors)
    scores_arr, indices_arr = indexer._index.search(query_vec, fetch_k)

    results: list[SearchResult] = []
    for idx, score in zip(indices_arr[0], scores_arr[0]):
        if idx < 0 or idx >= len(indexer.metadata):
            continue
        meta = indexer.metadata[idx]
        if meta.get("type") not in target_types:
            continue

        results.append(SearchResult(
            id=meta.get("id", str(idx)),
            score=score,
            type=meta.get("type", "unknown"),
            client_id=meta.get("client_id"),
            source_file=meta.get("source_file", ""),
            page_num=meta.get("page_num"),
            text_preview=meta.get("text_preview", ""),
            metadata=meta,
        ))
        if len(results) >= top_k:
            break

    return results


# ---------------------------------------------------------------------------
# search_documents — backward-compatible helper used by doc_agent.py
# ---------------------------------------------------------------------------

def search_documents(
    query: str,
    client_id: str | None = None,
    top_k: int = 3,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
) -> list[dict[str, Any]]:
    """Search for document pages relevant to *query*.

    This is the function imported by doc_agent.py.

    Returns:
        List of plain dicts with keys: filename, relevance_score, excerpt.
    """
    results = search(
        query_text=query,
        top_k=top_k,
        client_id=client_id,
        type_filter="document_page",
        index_dir=index_dir,
    )
    return [
        {
            "filename":        r.source_file,
            "relevance_score": round(r.score, 4),
            "excerpt":         r.text_preview,
            "page_num":        r.page_num,
        }
        for r in results
    ]
