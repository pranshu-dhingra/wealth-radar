"""Document Intelligence Agent — multimodal financial document analysis.

Uses Nova 2 Lite's multimodal capabilities via Strands Agents SDK to analyse
PDFs and other financial documents stored in data/documents/.

Tools:
  1. analyze_trust_document      — parse trust deeds; extract trustees, beneficiaries, provisions
  2. analyze_account_statement   — parse portfolio statements; extract holdings and metrics
  3. analyze_estate_documents    — unified estate planning status report for a client
  4. search_client_documents     — embedding-based semantic search over a client's documents

Agent:
  - Model      : us.amazon.nova-2-lite-v1:0 via Strands BedrockModel
  - Thinking   : medium (financial document analysis)
  - System     : document analysis specialist with estate-planning domain knowledge
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel

from app.config import settings
from app.services.bedrock import get_bedrock_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DOCUMENTS_DIR = Path(__file__).parent.parent / "data" / "documents"

# Document → client_id mapping (matches generated PDFs)
_DOC_CLIENT_MAP: dict[str, str] = {
    "johnson_trust.pdf":          "CLT001",
    "smith_account_statement.pdf": "CLT002",
    "davis_tax_return_summary.pdf":"CLT005",
    "wilson_insurance_policy.pdf": "CLT013",
    "martinez_estate_plan.pdf":    "CLT040",
}

# Reverse map: client_id → list of document filenames
_CLIENT_DOCS_MAP: dict[str, list[str]] = {}
for _fname, _cid in _DOC_CLIENT_MAP.items():
    _CLIENT_DOCS_MAP.setdefault(_cid, []).append(_fname)


# ---------------------------------------------------------------------------
# Shared analysis prompt helpers
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are the Document Intelligence specialist for WealthRadar,
an AI chief-of-staff system for financial advisors.

Your role is to analyse financial documents — trust deeds, account statements,
tax returns, insurance policies, and estate planning checklists — and extract
structured, actionable data that the advisor can act on immediately.

Rules:
- Always return valid JSON in the requested schema.
- Flag any provisions, gaps, or data points that require advisor attention.
- Use precise financial and legal terminology.
- Never fabricate data not present in the document; use null for missing fields.
- Dates must be in ISO 8601 format (YYYY-MM-DD).
- Dollar amounts as floats without currency symbols."""


def _read_pdf(pdf_path: str) -> bytes | None:
    """Read a PDF from disk; return bytes or None if not found."""
    p = Path(pdf_path)
    if not p.exists():
        # Try relative to documents directory
        p = _DOCUMENTS_DIR / Path(pdf_path).name
    if not p.exists():
        logger.warning("Document not found: %s", pdf_path)
        return None
    return p.read_bytes()


# ---------------------------------------------------------------------------
# Tool 1: analyze_trust_document
# ---------------------------------------------------------------------------

