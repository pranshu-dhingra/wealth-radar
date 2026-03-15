"""Bedrock client wrapper — singleton for all AWS Bedrock interactions.

Model IDs (CLAUDE.md):
  - Nova 2 Lite text/multimodal  : us.amazon.nova-2-lite-v1:0  (cross-region)
  - Nova Multimodal Embeddings   : amazon.nova-2-multimodal-embeddings-v1:0

API patterns:
  - Converse API  → Nova 2 Lite text / multimodal / tool-use / streaming
  - InvokeModel   → Nova Multimodal Embeddings (returns float vector)

Retry: explicit 3-attempt exponential back-off on top of botocore's adaptive retry.
Temperature guidance (CLAUDE.md):
  - 0   → tool calling
  - 0.3 → analysis
  - 0.7 → content generation

Extended thinking budget_tokens mapping:
  - "low"    → 1 024
  - "medium" → 4 096  (recommended for financial document analysis)
  - "high"   → 8 192
"""
from __future__ import annotations

import base64
import json
import logging
import time
from collections.abc import Generator, Callable
from typing import Any, Literal

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model IDs
# ---------------------------------------------------------------------------

NOVA_LITE_MODEL_ID = "us.amazon.nova-2-lite-v1:0"
NOVA_EMBED_MODEL_ID = "amazon.nova-2-multimodal-embeddings-v1:0"

# Extended thinking budget_tokens by level
_THINKING_BUDGET: dict[str, int] = {
    "low":    1_024,
    "medium": 4_096,
    "high":   8_192,
}

