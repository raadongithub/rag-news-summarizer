"""CLI entrypoint for RAG evaluation."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from backend.ai.rag_evaluation import RagasEvaluator
from backend.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SETTINGS = get_settings()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the evaluation runner.

    Returns
    -------
    argparse.Namespace
        Parsed CLI arguments including dataset path and retrieval settings.
    """
    parser = argparse.ArgumentParser(
        description="Evaluate the current RAG pipeline with RAGAs metrics."
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to a JSON or JSONL evaluation dataset.",
    )
    parser.add_argument(
        "--output",
        help="Optional path for the evaluation report JSON.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=SETTINGS.default_top_k,
        help="Number of retrieved passages to evaluate per sample.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=SETTINGS.default_chunk_size,
        help="Number of sentences per retrieval chunk.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=SETTINGS.default_chunk_overlap,
        help="Overlapping sentence count between retrieval chunks.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the evaluation CLI."""
    args = parse_args()

    if not SETTINGS.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is required for RAG evaluation.")
    if not SETTINGS.voyage_api_key:
        raise ValueError("VOYAGE_API_KEY is required for RAG evaluation.")
    if args.k < 1:
        raise ValueError("--k must be at least 1")
    if args.chunk_size < 1:
        raise ValueError("--chunk-size must be at least 1")
    if args.chunk_overlap < 0:
        raise ValueError("--chunk-overlap must be zero or greater")
    if args.chunk_overlap >= args.chunk_size:
        raise ValueError("--chunk-overlap must be smaller than --chunk-size")

    evaluator = RagasEvaluator(
        anthropic_api_key=SETTINGS.anthropic_api_key,
        voyage_api_key=SETTINGS.voyage_api_key,
        retrieval_k=args.k,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    report = evaluator.evaluate_file(args.dataset)
    report_json = report.model_dump(mode="json")

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(report_json, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Evaluation report written to %s", output_path)

    print(json.dumps(report_json, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