@tool
def analyze_trust_document(pdf_path: str) -> str:
    """Analyse a trust document PDF using Nova 2 Lite multimodal capabilities.

    Reads the PDF, sends it to Nova 2 Lite via the Converse API document block,
    and extracts structured estate-planning data.

    Args:
        pdf_path: Absolute or relative path to the trust PDF file.
                  Relative paths are resolved against the data/documents/ directory.

    Returns:
        JSON string with keys:
          - trust_type: str (e.g. "Revocable Living Trust", "Irrevocable Trust")
          - trust_name: str
          - date_established: str (ISO date or null)
          - grantor_names: list[str]
          - trustee_names: list[str]  (current trustees)
          - successor_trustee_names: list[str]
          - beneficiaries: list[{name, relationship, share_pct, conditions}]
          - distribution_provisions: str  (summary of distribution rules)
          - key_dates: list[{description, date}]
          - amendment_history: list[{amendment_number, date, description}]
          - concerning_provisions: list[str]  (flags for advisor attention)
          - document_currency: str  ("current", "needs_review", "outdated")
          - raw_summary: str  (2-3 sentence plain-English summary)
    """
    pdf_bytes = _read_pdf(pdf_path)
    if pdf_bytes is None:
        return json.dumps({"error": f"File not found: {pdf_path}"})

    svc = get_bedrock_service()
    prompt = (
        "Extract the following from this trust document and return ONLY valid JSON "
        "with these exact keys: trust_type, trust_name, date_established, grantor_names, "
        "trustee_names, successor_trustee_names, beneficiaries (list of objects with "
        "name/relationship/share_pct/conditions), distribution_provisions, "
        "key_dates (list of {description, date}), amendment_history "
        "(list of {amendment_number, date, description}), concerning_provisions "
        "(list of strings — flag anything that needs advisor attention), "
        "document_currency (one of: current/needs_review/outdated), "
        "raw_summary (2-3 plain-English sentences for the advisor)."
    )

    try:
        result = svc.analyze_document(
            pdf_bytes=pdf_bytes,
            prompt=prompt,
            document_name=Path(pdf_path).name,
            thinking_level="medium",
        )
        # Validate it's parseable JSON
        parsed = json.loads(result)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError:
        # Model returned text with markdown fences — strip and retry parse
        cleaned = result.strip()
        for fence in ("```json", "```"):
            if cleaned.startswith(fence):
                cleaned = cleaned[len(fence):]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        try:
            parsed = json.loads(cleaned.strip())
            return json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            return json.dumps({"raw_response": result, "parse_error": "Model returned non-JSON"})
    except Exception as exc:
        logger.error("analyze_trust_document failed: %s", exc)
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool 2: analyze_account_statement
# ---------------------------------------------------------------------------

@tool
def analyze_account_statement(pdf_path: str) -> str:
    """Analyse a portfolio/account statement PDF using Nova 2 Lite multimodal capabilities.

    Reads the PDF and extracts account details, holdings, performance, and fees.

    Args:
        pdf_path: Path to the account statement PDF file.

    Returns:
        JSON string with keys:
          - account_type: str
          - account_number: str (masked)
          - institution: str
          - statement_period: {start_date, end_date}
          - total_value: float
          - holdings: list[{ticker, name, asset_class, quantity, price, value, pct_of_portfolio}]
          - cash_position: float
          - total_fees_ytd: float
          - fee_rate_pct: float
          - performance: {ytd_return_pct, one_year_return_pct, since_inception_return_pct}
          - drift_alerts: list[str]  (any allocation drift warnings in the statement)
          - action_flags: list[str]  (items needing advisor attention)
          - raw_summary: str
    """
    pdf_bytes = _read_pdf(pdf_path)
    if pdf_bytes is None:
        return json.dumps({"error": f"File not found: {pdf_path}"})

    svc = get_bedrock_service()
    prompt = (
        "Extract the following from this account statement and return ONLY valid JSON "
        "with these exact keys: account_type, account_number, institution, "
        "statement_period ({start_date, end_date}), total_value (float), "
        "holdings (list of {ticker, name, asset_class, quantity, price, value, pct_of_portfolio}), "
        "cash_position (float), total_fees_ytd (float), fee_rate_pct (float), "
        "performance ({ytd_return_pct, one_year_return_pct, since_inception_return_pct}), "
        "drift_alerts (list of strings — any allocation warnings), "
        "action_flags (list of strings — items needing advisor attention), "
        "raw_summary (2-3 plain-English sentences)."
    )

    try:
        result = svc.analyze_document(
            pdf_bytes=pdf_bytes,
            prompt=prompt,
            document_name=Path(pdf_path).name,
            thinking_level="low",
        )
        parsed = json.loads(result)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError:
        cleaned = result.strip().strip("```json").strip("```").strip()
        try:
            return json.dumps(json.loads(cleaned), indent=2)
        except json.JSONDecodeError:
            return json.dumps({"raw_response": result})
    except Exception as exc:
        logger.error("analyze_account_statement failed: %s", exc)
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool 3: analyze_estate_documents
# ---------------------------------------------------------------------------

