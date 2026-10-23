"""Hybrid code retrieval using semantic search, BM25, and RRF."""

import re
from collections import defaultdict
from typing import Any

from rank_bm25 import BM25Okapi

from app.services.vector_store import (
    get_collection,
    get_repository_id,
    search_code,
)

# def _tokenize(text:str) -> list[str]:
#     """
#     Tokenize natural language and source code.

#     Keep complete identifiers such as calculate_total while also
#     indexing their component words, such as calculate and total.
#     """
#     identifiers = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)
#     tokens: list[str] = []

#     for identifier in identifiers:
#         lowered = identifier.lower()
#         tokens.append(lowered)

#         # Split snake_case identifiers.
#         parts = re.split(r"[_\W]+", lowered)

#         # Also split camelCase and PascalCase identifiers.
#         camel_parts = re.sub(
#             r"([a-z0-9])([A-Z])", r"\1 \2", identifier
#         )
#         parts.extend(camel_parts.lower().split())

#         tokens.extend(part for part in parts if part)

#     return tokens


def _tokenize(text: str) -> list[str]:
    """
    Tokenize natural language and source code.

    Keep complete identifiers such as calculate_total while also
    indexing their component words, such as calculate and total.
    """
    identifiers = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)
    tokens: list[str] = []

    for identifier in identifiers:
        lowered = identifier.lower()
        tokens.append(lowered)

        # Split snake_case identifiers.
        parts = re.split(r"[_\W]+", lowered)

        # Also split camelCase and PascalCase identifiers.
        camel_parts = re.sub(
            r"([a-z0-9])([A-Z])", r"\1 \2", identifier
        )
        parts.extend(camel_parts.lower().split())

        tokens.extend(part for part in parts if part)

    return tokens


def _result_key(result: dict[str, Any]) -> tuple:
    """Build a stable key to deduplicate identical chunks."""

    return(
        result.get("file_path",""),
        result.get("start_line"),
        result.get("end_line"),
        result.get("content",""),
    )

def _get_repository_chunks(repository_path: str) -> list[dict[str, Any]]:
    """Load the complete indexed corpus for one repository."""

    repository_id = get_repository_id(repository_path)
    collection = get_collection()

    stored = collection.get(
        where={"repository_id": repository_id},
        include=["documents","metadatas"],
    )

    ids = stored.get("ids",[])
    documents = stored.get("documents") or []
    metadatas = stored.get("metadatas") or []

    chunks = []

    for index, chunk_id in enumerate(ids):
        if index >= len(documents) or index >= len(metadatas):
            continue

        metadata = metadatas[index] or {}
        content = documents[index]

        if not content or not content.strip():
            continue

        chunks.append(
            {
                "chunk_id": chunk_id,
                "content": content,
                "file_path": metadata.get("file_path", ""),
                "node_type": metadata.get("node_type", "unknown"),
                "start_line": metadata.get("start_line"),
                "end_line": metadata.get("end_line"),
                **{
                    key: value
                    for key, value in metadata.items()
                    if key not in {
                        "file_path",
                        "node_type",
                        "start_line",
                        "end_line",
                    }
                },
            }
        )

    return chunks

