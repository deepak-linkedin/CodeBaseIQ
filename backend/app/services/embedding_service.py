
import os
from functools import lru_cache

from google import genai
from google.genai import types

from app.core.config import GEMINI_API_KEY, EMBEDDING_MODEL


EMBEDDING_DIMENSIONS = 768


@lru_cache(maxsize=1)
def get_embedding_client():
    """Create and reuse the Google Gen AI client."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Configure it in the project .env file."
        )

    return genai.Client(api_key=GEMINI_API_KEY)


def _embed(
    texts: list[str],
    task_type: str,
) -> list[list[float]]:
    """Generate normalized embeddings using Google's hosted API."""
    if not texts:
        return []

    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Embedding inputs must be non-empty strings.")

    client = get_embedding_client()

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=[text.strip() for text in texts],
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )

    if not response.embeddings or len(response.embeddings) != len(texts):
        raise RuntimeError(
            "The embedding API returned an unexpected number of vectors."
        )

    normalized_embeddings = []

    for embedding in response.embeddings:
        values = list(embedding.values)

        if len(values) != EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                f"Expected {EMBEDDING_DIMENSIONS} embedding dimensions, "
                f"received {len(values)}."
            )

        # Gemini requires manual normalization when gemini-embedding-001
        # uses a reduced dimensionality.
        magnitude = sum(value * value for value in values) ** 0.5

        if magnitude == 0:
            raise RuntimeError("The embedding API returned a zero vector.")

        normalized_embeddings.append(
            [value / magnitude for value in values]
        )

    return normalized_embeddings


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed code chunks for storage and retrieval."""
    return _embed(texts, "RETRIEVAL_DOCUMENT")


def embed_query(query: str) -> list[float]:
    """Embed a natural-language query for code retrieval."""
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty.")

    return _embed([query.strip()], "CODE_RETRIEVAL_QUERY")[0]