@tool
def analyze_estate_documents(client_id: str) -> str:
    """Generate a unified estate planning status report for a client.

    Loads all PDF documents associated with the client from data/documents/,
    analyses each one, and synthesises a complete estate planning gap analysis.

    Args:
        client_id: Client identifier (e.g. "CLT001"). Must match a client in clients.json.

    Returns:
        JSON string with keys:
          - client_id: str
          - documents_analysed: list[{filename, analysis_summary}]
          - estate_planning_status: str  ("complete", "needs_attention", "critical_gaps")
          - document_inventory: {will, trust, poa, healthcare_directive, insurance_policies}
            each with {found: bool, currency: str, concerns: list[str]}
          - identified_gaps: list[str]  (missing or problematic items)
          - priority_actions: list[{action, urgency, rationale}]
          - overall_summary: str
    """
    docs = _CLIENT_DOCS_MAP.get(client_id, [])
    if not docs:
        return json.dumps({
            "client_id": client_id,
            "error": f"No documents found for client {client_id}",
            "documents_analysed": [],
        })

    svc = get_bedrock_service()
    analyses: list[dict] = []

    for fname in docs:
        fpath = _DOCUMENTS_DIR / fname
        pdf_bytes = _read_pdf(str(fpath))
        if pdf_bytes is None:
            analyses.append({"filename": fname, "error": "File not found"})
            continue

        try:
            summary = svc.analyze_document(
                pdf_bytes=pdf_bytes,
                prompt=(
                    "Provide a concise structured analysis of this document as JSON with keys: "
                    "document_type, key_parties, effective_date, main_provisions_summary, "
                    "concerns (list of strings). Return ONLY valid JSON."
                ),
                document_name=fname,
                thinking_level="low",
            )
            try:
                parsed_summary = json.loads(
                    summary.strip().strip("```json").strip("```").strip()
                )
            except json.JSONDecodeError:
                parsed_summary = {"raw": summary}
            analyses.append({"filename": fname, "analysis": parsed_summary})
        except Exception as exc:
            logger.error("Failed to analyse %s for %s: %s", fname, client_id, exc)
            analyses.append({"filename": fname, "error": str(exc)})

    # Synthesise into unified report
    analyses_text = json.dumps(analyses, indent=2)
    synthesis_prompt = (
        f"Based on these individual document analyses for client {client_id}:\n\n"
        f"{analyses_text}\n\n"
        "Synthesise a unified estate planning status report as JSON with keys: "
        "client_id, documents_analysed (list of {filename, analysis_summary}), "
        "estate_planning_status (one of: complete/needs_attention/critical_gaps), "
        "document_inventory ({will, trust, poa, healthcare_directive, insurance_policies} — "
        "each with {found, currency, concerns}), "
        "identified_gaps (list of strings), "
        "priority_actions (list of {action, urgency, rationale}), "
        "overall_summary (3-4 sentences for the advisor). "
        "Return ONLY valid JSON."
    )

    try:
        synthesis = svc.converse(
            messages=[{"role": "user", "content": [{"text": synthesis_prompt}]}],
            system=_SYSTEM_PROMPT,
            temperature=0.3,
            thinking_level="medium",
        )
        cleaned = synthesis.strip().strip("```json").strip("```").strip()
        result = json.loads(cleaned)
        return json.dumps(result, indent=2)
    except Exception as exc:
        logger.error("Estate document synthesis failed: %s", exc)
        return json.dumps({
            "client_id": client_id,
            "documents_analysed": analyses,
            "synthesis_error": str(exc),
        })


# ---------------------------------------------------------------------------
# Tool 4: search_client_documents
# ---------------------------------------------------------------------------

