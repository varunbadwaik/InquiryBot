import hashlib
import logging
import math
from pathlib import Path
from typing import Iterable

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pypdf import PdfReader

from config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PATH,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATA_PATH,
    EMBEDDING_MODEL,
    RETRIEVAL_K,
    SIMILARITY_SCORE_THRESHOLD,
)
from embeddings import get_embeddings


logger = logging.getLogger(__name__)


def get_vector_store(
    embedding_function: Embeddings | None = None,
    persist_directory: Path | str = CHROMA_PATH,
) -> Chroma:
    return Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=embedding_function or get_embeddings(EMBEDDING_MODEL),
        persist_directory=str(persist_directory),
    )


def list_pdf_files(data_path: Path | str = DATA_PATH) -> list[Path]:
    """List all supported files (PDF, TXT, DOCX, MD, CSV, ZIP) under data/."""
    root = Path(data_path)
    if not root.exists():
        return []
    supported_extensions = {".pdf", ".txt", ".docx", ".md", ".csv", ".zip"}
    files = []
    for file_path in root.glob("**/*"):
        if file_path.suffix.lower() in supported_extensions:
            files.append(file_path)
    return sorted(files)


def load_zip_archive(zip_path: Path) -> list[Document]:
    """Safely extract ZIP and recursively load nested supported documents."""
    import zipfile
    import tempfile
    
    documents: list[Document] = []
    zip_name = zip_path.name
    
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        temp_path = Path(temp_dir)
        with zipfile.ZipFile(str(zip_path), "r") as z:
            for member in z.infolist():
                # Zip slip prevention: ensure member filename doesn't escape temp directory
                target_path = (temp_path / member.filename).resolve()
                if not str(target_path).startswith(str(temp_path.resolve())):
                    raise ValueError(f"Malicious ZIP entry detected: {member.filename}")
            
            z.extractall(str(temp_path))
            
        supported_extensions = {".pdf", ".txt", ".docx", ".md", ".csv"}
        extracted_files = []
        for p in temp_path.glob("**/*"):
            if p.is_file() and p.suffix.lower() in supported_extensions:
                extracted_files.append(p)
                
        for file_path in sorted(extracted_files):
            rel_path = file_path.relative_to(temp_path)
            rel_path_str = str(rel_path).replace("\\", "/")
            file_docs = load_pdf_paths([file_path])
            
            for doc in file_docs:
                doc.metadata["parent_document"] = zip_name
                doc.metadata["document_name"] = f"{zip_name} / {rel_path_str}"

                doc.metadata["source"] = str(zip_path)
                
            documents.extend(file_docs)
            
    return documents


def load_pdf_paths(pdf_paths: Iterable[Path | str]) -> list[Document]:
    """Load text content from supported files (PDF, TXT, DOCX, MD, CSV, ZIP)."""
    documents: list[Document] = []
    for pdf_path in pdf_paths:
        path = Path(pdf_path)
        if not path.exists():
            logger.warning("Document path does not exist: %s", path)
            continue
        
        ext = path.suffix.lower()
        try:
            if ext == ".zip":
                documents.extend(load_zip_archive(path))
            elif ext == ".pdf":
                reader = PdfReader(str(path))
                for page_index, page in enumerate(reader.pages, start=1):
                    text = page.extract_text() or ""
                    metadata = {
                        "source": str(path),
                        "document_name": path.name,
                        "parent_document": path.name,
                        "page_number": page_index,
                    }
                    documents.append(Document(page_content=text, metadata=metadata))
            elif ext in (".txt", ".md"):
                text = path.read_text(encoding="utf-8", errors="ignore")
                metadata = {
                    "source": str(path),
                    "document_name": path.name,
                    "parent_document": path.name,
                    "page_number": 1,
                }
                documents.append(Document(page_content=text, metadata=metadata))
            elif ext == ".docx":
                import docx
                doc = docx.Document(str(path))
                paragraphs_text = [p.text for p in doc.paragraphs]
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            paragraphs_text.append(cell.text)
                text = "\n".join(paragraphs_text)
                metadata = {
                    "source": str(path),
                    "document_name": path.name,
                    "parent_document": path.name,
                    "page_number": 1,
                }
                documents.append(Document(page_content=text, metadata=metadata))
            elif ext == ".csv":
                import csv
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.DictReader(f)
                    rows = []
                    for index, row in enumerate(reader, start=1):
                        row_str = ", ".join(f"{k}: {v}" for k, v in row.items())
                        rows.append(f"Row {index}: {row_str}")
                    text = "\n".join(rows)
                metadata = {
                    "source": str(path),
                    "document_name": path.name,
                    "parent_document": path.name,
                    "page_number": 1,
                }
                documents.append(Document(page_content=text, metadata=metadata))
            else:
                logger.warning("Unsupported file extension: %s", ext)
        except Exception:
            logger.exception("Failed to load document %s", path)
            raise
    return documents




