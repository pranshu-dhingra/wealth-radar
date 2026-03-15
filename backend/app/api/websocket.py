"""Real-time bidirectional agent stream via WebSocket.

Connect:  ws://localhost:8000/ws/agent-stream

Send (JSON):
  { "task": "...", "client_id": "CLT001" }

Receive (JSON stream):
  { "type": "thinking"|"tool_call"|"result"|"error", "content": "...",
    "agent": "...", "timestamp": float }

Task routing:
  - contains "analyze" or "scan" + client_id  → analyze_single_client
  - contains "analyze" or "scan" (no id)      → daily_radar_scan(top_n=5)
  - contains "meeting"                         → prepare_meeting
  - anything else                              → orchestrator LLM (free-form)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


def _ws_msg(type_: str, content: Any, agent: str = "orchestrator") -> str:
    return json.dumps({
        "type": type_,
        "content": content if isinstance(content, str) else json.dumps(content, default=str),
        "agent": agent,
        "timestamp": time.time(),
    }, ensure_ascii=False)


async def _run_sync(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


@router.websocket("/ws/agent-stream")
async def agent_stream(websocket: WebSocket) -> None:
    """Bidirectional WebSocket for real-time agent communication."""
    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        while True:
            raw = await websocket.receive_text()

            # Parse incoming message
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(_ws_msg("error", "Invalid JSON — send {task, client_id}"))
                continue

            task: str = (msg.get("task") or "").strip()
            client_id: str = (msg.get("client_id") or "").strip()

            if not task:
                await websocket.send_text(_ws_msg("error", "Missing 'task' field"))
                continue

            await websocket.send_text(_ws_msg("thinking", f"Processing: {task}"))

            try:
                task_lower = task.lower()

                # --- analyze / scan ---
                if any(kw in task_lower for kw in ("analyze", "scan", "trigger")):
                    if client_id:
                        from app.agents.orchestrator import analyze_single_client
                        await websocket.send_text(
                            _ws_msg("tool_call", f"Calling sentinel_scan for {client_id}", "sentinel")
                        )
                        result = await _run_sync(analyze_single_client, client_id)
                        await websocket.send_text(_ws_msg("result", result, "orchestrator"))
                    else:
                        from app.agents.orchestrator import daily_radar_scan
                        await websocket.send_text(
                            _ws_msg("tool_call", "Running daily radar scan (top 5)...", "sentinel")
                        )
                        result = await _run_sync(daily_radar_scan, 5)
                        await websocket.send_text(_ws_msg("result", result, "orchestrator"))

                # --- meeting prep ---
                elif "meeting" in task_lower:
                    if not client_id:
                        await websocket.send_text(
                            _ws_msg("error", "client_id required for meeting prep")
                        )
                        continue
                    from app.agents.orchestrator import prepare_meeting
                    await websocket.send_text(
                        _ws_msg("tool_call", f"Preparing meeting package for {client_id}...", "composer")
                    )
                    result = await _run_sync(prepare_meeting, client_id, False)
                    await websocket.send_text(_ws_msg("result", result, "composer"))

                # --- free-form: delegate to orchestrator LLM ---
                else:
                    from app.agents.orchestrator import _get_orchestrator
                    orch = _get_orchestrator()
                    full_query = task + (f" (Client: {client_id})" if client_id else "")
                    await websocket.send_text(
                        _ws_msg("tool_call", f"Delegating to orchestrator LLM: {task}", "orchestrator")
                    )
                    raw_result = await _run_sync(orch, full_query)
                    result_str = (
                        str(raw_result).encode("utf-8", errors="replace").decode("utf-8")
                    )
                    await websocket.send_text(_ws_msg("result", result_str, "orchestrator"))

            except Exception as exc:
                logger.exception("WebSocket task failed: %s", task)
                await websocket.send_text(_ws_msg("error", str(exc)))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
