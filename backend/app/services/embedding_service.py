
import os
from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import DATA_DIR, EMBEDDING_MODEL

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

# Keep downloaded models inside the project data directory.
os.environ.setdefault(
    "HF_HOME",
    str(DATA_DIR / "huggingface"),
)


@lru_cache(maxsize=1)
def get_embedding_model() -> "SentenceTransformer":
    """
    Load the embedding model once and reuse it.

    The model runs locally after its initial download.
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Convert multiple text chunks into embedding vectors."""
    if not texts:
        return []

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Convert one user's search query into an embedding vector."""
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty.")

    return embed_texts([query.strip()])[0]
