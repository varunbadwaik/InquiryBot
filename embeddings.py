from functools import lru_cache
import logging
import math

from langchain_core.embeddings import Embeddings

from config import EMBEDDING_MODEL


logger = logging.getLogger(__name__)


class OpenAIEmbeddingFunction(Embeddings):
    def __init__(self, model: str = EMBEDDING_MODEL):
        from openai import OpenAI

        self.model = model
        self.client = OpenAI()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(model=self.model, input=texts)
        vectors = [item.embedding for item in response.data]
        validate_embedding_vectors(vectors)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        response = self.client.embeddings.create(model=self.model, input=text)
        vector = response.data[0].embedding
        validate_embedding_vectors([vector])
        return vector


def validate_embedding_vectors(vectors: list[list[float]]) -> None:
    if not vectors:
        raise ValueError("OpenAI returned no embedding vectors.")

    expected_dimension = len(vectors[0])
    if expected_dimension == 0:
        raise ValueError("OpenAI returned an empty embedding vector.")

    for index, vector in enumerate(vectors):
        if len(vector) != expected_dimension:
            logger.error(
                "Embedding vector %s has dimension %s, expected %s.",
                index,
                len(vector),
                expected_dimension,
            )
            raise ValueError("OpenAI returned inconsistent embedding dimensions.")

        try:
            has_only_finite_values = all(
                math.isfinite(float(value)) for value in vector
            )
        except (TypeError, ValueError):
            has_only_finite_values = False

        if not has_only_finite_values:
            logger.error("Embedding vector %s contains invalid values.", index)
            raise ValueError("OpenAI returned invalid embedding values.")


@lru_cache(maxsize=4)
def get_embeddings(model: str = EMBEDDING_MODEL) -> OpenAIEmbeddingFunction:
    """Return the shared OpenAI embedding client used by ingestion and retrieval."""
    return OpenAIEmbeddingFunction(model=model)
