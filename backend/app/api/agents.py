"""Agent SSE streaming endpoints.

All endpoints return Server-Sent Events (text/event-stream).
Each event is:  data: <json>\n\n
Event types: status | tool_call | result | error | done
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse(data: dict[str, Any]) -> str:
    """Format a single SSE frame."""
    return f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def _run_sync(fn, *args, **kwargs):
    """Run a synchronous function in the default thread-pool executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


# ---------------------------------------------------------------------------
# POST /api/agents/analyze/{client_id}  — full client analysis (SSE)
# ---------------------------------------------------------------------------

@router.post("/analyze/{client_id}")
async def analyze_client(client_id: str) -> StreamingResponse:
    """Stream a full Sentinel analysis for one client.

    Events emitted:
      status  — pipeline progress messages
      result  — analyze_single_client() dict
      done    — stream complete
    """
    async def stream() -> AsyncGenerator[str, None]:
        yield _sse({"type": "status", "agent": "sentinel",
                    "message": f"Starting analysis for {client_id}..."})
        try:
            from app.agents.orchestrator import analyze_single_client
            yield _sse({"type": "status", "agent": "sentinel",
                        "message": "Running trigger scan + financial analyses..."})
            result = await _run_sync(analyze_single_client, client_id)
            if "error" in result and not result.get("client_name"):
                yield _sse({"type": "error", "message": result["error"]})
            else:
                yield _sse({"type": "result", "agent": "orchestrator", "data": result})
        except Exception as exc:
            logger.exception("analyze_client SSE failed for %s", client_id)
            yield _sse({"type": "error", "message": str(exc)})
        yield _sse({"type": "done"})

    return StreamingResponse(stream(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# POST /api/agents/meeting-prep/{client_id}  — meeting package (SSE)
# ---------------------------------------------------------------------------

@router.post("/meeting-prep/{client_id}")
async def meeting_prep(client_id: str) -> StreamingResponse:
    """Stream a complete meeting preparation package for a client.

    Events emitted:
      status  — pipeline step updates (sentinel → doc → scout → composer)
      result  — prepare_meeting() dict (trigger_analysis, meeting_package, etc.)
      done    — stream complete
    """
    async def stream() -> AsyncGenerator[str, None]:
        yield _sse({"type": "status", "agent": "orchestrator",
                    "message": f"Preparing meeting package for {client_id}..."})
        try:
            from app.agents.orchestrator import prepare_meeting

            yield _sse({"type": "status", "agent": "sentinel",
                        "message": "Step 1/4: Scanning triggers + financial analyses..."})

            # Meeting prep calls sentinel, doc, scout, composer internally —
            # use_orchestrator=False to skip the extra LLM call (frontend can show raw data)
            result = await _run_sync(prepare_meeting, client_id, False)

            if "error" in result and not result.get("client_name"):
                yield _sse({"type": "error", "message": result["error"]})
            else:
                yield _sse({"type": "status", "agent": "composer",
                            "message": "Meeting package assembled."})
                yield _sse({"type": "result", "agent": "composer", "data": result})
        except Exception as exc:
            logger.exception("meeting_prep SSE failed for %s", client_id)
            yield _sse({"type": "error", "message": str(exc)})
        yield _sse({"type": "done"})

    return StreamingResponse(stream(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# POST /api/agents/outreach/{client_id}  — outreach email (SSE)
# ---------------------------------------------------------------------------

class OutreachRequest(BaseModel):
    trigger_type: str
    context: str = ""


@router.post("/outreach/{client_id}")
async def generate_outreach(client_id: str, body: OutreachRequest) -> StreamingResponse:
    """Stream a personalized outreach email for a specific trigger.

    Request body:
      trigger_type  (str) — e.g. "RMD_DUE", "TLH_OPPORTUNITY"
      context       (str) — optional extra context, e.g. "RMD of $45,230 due Dec 31"

    Events emitted:
      status  — generating…
      result  — generate_outreach_email() dict (subject, body, tone, disclaimer)
      done    — stream complete
    """
    async def stream() -> AsyncGenerator[str, None]:
        yield _sse({"type": "status", "agent": "composer",
                    "message": f"Generating {body.trigger_type} outreach email for {client_id}..."})
        try:
            from app.agents.composer_agent import generate_outreach_email
            result_json = await _run_sync(
                generate_outreach_email, client_id, body.trigger_type, body.context
            )
            result = json.loads(result_json)
            if "error" in result:
                yield _sse({"type": "error", "message": result["error"]})
            else:
                yield _sse({"type": "result", "agent": "composer", "data": result})
        except Exception as exc:
            logger.exception("outreach SSE failed for %s", client_id)
            yield _sse({"type": "error", "message": str(exc)})
        yield _sse({"type": "done"})

    return StreamingResponse(stream(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# POST /api/agents/daily-scan  — book-wide radar scan (SSE)
# ---------------------------------------------------------------------------

class DailyScanRequest(BaseModel):
    top_n: int = 10


@router.post("/daily-scan")
async def daily_scan(body: DailyScanRequest = DailyScanRequest()) -> StreamingResponse:
    """Stream a daily book-wide radar scan.

    Scans all 50 clients, returns top-N by priority with full analyses.

    Events emitted:
      status  — "Scanning 50 clients…"
      result  — daily_radar_scan() dict (morning_briefing, top_clients, cohort_patterns)
      done    — stream complete
    """
    async def stream() -> AsyncGenerator[str, None]:
        yield _sse({"type": "status", "agent": "sentinel",
                    "message": "Starting daily radar scan across all clients..."})
        try:
            from app.agents.orchestrator import daily_radar_scan

            yield _sse({"type": "status", "agent": "sentinel",
                        "message": "Scanning client portfolios for all 12 trigger types..."})

            result = await _run_sync(daily_radar_scan, body.top_n)

            yield _sse({"type": "status", "agent": "sentinel",
                        "message": result.get("morning_briefing", "Scan complete.")})
            yield _sse({"type": "result", "agent": "orchestrator", "data": result})
        except Exception as exc:
            logger.exception("daily_scan SSE failed")
            yield _sse({"type": "error", "message": str(exc)})
        yield _sse({"type": "done"})

    return StreamingResponse(stream(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
