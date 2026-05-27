import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from database import (
    add_documents_in_batches,
    distance_to_relevance_score,
    get_vector_store,
    ingest_documents,
    normalize_relevance_score,
    retrieve_relevant_documents,
)


class KeywordEmbeddings(Embeddings):
    """Small deterministic embedding model for local retrieval tests."""

    vocabulary = ["isparx", "web", "development", "marketing", "lunch", "soup"]

    def _embed(self, text: str) -> list[float]:
        lower = text.lower()
        return [float(lower.count(term)) for term in self.vocabulary]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class RetrievalTests(unittest.TestCase):
    def test_add_documents_in_batches_limits_insert_size(self) -> None:
        store = MagicMock()
        chunks = [
            Document(page_content=f"chunk {index}", metadata={"chunk_index": index})
            for index in range(150)
        ]
        ids = [str(index) for index in range(150)]

        inserted_count = add_documents_in_batches(
            store,
            chunks,
            ids,
            batch_size=64,
        )

        self.assertEqual(inserted_count, 150)
        self.assertEqual(store.add_documents.call_count, 3)
        batch_sizes = [
            len(call.kwargs["documents"]) for call in store.add_documents.call_args_list
        ]
        self.assertEqual(batch_sizes, [64, 64, 22])

    def test_relevance_scores_are_clamped_to_valid_range(self) -> None:
        self.assertEqual(normalize_relevance_score(-0.25), 0.0)
        self.assertEqual(normalize_relevance_score(1.25), 1.0)
        self.assertEqual(normalize_relevance_score(0.5), 0.5)
        self.assertIsNone(normalize_relevance_score(float("nan")))

    def test_distance_scores_are_normalized_to_valid_range(self) -> None:
        self.assertEqual(distance_to_relevance_score(-5), 1.0)
        self.assertEqual(distance_to_relevance_score(0), 1.0)
        self.assertLess(distance_to_relevance_score(2), 1.0)
        self.assertGreaterEqual(distance_to_relevance_score(2), 0.0)

    def test_ingested_documents_create_vectors(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            store = get_vector_store(
                embedding_function=KeywordEmbeddings(),
                persist_directory=Path(directory) / "chroma",
            )
            documents = [
                Document(
                    page_content=(
                        "iSparx provides web development and digital marketing "
                        "services."
                    ),
                    metadata={
                        "source": "data/iSparx Business profile .pdf",
                        "document_name": "iSparx Business profile .pdf",
                        "page_number": 1,
                    },
                )
            ]

            chunk_count = ingest_documents(documents, vector_store=store)

            self.assertGreaterEqual(chunk_count, 1)
            self.assertEqual(store._collection.count(), chunk_count)

    def test_query_returns_relevant_chunks(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            store = get_vector_store(
                embedding_function=KeywordEmbeddings(),
                persist_directory=Path(directory) / "chroma",
            )
            documents = [
                Document(
                    page_content=(
                        "iSparx provides web development and digital marketing "
                        "services."
                    ),
                    metadata={
                        "source": "data/iSparx Business profile .pdf",
                        "document_name": "iSparx Business profile .pdf",
                        "page_number": 1,
                    },
                ),
                Document(
                    page_content="The office lunch menu includes rice and soup.",
                    metadata={
                        "source": "data/operations.pdf",
                        "document_name": "operations.pdf",
                        "page_number": 2,
                    },
                ),
            ]
            ingest_documents(documents, vector_store=store)

            results = retrieve_relevant_documents(
                "What web development services does iSparx provide?",
                vector_store=store,
                k=1,
                score_threshold=-1.0,
            )

            self.assertTrue(results)
            self.assertTrue(any("iSparx" in doc.page_content for doc, _ in results))
            self.assertTrue(all(0.0 <= score <= 1.0 for _doc, score in results))


if __name__ == "__main__":
    unittest.main()
