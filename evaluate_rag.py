import argparse
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from ai.rag_evaluation import RagasEvaluator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the evaluation runner.

    Returns
        argparse.Namespace
            Parsed CLI arguments including dataset path and retrieval settings.

    Raises
        SystemExit
            Raised by `argparse` when the CLI input is invalid.
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
        default=3,
        help="Number of retrieved passages to evaluate per sample.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=3,
        help="Number of sentences per retrieval chunk.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=1,
        help="Overlapping sentence count between retrieval chunks.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the evaluation CLI.

    Parameters
        None

    Returns
        None
            Writes the evaluation report to stdout and optionally to a JSON file.
            Successful execution exits with process code `0`.

    Raises
        ValueError
            Raised when required environment variables or retrieval settings are invalid.
        FileNotFoundError
            Raised when the dataset path does not exist.
        Exception
            Propagates runtime errors from the evaluator, retrieval stack, or model providers.
    """
    args = parse_args()
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    voyage_api_key = os.getenv("VOYAGE_API_KEY")

    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is required for RAG evaluation.")
    if not voyage_api_key:
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
        anthropic_api_key=anthropic_api_key,
        voyage_api_key=voyage_api_key,
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
