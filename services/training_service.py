"""Training service — FAQ / knowledge entry management with Chroma ingestion."""

from __future__ import annotations

import hashlib
import logging

from langchain_core.documents import Document

from config import CHROMA_COLLECTION_NAME
from database import add_documents_in_batches, get_vector_store
from models.schemas import TrainingEntry
from repositories import sqlite_repository as repo


logger = logging.getLogger(__name__)

TRAINING_SOURCE_TYPE = "admin_training"


def _training_document_id(entry_id: int) -> str:
    """Deterministic chunk ID for a training entry."""
    raw = f"training_entry|{entry_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def training_to_document(entry: TrainingEntry) -> Document:
    """Convert a training entry into a LangChain Document."""
    content = f"Q: {entry.question}\nA: {entry.answer}"
    metadata = {
        "source": TRAINING_SOURCE_TYPE,
        "source_type": TRAINING_SOURCE_TYPE,
        "document_name": "Admin Training",
        "training_entry_id": entry.id,
        "category": entry.category,
        "tags": entry.tags,
    }
    return Document(page_content=content, metadata=metadata)


def _ingest_training_to_chroma(entry: TrainingEntry) -> None:
    """Add or replace a training entry's chunk in Chroma."""
    store = get_vector_store()
    doc = training_to_document(entry)
    doc_id = _training_document_id(entry.id)

    # Remove existing chunk if present
    try:
        store.delete(ids=[doc_id])
    except Exception:
        pass  # May not exist yet

    add_documents_in_batches(store, [doc], [doc_id], batch_size=1)
    logger.info("Ingested training entry %s into Chroma", entry.id)


def add_training_entry(
    question: str,
    answer: str,
    category: str = "",
    tags: str = "",
) -> TrainingEntry:
    """Create a training entry and ingest it into Chroma."""
    entry = repo.create_training_entry(
        question=question, answer=answer,
        category=category, tags=tags,
    )
    try:
        _ingest_training_to_chroma(entry)
    except Exception:
        logger.exception("Failed to ingest training entry %s into Chroma", entry.id)
    return entry


def update_training_entry(
    entry_id: int,
    question: str = "",
    answer: str = "",
    category: str = "",
    tags: str = "",
) -> None:
    """Update a training entry in SQLite and re-ingest into Chroma."""
    repo.update_training_entry(
        entry_id, question=question, answer=answer,
        category=category, tags=tags,
    )
    entry = repo.get_training_entry(entry_id)
    if entry:
        try:
            _ingest_training_to_chroma(entry)
        except Exception:
            logger.exception("Failed to re-ingest training entry %s", entry_id)


def delete_training_entry(entry_id: int) -> None:
    """Remove a training entry from SQLite and Chroma."""
    # Remove from Chroma first
    try:
        store = get_vector_store()
        doc_id = _training_document_id(entry_id)
        store.delete(ids=[doc_id])
    except Exception:
        logger.warning("Could not delete Chroma chunk for training entry %s", entry_id)

    repo.delete_training_entry(entry_id)
    logger.info("Deleted training entry %s", entry_id)


def reindex_all_training() -> int:
    """Re-ingest all active training entries into Chroma."""
    entries = repo.list_training_entries()
    active = [e for e in entries if e.status == "active"]
    count = 0
    for entry in active:
        try:
            _ingest_training_to_chroma(entry)
            count += 1
        except Exception:
            logger.exception("Failed to reindex training entry %s", entry.id)
    logger.info("Reindexed %s/%s training entries", count, len(active))
    return count


def list_training_entries() -> list[TrainingEntry]:
    return repo.list_training_entries()


def get_training_entry(entry_id: int) -> TrainingEntry | None:
    return repo.get_training_entry(entry_id)