def _reciprocal_rank_fusion(
    semantic_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """
    Combine ranked lists using Reciprocal Rank Fusion.

    RRF score = sum(1 / (rrf_k + rank))

    Ranks start at 1. Higher scores indicate stronger combined rankings.
    """
    combined: dict[tuple, dict[str, Any]] = {}
    scores: dict[tuple, float] = defaultdict(float)

    for source, results in (
        ("semantic", semantic_results),
        ("bm25", keyword_results),
    ):
        for rank, result in enumerate(results, start=1):
            key = _result_key(result)

            if key not in combined:
                combined[key] = dict(result)
                combined[key]["semantic_rank"] = None
                combined[key]["bm25_rank"] = None
                combined[key]["semantic_distance"] = None
                combined[key]["bm25_score"] = None

            scores[key] += 1.0 / (rrf_k + rank)

            if source == "semantic":
                combined[key]["semantic_rank"] = rank
                combined[key]["semantic_distance"] = result.get(
                    "distance", result.get("cosine_distance")
                )
            else:
                combined[key]["bm25_rank"] = rank
                combined[key]["bm25_score"] = result.get("bm25_score")

    fused = []

    for key, result in combined.items():
        result["rrf_score"] = scores[key]
        fused.append(result)

    fused.sort(key=lambda item: item["rrf_score"], reverse=True)
    return fused

def hybrid_search(
    query: str,
    repository_path: str,
    top_k: int = 5,
    semantic_k: int | None = None,
    keyword_k: int | None = None,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """
    Retrieve code using semantic search and BM25, then fuse the rankings.

    BM25 searches every indexed chunk belonging to the selected repository.
    Semantic retrieval reuses the existing ChromaDB search implementation.
    """
    if not query or not query.strip():
        raise ValueError("Search query must not be empty.")

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    if rrf_k < 1:
        raise ValueError("rrf_k must be at least 1.")

    semantic_k = semantic_k or max(top_k * 3, 10)
    keyword_k = keyword_k or max(top_k * 3, 10)

    # 1. Semantic retrieval through the existing implementation.
    semantic_results = search_code(
        query=query,
        repository_path=repository_path,
        top_k=semantic_k,
    )

    # 2. Load the full repository corpus for keyword retrieval.
    corpus = _get_repository_chunks(repository_path)

    if not corpus:
        return []

    tokenized_corpus = [
        _tokenize(chunk["content"]) for chunk in corpus
    ]

    # BM25 requires a tokenized corpus and a tokenized query.
    if not any(tokenized_corpus):
        return []

    # bm25 = BM25Okapi(tokenized_corpus)
    # query_tokens = _tokenize(query)

    # if not query_tokens:
    #     return []

    # bm25_scores = bm25.get_scores(query_tokens)

    
    bm25 = BM25Okapi(tokenized_corpus)
    query_tokens = _tokenize(query)

    if not query_tokens:
        return []

    bm25_scores = bm25.get_scores(query_tokens)

    # BM25Okapi can produce zero scores for rare terms in small corpora.
    # If every score is zero, fall back to exact token overlap so that
    # keyword retrieval can still contribute candidates to RRF.
    if not any(float(score) > 0 for score in bm25_scores):
        query_token_set = set(query_tokens)
        bm25_scores = [
            float(len(query_token_set.intersection(set(tokens))))
            for tokens in tokenized_corpus
        ]


    # Stable tie-breaking: original corpus order is preserved.
    ranked_indices = sorted(
        range(len(corpus)),
        key=lambda index: (-float(bm25_scores[index]), index),
    )

    keyword_results = []

    for index in ranked_indices:
        score = float(bm25_scores[index])

        # Stop when all remaining chunks have zero lexical relevance.
        if score <= 0:
            break

        result = dict(corpus[index])
        result["bm25_score"] = score
        keyword_results.append(result)

        if len(keyword_results) >= keyword_k:
            break

    # print("\n--- BM25 DEBUG ---")
    # print("Query tokens:", query_tokens)
    # print("Corpus size:", len(corpus))
    # print("BM25 scores:", [float(score) for score in bm25_scores])
    # print("Keyword candidates:", len(keyword_results))

    for candidate in keyword_results:
        print(
            candidate["file_path"],
            candidate["start_line"],
            candidate.get("bm25_score"),
        )

    # 3. Merge the two rankings and deduplicate matching chunks.
    fused_results = _reciprocal_rank_fusion(
        semantic_results=semantic_results,
        keyword_results=keyword_results,
        rrf_k=rrf_k,
    )

    # Return only the number of results requested by the caller.
    return fused_results[:top_k]
