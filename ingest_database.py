import argparse
import logging
import sys

from dotenv import load_dotenv

from config import DATA_PATH
from database import ingest_pdf_paths, list_pdf_files, rebuild_vector_database
from utils import setup_logging


load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest PDF documents into ChromaDB.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Clear the existing vector database before ingesting all PDFs.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional PDF paths. Defaults to all PDFs under data/.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        if args.rebuild:
            chunk_count = rebuild_vector_database()
            print(f"Rebuilt vector database with {chunk_count} chunks.")
            return 0

        pdf_paths = args.paths or list_pdf_files(DATA_PATH)
        if not pdf_paths:
            print("No PDF files found. Add PDFs to data/ or pass PDF paths.")
            return 1

        chunk_count = ingest_pdf_paths(pdf_paths, replace_existing=True)
        print(f"Ingested {chunk_count} chunks from {len(pdf_paths)} PDF(s).")
        return 0
    except Exception as exc:
        logger.exception("PDF ingestion failed")
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
