"""Build and save the WealthRadar FAISS embedding index.

Run from the project root:
    python scripts/index_documents.py

Or with mock embeddings (no AWS required):
    python scripts/index_documents.py --mock

Steps:
  1. Load all client data, holdings, market events, and PDFs.
  2. Embed each record via Nova Multimodal Embeddings (or mock fallback).
  3. Save index to backend/app/data/embeddings/.
  4. Print index stats (total vectors, by type).
  5. Run 3 test queries and print results.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup (run from project root or scripts/)
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("index_documents")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_section(title: str) -> None:
    width = 64
    print(f"\n{'-' * width}")
    print(f"  {title}")
    print(f"{'-' * width}")


def _print_result(i: int, r) -> None:
    score_str = f"{r.score:+.4f}"
    cid = f"[{r.client_id}]" if r.client_id else "[global]"
    src = r.source_file or "?"
    page = f" p.{r.page_num}" if r.page_num else ""
    print(
        f"  {i+1}. score={score_str}  type={r.type:<16s}  {cid}  "
        f"src={src}{page}"
    )
    preview = r.text_preview[:160].replace("\n", " ")
    print(f"     > {preview}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build WealthRadar FAISS index")
    parser.add_argument(
        "--mock", action="store_true",
        help="Use deterministic mock embeddings instead of Bedrock (no AWS needed)"
    )
    parser.add_argument(
        "--index-dir", default=None,
        help="Output directory (default: backend/app/data/embeddings/)"
    )
    args = parser.parse_args()

    from app.embeddings.indexer import DEFAULT_INDEX_DIR, EmbeddingIndexer
    from app.embeddings.search import cross_modal_search, search

    index_dir = Path(args.index_dir) if args.index_dir else DEFAULT_INDEX_DIR

    # ------------------------------------------------------------------
    # Step 1 + 2: Build index
    # ------------------------------------------------------------------
    _print_section("Step 1 — Building FAISS index")

    mode_label = (
        "MOCK embeddings (deterministic, no AWS)" if args.mock
        else "Bedrock Nova Multimodal Embeddings"
    )
    print(f"  Mode       : {mode_label}")
    print(f"  Output dir : {index_dir}")

    t0 = time.perf_counter()
    indexer = EmbeddingIndexer(use_mock=args.mock)
    counts = indexer.build_full_index()
    elapsed = time.perf_counter() - t0

    # ------------------------------------------------------------------
    # Step 3: Save
    # ------------------------------------------------------------------
    _print_section("Step 2 — Saving index")
    indexer.save_index(index_dir)
    index_faiss = index_dir / "index.faiss"
    meta_json   = index_dir / "metadata.json"
    print(f"  index.faiss  : {index_faiss.stat().st_size / 1024:.1f} KB")
    print(f"  metadata.json: {meta_json.stat().st_size / 1024:.1f} KB")

    # ------------------------------------------------------------------
    # Step 4: Stats
    # ------------------------------------------------------------------
    _print_section("Step 3 — Index statistics")
    total = sum(counts.values())
    print(f"  Total vectors : {total}")
    print(f"  Build time    : {elapsed:.1f}s")
    print()
    col_w = max(len(k) for k in counts) + 2
    for rec_type, count in sorted(counts.items(), key=lambda x: -x[1]):
        bar = "#" * min(count, 40)
        print(f"  {rec_type:<{col_w}} {count:>5}  {bar}")

    # ------------------------------------------------------------------
    # Step 5: Test queries (load from saved index to prove round-trip)
    # ------------------------------------------------------------------
    _print_section("Step 4 — Loading saved index for verification")
    from app.embeddings.indexer import EmbeddingIndexer as _Idx
    loaded = _Idx.load_index(index_dir, use_mock=args.mock)
    print(f"  Loaded {loaded.total_vectors} vectors OK")

    # Patch the singleton so search() uses the just-loaded indexer
    import app.embeddings.search as _search_mod
    _search_mod._indexer = loaded

    _print_section("Step 5 — Test queries")

    queries = [
        {
            "label":  "Query 1: RMD and Required Minimum Distribution",
            "text":   "required minimum distribution IRA retirement account",
            "kwargs": {"top_k": 3},
        },
        {
            "label":  "Query 2: Portfolio drift rebalancing",
            "text":   "portfolio drift rebalancing equity allocation",
            "kwargs": {"top_k": 3},
        },
        {
            "label":  "Query 3: Trust document beneficiary provisions",
            "text":   "trust beneficiary distribution provisions",
            "kwargs": {"top_k": 3, "type_filter": "document_page"},
        },
    ]

    all_ok = True
    for q in queries:
        print(f"\n  {q['label']}")
        print(f"  Query text: \"{q['text']}\"")
        try:
            results = search(q["text"], index_dir=index_dir, **q["kwargs"])
            if results:
                for i, r in enumerate(results):
                    _print_result(i, r)
            else:
                print("  (no results)")
                if q["kwargs"].get("type_filter") == "document_page" and counts["document_page"] == 0:
                    print("  ⚠  No PDFs were indexed (document_page count = 0)")
                else:
                    all_ok = False
        except Exception as exc:
            logger.error("Query failed: %s", exc)
            all_ok = False

    # Cross-modal test
    print(f"\n  Cross-modal: financial holdings / unrealized gains")
    try:
        results = cross_modal_search(
            "unrealized gain loss equity holdings",
            modality_filter="financial",
            top_k=3,
            index_dir=index_dir,
        )
        for i, r in enumerate(results):
            _print_result(i, r)
    except Exception as exc:
        logger.error("Cross-modal query failed: %s", exc)
        all_ok = False

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    _print_section("Summary")
    if all_ok:
        print("  OK  Index built, saved, loaded, and queried successfully.")
    else:
        print("  FAIL  One or more queries returned no results -- check logs.")
    print(f"  Index directory: {index_dir.resolve()}\n")


if __name__ == "__main__":
    main()