@tool
def search_client_documents(query: str, client_id: str) -> str:
    """Search a client's documents using semantic (embedding-based) similarity.

    Attempts to use the FAISS embedding index if available. Falls back to
    keyword matching over document filenames when the index is not built.

    Args:
        query: Natural-language search query
               (e.g. "distribution to children after age 25").
        client_id: Restrict search to this client's documents.

    Returns:
        JSON string with keys:
          - query: str
          - client_id: str
          - results: list[{filename, relevance_score, excerpt}]
            (up to 3 results, sorted by relevance descending)
    """
    # Try FAISS-backed search first
    try:
        from app.embeddings.search import search_documents  # type: ignore[import]
        hits = search_documents(query=query, client_id=client_id, top_k=3)
        return json.dumps({"query": query, "client_id": client_id, "results": hits}, indent=2)
    except (ImportError, Exception) as exc:
        logger.debug("Embedding search unavailable (%s) — falling back to keyword match", exc)

    # Fallback: keyword relevance over this client's document filenames
    docs = _CLIENT_DOCS_MAP.get(client_id, [])
    query_lower = query.lower()
    results: list[dict] = []

    for fname in docs:
        fpath = _DOCUMENTS_DIR / fname
        pdf_bytes = _read_pdf(str(fpath))
        if pdf_bytes is None:
            continue

        # Rough relevance: count query term hits in a short text extraction
        try:
            import pypdf  # type: ignore[import]
            import io
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            doc_text = " ".join(
                page.extract_text() or "" for page in reader.pages
            ).lower()
        except Exception:
            doc_text = fname.lower()

        # Score: fraction of query words found in document text
        words = [w for w in query_lower.split() if len(w) > 3]
        if words:
            hits = sum(1 for w in words if w in doc_text)
            score = round(hits / len(words), 3)
        else:
            score = 0.0

        if score > 0:
            # Extract a short excerpt around the first query term hit
            excerpt = ""
            for word in words:
                idx = doc_text.find(word)
                if idx >= 0:
                    start = max(0, idx - 100)
                    end = min(len(doc_text), idx + 300)
                    excerpt = doc_text[start:end].replace("\n", " ").strip()
                    break

            results.append({
                "filename": fname,
                "relevance_score": score,
                "excerpt": excerpt[:400] if excerpt else f"Document: {fname}",
            })

    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return json.dumps(
        {"query": query, "client_id": client_id, "results": results[:3]},
        indent=2,
    )


# ---------------------------------------------------------------------------
# Strands Agent factory
# ---------------------------------------------------------------------------

def create_doc_agent() -> Agent:
    """Create and return the Document Intelligence Strands Agent.

    Returns:
        Configured strands.Agent ready to receive document analysis queries.
    """
    model = BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name=settings.AWS_DEFAULT_REGION,
    )

    return Agent(
        model=model,
        tools=[
            analyze_trust_document,
            analyze_account_statement,
            analyze_estate_documents,
            search_client_documents,
        ],
        system_prompt=_SYSTEM_PROMPT,
    )


# ---------------------------------------------------------------------------
# Manual smoke-test  (python -m app.agents.doc_agent from backend/)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import pprint

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    print("\n=== Document Intelligence Agent — Smoke Test ===\n")
    agent = create_doc_agent()

    # Analyse the Johnson trust document
    print("Analysing johnson_trust.pdf for client CLT001...\n")
    trust_path = str(_DOCUMENTS_DIR / "johnson_trust.pdf")
    response = agent(
        f"Please analyse the trust document at {trust_path} and provide "
        "a full estate planning assessment including trustees, beneficiaries, "
        "distribution provisions, and any concerns."
    )
    print(str(response))

    # Search within client documents
    print("\n--- Searching CLT001 documents for 'distribution to beneficiaries' ---\n")
    search_result = search_client_documents(
        query="distribution to beneficiaries",
        client_id="CLT001",
    )
    pprint.pprint(json.loads(search_result))
