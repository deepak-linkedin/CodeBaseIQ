import os
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import DATA_DIR,EMBEDDING_MODEL

# Keep downloaded models inside the project data directory.
os.environ.setdefault(
    "HF_HOME",
    str(DATA_DIR / "huggingface"),
)

@lru_cache(maxsize=1) # prevents repeatedly loading the model into memory.
def get_embedding_model() -> SentenceTransformer:
    """
    Load the embedding model once and reuse it.

    The model runs locally after its initial download.
    """
    return SentenceTransformer(EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Convert multiple text chunks into embedding vectors."""
    if not texts:
        return []

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        normalize_embeddings=True, # normalizes the vectors, which works well with cosine similarity.
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Convert one user's search query into an embedding vector."""
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty.")

    return embed_texts([query.strip()])[0]
