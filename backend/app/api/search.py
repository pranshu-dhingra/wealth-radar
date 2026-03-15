"""Embedding search endpoint.

POST /api/search
  body: { query, client_id?, top_k?, modality? }
  returns: { query, results: [SearchResult...] }
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural-language search query")
    client_id: Optional[str] = Field(None, description="Restrict results to one client")
    top_k: int = Field(5, ge=1, le=50, description="Max results to return")
    modality: Optional[str] = Field(
        None,
        description="Modality filter: 'documents' | 'client_data' | 'financial' | None (all)",
    )


@router.post("")
async def semantic_search(body: SearchRequest) -> dict:
    """Semantic search over the FAISS embedding index.

    Supports cross-modal search across:
      - document_page     (PDF trust docs, account statements)
      - client_profile    (client profiles and advisor notes)
      - holding           (portfolio holdings)
      - market_event      (market events)
      - action_item       (recommended actions)

    Modality shortcuts:
      - "documents"      → document_page only
      - "client_data"    → client_profile, action_item, advisor_notes
      - "financial"      → holding, market_event
      - None / omitted   → all types
    """
    try:
        from app.embeddings.search import search, cross_modal_search
        if body.modality:
            results = cross_modal_search(
                body.query, modality_filter=body.modality, top_k=body.top_k
            )
        else:
            results = search(body.query, top_k=body.top_k, client_id=body.client_id)
        return {
            "query": body.query,
            "client_id": body.client_id,
            "modality": body.modality,
            "total": len(results),
            "results": [r.to_dict() for r in results],
        }
    except RuntimeError as exc:
        # FAISS index not built yet
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
