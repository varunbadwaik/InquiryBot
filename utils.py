import logging
import re

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document

from config import DATA_PATH, LEADS_FILE, LOG_FILE


def setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def safe_filename(filename: str) -> str:
    cleaned = Path(filename).name.strip()
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "uploaded.pdf"


def save_uploaded_pdf(uploaded_file) -> Path:
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    target = DATA_PATH / safe_filename(uploaded_file.name)
    target.write_bytes(uploaded_file.getbuffer())
    return target


def document_label(doc: Document) -> str:
    name = doc.metadata.get("document_name") or Path(doc.metadata.get("source", "")).name
    page = doc.metadata.get("page_number") or doc.metadata.get("page")
    if page:
        return f"{name}, page {page}"
    return name or "Unknown document"


def format_documents_for_prompt(docs: Iterable[Document]) -> str:
    blocks = []
    for index, doc in enumerate(docs, start=1):
        blocks.append(
            f"[Source {index}: {document_label(doc)}]\n{doc.page_content.strip()}"
        )
    return "\n\n".join(blocks)


def citation_payload(doc: Document, score: float | None = None) -> dict:
    return {
        "document_name": doc.metadata.get("document_name")
        or Path(doc.metadata.get("source", "")).name
        or "Unknown document",
        "page_number": doc.metadata.get("page_number"),
        "chunk_text": doc.page_content.strip(),
        "score": score,
        "source_type": doc.metadata.get("source_type", "pdf"),
    }


def validate_phone(phone: str) -> bool:
    """Basic phone number validation — at least 7 digits after stripping."""
    digits = re.sub(r"\D", "", phone)
    return len(digits) >= 7
