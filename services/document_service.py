"""Document service — Document upload tracking, ingestion, and duplicate detection."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from config import DATA_PATH
from database import (
    delete_document,
    get_vector_store,
    ingest_pdf_paths,
    list_pdf_files,
    rebuild_vector_database,
)
from models.schemas import DocumentRecord
from repositories import sqlite_repository as repo
from utils import safe_filename


logger = logging.getLogger(__name__)


def compute_file_hash(file_path: str | Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_and_track(uploaded_file) -> tuple[DocumentRecord, bool]:
    """Save an uploaded document, compute its hash, and track it.

    Returns (document_record, is_duplicate).
    """
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    
    # Resolve filename
    if hasattr(uploaded_file, "filename") and uploaded_file.filename:
        filename = uploaded_file.filename
    elif hasattr(uploaded_file, "name") and uploaded_file.name:
        filename = uploaded_file.name
    else:
        filename = "uploaded_document.pdf"
        
    target = DATA_PATH / safe_filename(filename)

    # Resolve file content bytes
    if hasattr(uploaded_file, "getbuffer"):
        content_bytes = uploaded_file.getbuffer()
    elif hasattr(uploaded_file, "file") and hasattr(uploaded_file.file, "read"):
        content_bytes = uploaded_file.file.read()
        if hasattr(uploaded_file.file, "seek"):
            uploaded_file.file.seek(0)
    elif hasattr(uploaded_file, "read"):
        content_bytes = uploaded_file.read()
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
    else:
        raise ValueError("Could not read uploaded file content.")

    target.write_bytes(content_bytes)

    file_hash = compute_file_hash(target)
    existing = repo.get_document_by_hash(file_hash)
    if existing is not None:
        return existing, True

    doc = repo.create_document(
        file_name=target.name,
        file_path=str(target),
        file_hash=file_hash,
        status="uploaded",
    )
    return doc, False


def ingest_document(doc_id: int) -> int:
    """Ingest a tracked document into Chroma. Returns chunk count."""
    doc = repo.get_document_by_id(doc_id)
    if doc is None:
        raise ValueError(f"Document {doc_id} not found")

    try:
        repo.update_document_status(doc_id, status="ingesting")
        chunk_count = ingest_pdf_paths([Path(doc.file_path)], replace_existing=True)
        repo.update_document_status(doc_id, status="ingested", chunk_count=chunk_count)
        logger.info("Ingested document %s (%s chunks)", doc.file_name, chunk_count)
        return chunk_count
    except Exception as exc:
        repo.update_document_status(
            doc_id, status="error", error_message=str(exc),
        )
        logger.exception("Failed to ingest document %s", doc.file_name)
        raise


def reingest_document(doc_id: int) -> int:
    """Re-ingest an existing document (clear old chunks, re-embed)."""
    doc = repo.get_document_by_id(doc_id)
    if doc is None:
        raise ValueError(f"Document {doc_id} not found")

    store = get_vector_store()
    try:
        delete_document(store, doc.file_name)
    except Exception:
        logger.warning("Could not delete old chunks for %s", doc.file_name)

    return ingest_document(doc_id)


def delete_tracked_document(doc_id: int) -> None:
    """Remove document from Chroma and SQLite tracking."""
    doc = repo.get_document_by_id(doc_id)
    if doc is None:
        return

    store = get_vector_store()
    try:
        delete_document(store, doc.file_name)
    except Exception:
        logger.warning("Could not delete Chroma chunks for %s", doc.file_name)

    repo.delete_document_record(doc_id)
    logger.info("Deleted document record %s (%s)", doc_id, doc.file_name)


def rebuild_all() -> int:
    """Clear Chroma and re-ingest all PDFs from data/."""
    chunk_count = rebuild_vector_database()
    # Update tracked documents
    for doc in repo.list_documents():
        if Path(doc.file_path).exists():
            try:
                count = ingest_pdf_paths([Path(doc.file_path)], replace_existing=True)
                repo.update_document_status(doc.id, status="ingested", chunk_count=count)
            except Exception as exc:
                repo.update_document_status(
                    doc.id, status="error", error_message=str(exc),
                )
        else:
            repo.update_document_status(
                doc.id, status="error", error_message="File not found on disk",
            )
    return chunk_count


def list_tracked_documents() -> list[DocumentRecord]:
    return repo.list_documents()