# Retryable botocore / boto3 error codes
_RETRYABLE_CODES = frozenset({
    "ThrottlingException",
    "ServiceUnavailableException",
    "ModelTimeoutException",
    "RequestTimeoutException",
    "InternalServerException",
    "TooManyRequestsException",
})


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class BedrockService:
    """Reusable wrapper around the AWS Bedrock Runtime client."""

    def __init__(self) -> None:
        logger.info(
            "Initialising BedrockService (region=%s)", settings.AWS_DEFAULT_REGION
        )
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_DEFAULT_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            # botocore adaptive retry is a safety net; explicit back-off is in each method
            config=Config(retries={"max_attempts": 3, "mode": "adaptive"}),
        )

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _retry(self, fn: Callable, *args, max_attempts: int = 3, **kwargs) -> Any:
        """Call *fn* with exponential back-off on transient errors."""
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                return fn(*args, **kwargs)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in _RETRYABLE_CODES and attempt < max_attempts - 1:
                    wait = 2 ** attempt  # 1 s, 2 s
                    logger.warning(
                        "Bedrock %s (attempt %d/%d) — retrying in %ds",
                        code, attempt + 1, max_attempts, wait,
                    )
                    time.sleep(wait)
                    last_exc = exc
                else:
                    raise
            except (BotoCoreError, Exception) as exc:
                if attempt < max_attempts - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "Bedrock error (attempt %d/%d): %s — retrying in %ds",
                        attempt + 1, max_attempts, exc, wait,
                    )
                    time.sleep(wait)
                    last_exc = exc
                else:
                    raise
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _log_usage(method: str, usage: dict) -> None:
        logger.info(
            "[%s] tokens — input: %d  output: %d  total: %d",
            method,
            usage.get("inputTokens", 0),
            usage.get("outputTokens", 0),
            usage.get("totalTokens", usage.get("inputTokens", 0) + usage.get("outputTokens", 0)),
        )

    @staticmethod
    def _thinking_fields(level: str) -> dict:
        """Build additionalModelRequestFields for extended thinking."""
        budget = _THINKING_BUDGET.get(level)
        if not budget:
            return {}
        return {"thinking": {"type": "enabled", "budget_tokens": budget}}

    # -----------------------------------------------------------------------
    # converse()
    # -----------------------------------------------------------------------

    def converse(
        self,
        messages: list[dict],
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4_096,
        thinking_level: Literal["none", "low", "medium", "high"] = "none",
        model_id: str = NOVA_LITE_MODEL_ID,
    ) -> str:
        """Send messages to Nova 2 Lite via Converse API; return the text response.

        Args:
            messages: Bedrock Converse message list (role/content dicts).
            system: Optional system prompt string.
            temperature: Sampling temperature (0=deterministic, 0.7=creative).
            max_tokens: Maximum output tokens.
            thinking_level: Extended thinking budget ("none"|"low"|"medium"|"high").
            model_id: Bedrock model identifier.

        Returns:
            The assistant's text response.
        """
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": messages,
            "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
        }
        if system:
            kwargs["system"] = [{"text": system}]

        extra = self._thinking_fields(thinking_level) if thinking_level != "none" else {}
        if extra:
            kwargs["additionalModelRequestFields"] = extra
            # Thinking requires temperature=1 on Nova models
            kwargs["inferenceConfig"]["temperature"] = 1.0

        response = self._retry(self._client.converse, **kwargs)
        self._log_usage("converse", response.get("usage", {}))

        # Extract text from the first content block
        content = response["output"]["message"]["content"]
        texts = [block["text"] for block in content if "text" in block]
        return "\n".join(texts)

    # -----------------------------------------------------------------------
    # converse_with_tools()
    # -----------------------------------------------------------------------

    def converse_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_executor: Callable[[str, dict], str],
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4_096,
        model_id: str = NOVA_LITE_MODEL_ID,
        max_tool_rounds: int = 10,
    ) -> tuple[str, list[dict]]:
        """Send messages with tool definitions, run the tool-use loop to completion.

        Args:
            messages: Initial conversation messages.
            tools: List of Bedrock toolSpec dicts.
            tool_executor: Callable(tool_name, tool_input_dict) → result_string.
            system: System prompt.
            temperature: Should be 0 for reliable tool calling.
            max_tokens: Maximum output tokens per round.
            model_id: Bedrock model ID.
            max_tool_rounds: Safety cap on tool-use iterations.

        Returns:
            (final_text, all_tool_calls) where all_tool_calls is a list of
            {"name": str, "input": dict, "result": str} dicts.
        """
        conversation: list[dict] = list(messages)
        all_tool_calls: list[dict] = []
        final_text = ""

        for round_num in range(max_tool_rounds):
            kwargs: dict[str, Any] = {
                "modelId": model_id,
                "messages": conversation,
                "toolConfig": {"tools": [{"toolSpec": t} for t in tools]},
                "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
            }
            if system:
                kwargs["system"] = [{"text": system}]

            response = self._retry(self._client.converse, **kwargs)
            self._log_usage(f"converse_with_tools[round={round_num}]", response.get("usage", {}))

            stop_reason = response.get("stopReason", "end_turn")
            assistant_message = response["output"]["message"]
            conversation.append(assistant_message)

            if stop_reason == "end_turn" or stop_reason == "max_tokens":
                content = assistant_message.get("content", [])
                texts = [b["text"] for b in content if "text" in b]
                final_text = "\n".join(texts)
                break

            if stop_reason == "tool_use":
                content = assistant_message.get("content", [])
                tool_results: list[dict] = []

                for block in content:
                    if "toolUse" not in block:
                        continue
                    use = block["toolUse"]
                    tool_name = use["name"]
                    tool_input = use.get("input", {})
                    tool_use_id = use["toolUseId"]

                    logger.info("[tool_use] calling %s with input=%s", tool_name, tool_input)
                    try:
                        result_str = tool_executor(tool_name, tool_input)
                        status = "success"
                    except Exception as exc:
                        logger.error("Tool %s raised: %s", tool_name, exc)
                        result_str = json.dumps({"error": str(exc)})
                        status = "error"

                    all_tool_calls.append(
                        {"name": tool_name, "input": tool_input, "result": result_str}
                    )
                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_use_id,
                            "content": [{"text": result_str}],
                            "status": status,
                        }
                    })

                conversation.append({"role": "user", "content": tool_results})

        return final_text, all_tool_calls

    # -----------------------------------------------------------------------
    # converse_stream()
    # -----------------------------------------------------------------------

    def converse_stream(
        self,
        messages: list[dict],
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4_096,
        model_id: str = NOVA_LITE_MODEL_ID,
    ) -> Generator[str, None, None]:
        """Stream text chunks from Nova 2 Lite via converse_stream API.

        Yields individual text delta strings. Logs final token counts.

        Usage::
            for chunk in bedrock.converse_stream(messages):
                yield f"data: {chunk}\\n\\n"
        """
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": messages,
            "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
        }
        if system:
            kwargs["system"] = [{"text": system}]

        response = self._retry(self._client.converse_stream, **kwargs)
        stream = response.get("stream", [])

        input_tokens = 0
        output_tokens = 0

        for event in stream:
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    yield delta["text"]

            elif "messageStop" in event:
                pass  # stop reason — no text

            elif "metadata" in event:
                usage = event["metadata"].get("usage", {})
                input_tokens = usage.get("inputTokens", 0)
                output_tokens = usage.get("outputTokens", 0)

        logger.info(
            "[converse_stream] tokens — input: %d  output: %d",
            input_tokens, output_tokens,
        )

    # -----------------------------------------------------------------------
    # analyze_document()
    # -----------------------------------------------------------------------

    def analyze_document(
        self,
        pdf_bytes: bytes,
        prompt: str,
        document_name: str = "document.pdf",
        document_format: str = "pdf",
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4_096,
        thinking_level: Literal["none", "low", "medium", "high"] = "none",
    ) -> str:
        """Send a document to Nova 2 Lite for multimodal analysis via Converse API.

        Uses the Converse API document block format. Supports PDFs and other
        formats accepted by Nova 2 Lite (pdf, csv, doc, docx, xls, xlsx, html,
        txt, md).

        Args:
            pdf_bytes: Raw bytes of the document.
            prompt: Analysis instruction (what to extract).
            document_name: Logical name used by the model for reference.
            document_format: Format string ("pdf", "txt", etc.).
            system: System prompt override.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            thinking_level: Extended thinking level.

        Returns:
            Extracted / analysed text response.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "document": {
                            "format": document_format,
                            "name": document_name,
                            "source": {"bytes": pdf_bytes},
                        }
                    },
                    {"text": prompt},
                ],
            }
        ]
        return self.converse(
            messages=messages,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking_level=thinking_level,
        )

    # -----------------------------------------------------------------------
    # embed_text()
    # -----------------------------------------------------------------------

    def embed_text(self, text: str) -> list[float]:
        """Generate a text embedding via Nova Multimodal Embeddings (InvokeModel).

        Args:
            text: Input text (max ~8 000 tokens for Nova embeddings).

        Returns:
            Float embedding vector.
        """
        body = json.dumps({"inputText": text})
        response = self._retry(
            self._client.invoke_model,
            modelId=NOVA_EMBED_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        embedding: list[float] = result["embedding"]
        logger.info("[embed_text] dim=%d  text_len=%d", len(embedding), len(text))
        return embedding

    # -----------------------------------------------------------------------
    # embed_image()
    # -----------------------------------------------------------------------

    def embed_image(
        self,
        image_bytes: bytes,
        image_format: Literal["jpeg", "png", "gif", "webp"] = "jpeg",
    ) -> list[float]:
        """Generate an image embedding via Nova Multimodal Embeddings (InvokeModel).

        Args:
            image_bytes: Raw image bytes.
            image_format: Image format string ("jpeg", "png", "gif", "webp").

        Returns:
            Float embedding vector.
        """
        b64_str = base64.b64encode(image_bytes).decode("utf-8")
        body = json.dumps({
            "inputImage": {
                "format": image_format,
                "source": {"bytes": b64_str},
            }
        })
        response = self._retry(
            self._client.invoke_model,
            modelId=NOVA_EMBED_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        embedding: list[float] = result["embedding"]
        logger.info("[embed_image] dim=%d  format=%s", len(embedding), image_format)
        return embedding


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: BedrockService | None = None


def get_bedrock_service() -> BedrockService:
    """Return the shared BedrockService singleton (lazy-initialised)."""
    global _service
    if _service is None:
        _service = BedrockService()
    return _service


# ---------------------------------------------------------------------------
# Manual smoke-test  (python -m app.services.bedrock from backend/)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

    # Allow running from the backend/ directory
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    svc = get_bedrock_service()

    # 1. Simple text query
    print("\n=== 1. Simple text query ===")
    text_response = svc.converse(
        messages=[{"role": "user", "content": [{"text": "What is the RMD age under SECURE Act 2.0 for someone born in 1955?"}]}],
        system="You are a financial planning assistant. Answer concisely.",
        temperature=0.3,
    )
    print(text_response)

    # 2. Multimodal query with the Johnson trust PDF
    print("\n=== 2. Multimodal document analysis ===")
    pdf_path = Path(__file__).parent.parent / "data" / "documents" / "johnson_trust.pdf"
    if pdf_path.exists():
        pdf_bytes = pdf_path.read_bytes()
        doc_response = svc.analyze_document(
            pdf_bytes=pdf_bytes,
            prompt=(
                "Extract the following from this trust document as JSON: "
                "trust_type, trustee_names, beneficiary_names, distribution_provisions, "
                "key_dates, any_concerning_provisions."
            ),
            document_name="johnson_trust.pdf",
            thinking_level="medium",
        )
        print(doc_response)
    else:
        print(f"PDF not found at {pdf_path} — skipping multimodal test")

    # 3. Text embedding
    print("\n=== 3. Text embedding ===")
    embedding = svc.embed_text("Required Minimum Distribution from Traditional IRA account")
    print(f"Embedding dim: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")
    print(f"Last  5 values: {embedding[-5:]}")
