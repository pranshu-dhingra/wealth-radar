"""Smoke-test for Amazon Bedrock connectivity.

Tests:
1. Nova 2 Lite (Converse API) — sends "Hello, respond with one word."
2. Nova Multimodal Embeddings (InvokeModel) — embeds a short text string and
   prints the embedding dimension.

Usage:
    cd wealth-radar
    python scripts/test_bedrock.py
"""
from __future__ import annotations

import json
import logging
import os
import sys

import boto3
from dotenv import load_dotenv

# Load .env from project root (one level above this script)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model IDs (per CLAUDE.md)
# ---------------------------------------------------------------------------
NOVA_LITE_MODEL = "us.amazon.nova-2-lite-v1:0"          # cross-region inference
NOVA_EMBED_MODEL = "amazon.nova-2-multimodal-embeddings-v1:0"

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


def get_client() -> boto3.client:
    return boto3.client(
        "bedrock-runtime",
        region_name=REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )


# ---------------------------------------------------------------------------
# Test 1 — Nova 2 Lite via Converse API
# ---------------------------------------------------------------------------
def test_nova_lite(client: boto3.client) -> None:
    logger.info("=== Test 1: Nova 2 Lite (Converse API) ===")

    response = client.converse(
        modelId=NOVA_LITE_MODEL,
        messages=[
            {
                "role": "user",
                "content": [{"text": "Hello, respond with one word."}],
            }
        ],
        inferenceConfig={"maxTokens": 16, "temperature": 0},
    )

    output_text: str = response["output"]["message"]["content"][0]["text"]
    input_tokens: int = response["usage"]["inputTokens"]
    output_tokens: int = response["usage"]["outputTokens"]

    logger.info("Response  : %s", output_text.strip())
    logger.info("Tokens    : %d in / %d out", input_tokens, output_tokens)
    print(f"\n[Nova 2 Lite] Response: {output_text.strip()!r}\n")


# ---------------------------------------------------------------------------
# Test 2 — Nova Multimodal Embeddings via InvokeModel
#
# Schema: nova-multimodal-embed-v1
# Response: {"embeddings": [{"embeddingType": "TEXT", "embedding": [...]}]}
# Ref: https://docs.aws.amazon.com/nova/latest/nova2-userguide/embeddings.html
# ---------------------------------------------------------------------------
def test_nova_embeddings(client: boto3.client) -> None:
    logger.info("=== Test 2: Nova Multimodal Embeddings (InvokeModel) ===")

    body = json.dumps(
        {
            "schemaVersion": "nova-multimodal-embed-v1",
            "taskType": "SINGLE_EMBEDDING",
            "singleEmbeddingParams": {
                "embeddingPurpose": "GENERIC_INDEX",
                "embeddingDimension": 1024,
                "text": {
                    "truncationMode": "END",
                    "value": "WealthRadar financial advisor platform",
                },
            },
        }
    )

    response = client.invoke_model(
        modelId=NOVA_EMBED_MODEL,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())
    # Response: {"embeddings": [{"embeddingType": "TEXT", "embedding": [...]}]}
    embedding: list[float] = result["embeddings"][0]["embedding"]
    embedding_type: str = result["embeddings"][0]["embeddingType"]
    logger.info("Embedding type     : %s", embedding_type)
    logger.info("Embedding dimension: %d", len(embedding))
    logger.info("First 5 values     : %s", embedding[:5])
    print(f"[Nova Embeddings] Type={embedding_type}  Dimension={len(embedding)}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    missing = [
        k for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
        if not os.environ.get(k)
    ]
    if missing:
        logger.error("Missing env vars: %s — check your .env file.", missing)
        sys.exit(1)

    client = get_client()

    try:
        test_nova_lite(client)
    except Exception as exc:
        logger.error("Nova 2 Lite test FAILED: %s", exc)

    try:
        test_nova_embeddings(client)
    except Exception as exc:
        logger.error("Nova Embeddings test FAILED: %s", exc)


if __name__ == "__main__":
    main()