def _split_text(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(stripped):
        end = min(start + CHUNK_SIZE, len(stripped))
        chunks.append(stripped[start:end])
        if end == len(stripped):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def split_documents(documents: list[Document]) -> list[Document]:
    chunks: list[Document] = []
    for document in documents:
        for text in _split_text(document.page_content):
            chunks.append(Document(page_content=text, metadata=dict(document.metadata)))

    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = index
    return chunks


def _document_id(doc: Document) -> str:
    source = doc.metadata.get("source", "")
    page = doc.metadata.get("page_number", "")
    chunk_index = doc.metadata.get("chunk_index", "")
    raw = f"{source}|{page}|{chunk_index}|{doc.page_content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def delete_document(vector_store: Chroma, document_name: str) -> None:
    try:
        # Delete by parent_document first (for zip archives or standard docs)
        vector_store.delete(where={"parent_document": document_name})
    except Exception:
        # Fallback to delete by document_name
        try:
            vector_store.delete(where={"document_name": document_name})
        except Exception:
            logger.exception("Failed to delete existing chunks for %s", document_name)
            raise



def add_documents_in_batches(
    store: Chroma,
    chunks: list[Document],
    ids: list[str],
    batch_size: int = 64,
) -> int:
    if len(chunks) != len(ids):
        raise ValueError("Document chunks and ids must have the same length.")

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    inserted_count = 0
    total_chunks = len(chunks)
    for start in range(0, total_chunks, batch_size):
        end = min(start + batch_size, total_chunks)
        batch_chunks = chunks[start:end]
        batch_ids = ids[start:end]
        try:
            store.add_documents(documents=batch_chunks, ids=batch_ids)
        except Exception:
            logger.exception(
                "Failed to insert Chroma batch %s-%s of %s chunks.",
                start + 1,
                end,
                total_chunks,
            )
            raise

        inserted_count += len(batch_chunks)
        logger.info(
            "Inserted Chroma batch %s-%s of %s chunks into %s.",
            start + 1,
            end,
            total_chunks,
            CHROMA_COLLECTION_NAME,
        )

    return inserted_count


def ingest_documents(
    documents: list[Document],
    vector_store: Chroma | None = None,
    replace_existing: bool = True,
) -> int:
    if not documents:
        return 0

    store = vector_store or get_vector_store()
    chunks = split_documents(documents)

    if replace_existing:
        for name in sorted({chunk.metadata.get("document_name") for chunk in chunks}):
            if name:
                delete_document(store, name)

    ids = [_document_id(chunk) for chunk in chunks]
    inserted_count = add_documents_in_batches(store, chunks, ids)
    logger.info("Ingested %s chunks into %s", len(chunks), CHROMA_COLLECTION_NAME)
    return inserted_count


def ingest_pdf_paths(
    pdf_paths: Iterable[Path | str],
    vector_store: Chroma | None = None,
    replace_existing: bool = True,
) -> int:
    documents = load_pdf_paths(pdf_paths)
    return ingest_documents(
        documents=documents,
        vector_store=vector_store,
        replace_existing=replace_existing,
    )


def rebuild_vector_database(
    data_path: Path | str = DATA_PATH,
    persist_directory: Path | str = CHROMA_PATH,
    embedding_function: Embeddings | None = None,
) -> int:
    store = clear_chroma_collection(
        persist_directory=persist_directory,
        embedding_function=embedding_function,
    )
    pdf_paths = list_pdf_files(data_path)
    if not pdf_paths:
        logger.info("Vector database cleared; no PDFs found under %s.", data_path)
        return 0
    return ingest_pdf_paths(pdf_paths, vector_store=store, replace_existing=False)


def clear_chroma_collection(
    persist_directory: Path | str = CHROMA_PATH,
    embedding_function: Embeddings | None = None,
) -> Chroma:
    """Clear the persistent Chroma collection without deleting database files.

    On Windows, Streamlit or Chroma can keep handles open to files under
    chroma_db/. Deleting the collection through the Chroma client avoids rmtree
    file-lock failures while preserving the persistent directory.
    """
    directory = Path(persist_directory)
    directory.mkdir(parents=True, exist_ok=True)

    store = get_vector_store(
        embedding_function=embedding_function,
        persist_directory=directory,
    )
    client = getattr(store, "_client", None)

    try:
        if client is not None:
            client.delete_collection(name=CHROMA_COLLECTION_NAME)
        else:
            store.delete_collection()
        logger.info("Deleted Chroma collection %s.", CHROMA_COLLECTION_NAME)
    except Exception as exc:
        message = str(exc).lower()
        if "does not exist" in message or "not found" in message:
            logger.info(
                "Chroma collection %s did not exist before rebuild.",
                CHROMA_COLLECTION_NAME,
            )
        else:
            logger.exception("Failed to delete Chroma collection %s.", CHROMA_COLLECTION_NAME)
            raise

    return get_vector_store(
        embedding_function=embedding_function,
        persist_directory=directory,
    )


def normalize_relevance_score(raw_score: float | int | None) -> float | None:
    """Validate and clamp a relevance score into Chroma/LangChain's expected range.

    Chroma integrations can return raw distances or relevance values depending on
    the collection metric and wrapper method. Downstream UI code should only see a
    normalized relevance score where 1.0 is best and 0.0 is unusable.
    """
    if raw_score is None:
        logger.warning("Chroma returned a missing relevance score.")
        return None

    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        logger.warning("Chroma returned a non-numeric relevance score: %r", raw_score)
        return None

    if not math.isfinite(score):
        logger.warning("Chroma returned a non-finite relevance score: %r", raw_score)
        return None

    if 0.0 <= score <= 1.0:
        return score

    clamped_score = min(max(score, 0.0), 1.0)
    logger.warning(
        "Chroma returned out-of-range relevance score %.6f; clamped to %.6f.",
        score,
        clamped_score,
    )
    return clamped_score


def distance_to_relevance_score(distance: float | int | None) -> float | None:
    """Convert a raw Chroma distance into a normalized relevance score.

    Chroma's lower-level search returns a distance where smaller is better. This
    monotonic transform keeps scores bounded without relying on LangChain's
    relevance wrapper, which can emit warnings before callers can validate values.
    """
    if distance is None:
        logger.warning("Chroma returned a missing distance score.")
        return None

    try:
        numeric_distance = float(distance)
    except (TypeError, ValueError):
        logger.warning("Chroma returned a non-numeric distance score: %r", distance)
        return None

    if not math.isfinite(numeric_distance):
        logger.warning("Chroma returned a non-finite distance score: %r", distance)
        return None

    if numeric_distance < 0:
        logger.warning(
            "Chroma returned a negative distance score %.6f; treating as exact match.",
            numeric_distance,
        )
        numeric_distance = 0.0

    return normalize_relevance_score(1.0 / (1.0 + numeric_distance))


def retrieve_relevant_documents(
    query: str,
    vector_store: Chroma | None = None,
    k: int = RETRIEVAL_K,
    score_threshold: float = SIMILARITY_SCORE_THRESHOLD,
) -> list[tuple[Document, float]]:
    store = vector_store or get_vector_store()
    try:
        results = store.similarity_search_with_score(query, k=k)
    except Exception:
        logger.exception("Chroma similarity search failed.")
        raise

    normalized_threshold = normalize_relevance_score(score_threshold)
    if normalized_threshold is None:
        logger.warning(
            "Invalid score threshold %r; falling back to configured default 0.0.",
            score_threshold,
        )
        normalized_threshold = 0.0

    filtered: list[tuple[Document, float]] = []
    invalid_scores = 0
    for doc, raw_distance in results:
        score = distance_to_relevance_score(raw_distance)
        if score is None:
            invalid_scores += 1
            continue
        if score >= normalized_threshold:
            filtered.append((doc, score))

    if invalid_scores:
        logger.warning("Skipped %s retrieval result(s) with invalid scores.", invalid_scores)

    logger.info("Retrieved %s/%s chunks for query", len(filtered), len(results))
    return filtered
