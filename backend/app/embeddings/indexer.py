"""FAISS embedding indexer — builds and persists the vector index.

Uses Nova Multimodal Embeddings (dimension=1024) via InvokeModel.
All vectors are L2-normalised before insertion so that IndexFlatIP
returns cosine-similarity scores in [-1, 1].

Fallback: when Bedrock is unavailable (missing credentials, no network)
the indexer generates deterministic pseudo-embeddings keyed by a hash of
the text.  Semantic similarity does NOT work with the fallback, but the
mechanics of save/load/search remain fully functional and testable.

Index layout on disk  (default: backend/app/data/embeddings/)
  index.faiss   — FAISS binary
  metadata.json — parallel list of metadata dicts

Metadata dict schema:
  {
    "id":           str,          # unique key, e.g. "client:CLT001"
    "type":         str,          # "client_profile"|"holding"|"market_event"
                                  # |"document_page"|"action_item"|"advisor_notes"
    "client_id":    str | null,
    "source_file":  str,          # originating filename
    "page_num":     int | null,   # PDF page number (1-based), else null
    "text_preview": str,          # first 150 chars of the indexed text
  }
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import faiss
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 1024          # Nova Multimodal Embeddings output dimension
_DATA_DIR = Path(__file__).parent.parent / "data"
_DOCS_DIR = _DATA_DIR / "documents"
DEFAULT_INDEX_DIR = _DATA_DIR / "embeddings"


# ---------------------------------------------------------------------------
# Mock embedding (hash-based, deterministic)
# ---------------------------------------------------------------------------

def _mock_embed(text: str) -> np.ndarray:
    """Deterministic pseudo-embedding when Bedrock is unavailable.

    Same text ⟹ same vector (good for exact-match recall).
    Different texts ⟹ independent random vectors (no semantic clustering).
    """
    seed = abs(hash(text)) % (2 ** 31)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


# ---------------------------------------------------------------------------
# EmbeddingIndexer
# ---------------------------------------------------------------------------

class EmbeddingIndexer:
    """Builds and manages the FAISS index for WealthRadar client data.

    Usage::
        indexer = EmbeddingIndexer()
        indexer.index_text("some text", {"type": "note", "client_id": "CLT001", ...})
        indexer.save_index(DEFAULT_INDEX_DIR)

        loaded = EmbeddingIndexer.load_index(DEFAULT_INDEX_DIR)
    """

    def __init__(self, use_mock: bool = False) -> None:
        self._index: faiss.IndexFlatIP = faiss.IndexFlatIP(EMBEDDING_DIM)
        self._metadata: list[dict[str, Any]] = []
        self._use_mock = use_mock
        self._bedrock = None  # lazy — only initialise if needed

        if not use_mock:
            try:
                from app.services.bedrock import get_bedrock_service  # type: ignore[import]
                self._bedrock = get_bedrock_service()
                logger.info("EmbeddingIndexer: using Bedrock Nova Multimodal Embeddings")
            except Exception as exc:
                logger.warning(
                    "Bedrock unavailable (%s) — falling back to mock embeddings", exc
                )
                self._use_mock = True

    # -----------------------------------------------------------------------
    # Core embedding helper
    # -----------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:
        """Return a normalised float32 embedding vector for *text*."""
        if self._use_mock or self._bedrock is None:
            return _mock_embed(text)

        try:
            raw = self._bedrock.embed_text(text[:8_000])  # Nova token limit guard
            vec = np.array(raw, dtype=np.float32)
        except Exception as exc:
            logger.warning("embed_text failed (%s) — using mock for this entry", exc)
            return _mock_embed(text)

        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    # -----------------------------------------------------------------------
    # Public indexing methods
    # -----------------------------------------------------------------------

    def index_text(self, text: str, metadata: dict[str, Any]) -> int:
        """Embed *text* and add it to the FAISS index.

        Args:
            text:     The text to embed.
            metadata: Metadata dict (see module docstring for required keys).
                      Any missing keys are filled with None / "".

        Returns:
            The integer index position (FAISS row number) of the new vector.
        """
        meta = {
            "id":           metadata.get("id", f"entry:{len(self._metadata)}"),
            "type":         metadata.get("type", "unknown"),
            "client_id":    metadata.get("client_id"),
            "source_file":  metadata.get("source_file", ""),
            "page_num":     metadata.get("page_num"),
            "text_preview": text[:150].replace("\n", " "),
        }
        vec = self._embed(text)
        self._index.add(vec.reshape(1, -1))
        self._metadata.append(meta)
        pos = len(self._metadata) - 1
        logger.debug("Indexed [%s] id=%s pos=%d", meta["type"], meta["id"], pos)
        return pos

    def index_document(self, pdf_path: str | Path, client_id: str) -> int:
        """Extract text from each PDF page and index each page separately.

        Args:
            pdf_path:  Path to the PDF file.
            client_id: Client this document belongs to.

        Returns:
            Number of pages successfully indexed.
        """
        import io
        import pypdf  # type: ignore[import]

        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.warning("PDF not found: %s", pdf_path)
            return 0

        pdf_bytes = pdf_path.read_bytes()
        pages_indexed = 0

        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        except Exception as exc:
            logger.error("Failed to read PDF %s: %s", pdf_path.name, exc)
            return 0

        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            page_text = re.sub(r"\s+", " ", page_text).strip()
            if len(page_text) < 20:
                continue

            self.index_text(
                text=page_text,
                metadata={
                    "id":          f"doc:{pdf_path.name}:page{page_num}",
                    "type":        "document_page",
                    "client_id":   client_id,
                    "source_file": pdf_path.name,
                    "page_num":    page_num,
                },
            )
            pages_indexed += 1

        logger.info("Indexed %d pages from %s (client=%s)", pages_indexed, pdf_path.name, client_id)
        return pages_indexed

    def index_client_notes(self, client_id: str, notes_text: str) -> int:
        """Embed and index meeting notes, action items, or advisor commentary.

        Args:
            client_id:  Client identifier.
            notes_text: The text content to index.

        Returns:
            The FAISS row position of the new vector.
        """
        return self.index_text(
            text=notes_text,
            metadata={
                "id":          f"notes:{client_id}:{len(self._metadata)}",
                "type":        "advisor_notes",
                "client_id":   client_id,
                "source_file": "clients.json",
                "page_num":    None,
            },
        )

    def build_full_index(self) -> dict[str, int]:
        """Index all client data, holdings, market events, and PDFs.

        Reads from the standard data/ directory:
          - data/clients.json       → client_profile, action_item, advisor_notes
          - data/holdings.json      → holding
          - data/market_events.json → market_event
          - data/documents/*.pdf    → document_page

        Returns:
            Dict mapping record type → count of vectors added.
        """
        counts: dict[str, int] = {
            "client_profile": 0,
            "holding": 0,
            "market_event": 0,
            "document_page": 0,
            "action_item": 0,
            "advisor_notes": 0,
        }

        # -- clients.json -------------------------------------------------------
        clients_file = _DATA_DIR / "clients.json"
        if clients_file.exists():
            clients: list[dict] = json.loads(clients_file.read_text(encoding="utf-8"))
            logger.info("Indexing %d clients…", len(clients))

            for c in clients:
                cid = c["id"]
                tier = c.get("tier", "?")
                aum = c.get("aum", 0)
                age = c.get("age", "?")
                name = c.get("name", "Unknown")
                occupation = c.get("occupation", "")
                tax_bracket = c.get("tax_bracket", "")
                risk = c.get("risk_tolerance", "")

                # Trigger flags
                flags: list[str] = []
                if c.get("rmd_eligible"):
                    flags.append("RMD eligible")
                if c.get("rmd_overdue"):
                    flags.append("RMD overdue 2026")
                if c.get("qcd_eligible"):
                    flags.append("QCD eligible")
                if c.get("roth_conversion_candidate"):
                    flags.append("Roth conversion candidate")
                if c.get("has_portfolio_drift"):
                    flags.append("portfolio drift >5%")
                if c.get("tax_loss_harvesting_opportunity"):
                    flags.append("TLH opportunity")
                if c.get("has_recent_life_event"):
                    flags.append("recent life event")

                # Life events
                life_events_text = "; ".join(
                    f"{e.get('type','event')} on {e.get('date','?')}"
                    for e in c.get("life_events", [])
                )

                profile_text = (
                    f"Client {name} (ID: {cid}), Tier {tier}, age {age}, "
                    f"AUM ${aum:,.0f}, {occupation}. "
                    f"Tax bracket: {tax_bracket}, risk tolerance: {risk}. "
                    f"Flags: {', '.join(flags) if flags else 'none'}. "
                    f"Life events: {life_events_text or 'none'}."
                )

                self.index_text(
                    profile_text,
                    {"id": f"client:{cid}", "type": "client_profile",
                     "client_id": cid, "source_file": "clients.json"},
                )
                counts["client_profile"] += 1

                # Advisor notes
                notes = c.get("advisor_notes", "").strip()
                if notes:
                    self.index_client_notes(cid, f"{name}: {notes}")
                    counts["advisor_notes"] += 1

                # Open action items
                for item in c.get("open_action_items", []):
                    item_text = (
                        f"Action item for {name} (client {cid}): "
                        f"[{item.get('priority','?').upper()}] {item.get('description','')}. "
                        f"Category: {item.get('category','')}. "
                        f"Due: {item.get('due_date','?')}."
                    )
                    self.index_text(
                        item_text,
                        {"id": f"action:{cid}:{item.get('id','?')}", "type": "action_item",
                         "client_id": cid, "source_file": "clients.json"},
                    )
                    counts["action_item"] += 1

        # -- holdings.json ------------------------------------------------------
        holdings_file = _DATA_DIR / "holdings.json"
        if holdings_file.exists():
            holdings: list[dict] = json.loads(holdings_file.read_text(encoding="utf-8"))
            logger.info("Indexing %d holdings…", len(holdings))

            for h in holdings:
                cid = h.get("client_id", "")
                holding_text = (
                    f"{h.get('ticker','')} — {h.get('name','')} "
                    f"({h.get('asset_class','')}) in {h.get('account_type','')} "
                    f"for client {cid}. "
                    f"Value: ${h.get('current_value',0):,.2f}, "
                    f"shares: {h.get('shares',0):.4f}, "
                    f"unrealised P&L: ${h.get('unrealized_gain_loss',0):,.2f}. "
                    f"Wash-sale flag: {h.get('wash_sale_flag', False)}."
                )
                self.index_text(
                    holding_text,
                    {"id": f"holding:{cid}:{h.get('ticker','?')}:{h.get('account_id','?')}",
                     "type": "holding", "client_id": cid, "source_file": "holdings.json"},
                )
                counts["holding"] += 1

        # -- market_events.json -------------------------------------------------
        events_file = _DATA_DIR / "market_events.json"
        if events_file.exists():
            events: list[dict] = json.loads(events_file.read_text(encoding="utf-8"))
            logger.info("Indexing %d market events…", len(events))

            for ev in events:
                event_text = (
                    f"Market event [{ev.get('id','')}] on {ev.get('date','')}: "
                    f"{ev.get('title','')}. {ev.get('description','')} "
                    f"Severity: {ev.get('severity','')}. "
                    f"Affected sectors: {', '.join(ev.get('affected_sectors',[]))}. "
                    f"Recommended action: {ev.get('recommended_action','')}."
                )
                self.index_text(
                    event_text,
                    {"id": f"event:{ev.get('id','?')}", "type": "market_event",
                     "client_id": None, "source_file": "market_events.json"},
                )
                counts["market_event"] += 1

        # -- PDF documents ------------------------------------------------------
        doc_client_map: dict[str, str] = {
            "johnson_trust.pdf":           "CLT001",
            "smith_account_statement.pdf": "CLT002",
            "davis_tax_return_summary.pdf":"CLT005",
            "wilson_insurance_policy.pdf": "CLT013",
            "martinez_estate_plan.pdf":    "CLT040",
        }

        for fname, cid in doc_client_map.items():
            fpath = _DOCS_DIR / fname
            if fpath.exists():
                pages = self.index_document(fpath, cid)
                counts["document_page"] += pages
            else:
                logger.warning("PDF not found, skipping: %s", fname)

        total = sum(counts.values())
        logger.info(
            "build_full_index complete — %d vectors total: %s",
            total, counts,
        )
        return counts

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    def save_index(self, path: str | Path) -> None:
        """Save FAISS index and metadata to *path* directory.

        Creates the directory if it does not exist.
        Writes:
          {path}/index.faiss
          {path}/metadata.json
        """
        out = Path(path)
        out.mkdir(parents=True, exist_ok=True)

        faiss_path = out / "index.faiss"
        meta_path  = out / "metadata.json"

        faiss.write_index(self._index, str(faiss_path))
        meta_path.write_text(json.dumps(self._metadata, indent=2), encoding="utf-8")

        logger.info(
            "Saved index: %d vectors → %s  |  metadata → %s",
            self._index.ntotal, faiss_path, meta_path,
        )

    @classmethod
    def load_index(cls, path: str | Path, use_mock: bool = False) -> "EmbeddingIndexer":
        """Load a previously saved index from *path* directory.

        Args:
            path:     Directory containing index.faiss and metadata.json.
            use_mock: If True, skip Bedrock initialisation (for offline use).

        Returns:
            A fully populated EmbeddingIndexer ready for search.
        """
        src = Path(path)
        faiss_path = src / "index.faiss"
        meta_path  = src / "metadata.json"

        if not faiss_path.exists():
            raise FileNotFoundError(f"FAISS index not found: {faiss_path}")
        if not meta_path.exists():
            raise FileNotFoundError(f"Metadata not found: {meta_path}")

        indexer = cls.__new__(cls)
        indexer._index = faiss.read_index(str(faiss_path))
        indexer._metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        indexer._use_mock = use_mock
        indexer._bedrock = None

        if not use_mock:
            try:
                from app.services.bedrock import get_bedrock_service  # type: ignore[import]
                indexer._bedrock = get_bedrock_service()
            except Exception:
                indexer._use_mock = True

        logger.info(
            "Loaded index: %d vectors from %s", indexer._index.ntotal, src
        )
        return indexer

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def total_vectors(self) -> int:
        return self._index.ntotal

    @property
    def metadata(self) -> list[dict[str, Any]]:
        return self._metadata
