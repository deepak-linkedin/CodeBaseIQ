
import hashlib
from pathlib import Path

import chromadb

from app.core.config import DATA_DIR
from app.services.embedding_service import embed_query, embed_texts, get_embedding_model


COLLECTION_NAME = "codebase_chunks"


def get_repository_id(repository_path: str) -> str:
    """Generate a stable identifier for a local repository path."""
    resolved_path = str(
        Path(repository_path).expanduser().resolve()
    ).lower()

    return hashlib.sha256(
        resolved_path.encode("utf-8")
    ).hexdigest()[:24]


def get_collection():
    """Open the persistent ChromaDB collection."""
    chroma_path = DATA_DIR / "chroma"
    chroma_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(chroma_path)
    )

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# def index_chunks(
#     repository_path: str,
#     chunks: list[dict],
# ) -> int:
#     """
#     Replace the existing indexed chunks for one repository.

#     Each chunk must contain:
#     chunk_id, file_path, node_type, start_line, end_line, content.
#     """
#     if not chunks:
#         raise ValueError("No code chunks were provided for indexing.")

#     repository_id = get_repository_id(repository_path)
#     collection = get_collection()

#     # Validate required fields before modifying the index.
#     required_fields = {
#         "chunk_id",
#         "file_path",
#         "node_type",
#         "start_line",
#         "end_line",
#         "content",
#     }

#     for chunk in chunks:
#         missing = required_fields - chunk.keys()

#         if missing:
#             raise ValueError(
#                 f"Chunk is missing required fields: {sorted(missing)}"
#             )

#         if not chunk["content"].strip():
#             raise ValueError("A code chunk cannot have empty content.")

#     # Compute vectors before deleting existing data.
#     documents = [chunk["content"] for chunk in chunks]
#     embeddings = embed_texts(documents)

#     ids = []
#     metadatas = []

#     for chunk in chunks:
#         unique_key = (
#             f"{repository_id}:"
#             f"{chunk['chunk_id']}"
#         )

#         chunk_id = hashlib.sha256(
#             unique_key.encode("utf-8")
#         ).hexdigest()

#         ids.append(chunk_id)

#         metadatas.append({
#             "repository_id": repository_id,
#             "file_path": chunk["file_path"],
#             "node_type": chunk["node_type"],
#             "start_line": int(chunk["start_line"]),
#             "end_line": int(chunk["end_line"]),
#         })

#     # Remove stale entries only after embedding succeeds.
#     collection.delete(
#         where={"repository_id": repository_id}
#     )

#     # Add in batches to avoid sending a very large request.
#     batch_size = 100

#     for start in range(0, len(chunks), batch_size):
#         end = start + batch_size

#         collection.add(
#             ids=ids[start:end],
#             documents=documents[start:end],
#             embeddings=embeddings[start:end],
#             metadatas=metadatas[start:end],
#         )

#     return len(chunks)


def index_chunks(
    repository_path: str,
    chunks: list[dict],
    progress_callback=None,
) -> int:
    """
    Replace all indexed chunks for one repository.

    An empty chunk list clears that repository's index.
    Existing data is backed up so a failed replacement can
    attempt to restore the previous index.
    """
    # repository_id = get_repository_id(repository_path)
    # collection = get_collection()
    resolved_path = str(
        Path(repository_path).expanduser().resolve()
    )
    repository_id = get_repository_id(resolved_path)
    repository_name = Path(resolved_path).name or resolved_path

    collection = get_collection()

    required_fields = {
        "chunk_id",
        "file_path",
        "node_type",
        "start_line",
        "end_line",
        "content",
    }

    seen_chunk_ids = set()

    # Validate everything before touching the existing index.
    for chunk in chunks:
        missing = required_fields - chunk.keys()

        if missing:
            raise ValueError(
                f"Chunk is missing required fields: {sorted(missing)}"
            )

        if not isinstance(chunk["content"], str) or not chunk["content"].strip():
            raise ValueError("A code chunk cannot have empty content.")

        if chunk["chunk_id"] in seen_chunk_ids:
            raise ValueError(
                f"Duplicate chunk_id: {chunk['chunk_id']}"
            )

        seen_chunk_ids.add(chunk["chunk_id"])

        try:
            start_line = int(chunk["start_line"])
            end_line = int(chunk["end_line"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Chunk line numbers must be integers."
            ) from exc

        if start_line < 1 or end_line < start_line:
            raise ValueError(
                "Chunk line numbers must be positive and ordered."
            )

    # Prepare new data before modifying the current index. Batch embedding to
    # reduce peak memory and report progress during large repository indexing.
    documents = [chunk["content"] for chunk in chunks]
    embeddings = []
    if progress_callback:
        progress_callback("embedding", "Loading the local embedding model (the first run may download it)…", 58)
    # Load once before embedding so the UI can explain a potentially slow first-run download.
    if documents:
        get_embedding_model()
    if progress_callback:
        progress_callback("embedding", f"Generating embeddings for {len(documents)} code chunks…", 60)
    embedding_batch_size = 8
    for start in range(0, len(documents), embedding_batch_size):
        end = min(start + embedding_batch_size, len(documents))
        embeddings.extend(embed_texts(documents[start:end]))
        if progress_callback:
            progress = 60 + int(25 * end / max(len(documents), 1))
            progress_callback("embedding", f"Embedded {end}/{len(documents)} code chunks…", progress)
    if progress_callback:
        progress_callback("indexing", f"Writing {len(documents)} vectors to ChromaDB…", 87)

    ids = []
    metadatas = []

    # for chunk in chunks:
    #     unique_key = f"{repository_id}:{chunk['chunk_id']}"

    #     vector_id = hashlib.sha256(
    #         unique_key.encode("utf-8")
    #     ).hexdigest()

    #     ids.append(vector_id)

    #     metadatas.append({
    #         "repository_id": repository_id,
    #         "file_path": chunk["file_path"],
    #         "node_type": chunk["node_type"],
    #         "start_line": int(chunk["start_line"]),
    #         "end_line": int(chunk["end_line"]),
    #     })
    for chunk in chunks:
        unique_key = f"{repository_id}:{chunk['chunk_id']}"

        vector_id = hashlib.sha256(
            unique_key.encode("utf-8")
        ).hexdigest()

        ids.append(vector_id)

        metadatas.append({
            "repository_id": repository_id,
            "repository_path": resolved_path,
            "repository_name": repository_name,
            "file_path": chunk["file_path"],
            "node_type": chunk["node_type"],
            "start_line": int(chunk["start_line"]),
            "end_line": int(chunk["end_line"]),
        })

    # Save the previous repository index for rollback.
    previous = collection.get(
        where={"repository_id": repository_id},
        include=["documents", "metadatas", "embeddings"],
    )

    previous_ids = previous["ids"]
    previous_documents = previous["documents"] or []
    previous_metadatas = previous["metadatas"] or []
    previous_embeddings = previous["embeddings"]

    # Delete only this repository's data, then install the new index.
    try:
        collection.delete(where={"repository_id": repository_id})

        batch_size = 100

        for start in range(0, len(chunks), batch_size):
            end = min(start + batch_size, len(chunks))
            collection.add(
                ids=ids[start:end],
                documents=documents[start:end],
                embeddings=embeddings[start:end],
                metadatas=metadatas[start:end],
            )
            if progress_callback:
                progress_callback("indexing", f"Indexed {end}/{len(chunks)} code chunks…", 87 + int(12 * end / max(len(chunks), 1)))

    except Exception as indexing_error:
        # Best-effort rollback: remove any partial replacement
        # and restore the previous records.
        try:
            collection.delete(
                where={"repository_id": repository_id}
            )

            if previous_ids:
                batch_size = 100

                for start in range(0, len(previous_ids), batch_size):
                    end = start + batch_size

                    collection.add(
                        ids=previous_ids[start:end],
                        documents=previous_documents[start:end],
                        embeddings=previous_embeddings[start:end].tolist(),
                        metadatas=previous_metadatas[start:end],
                    )

        except Exception as rollback_error:
            raise RuntimeError(
                "Index replacement failed, and restoring the previous "
                "index also failed. Inspect the ChromaDB collection."
            ) from rollback_error

        raise RuntimeError(
            "Index replacement failed; the previous index was restored."
        ) from indexing_error

    return len(chunks)


def search_code(
    query: str,
    repository_path: str,
    top_k: int = 5,
) -> list[dict]:
    """Find code chunks most relevant to a natural-language query."""
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    collection = get_collection()
    repository_id = get_repository_id(repository_path)

    # matching_count = collection.count(
    #     where={"repository_id": repository_id}
    # )
    all_metadata = collection.get(
        where={"repository_id": repository_id},
        include=["metadatas"],
    )

    matching_count = len(all_metadata["ids"])

    if matching_count == 0:
        return []

    query_embedding = embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, matching_count),
        where={"repository_id": repository_id},
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    matches = []

    for i, document in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i]

        matches.append({
            "content": document,
            "file_path": metadata["file_path"],
            "node_type": metadata["node_type"],
            "start_line": metadata["start_line"],
            "end_line": metadata["end_line"],
            "distance": results["distances"][0][i],
        })

    return matches


def get_repository_stats(repository_id: str) -> dict:
    """Return indexing statistics for one repository ID."""
    collection = get_collection()

    records = collection.get(
        where={"repository_id": repository_id},
        include=["metadatas"],
    )

    metadatas = records["metadatas"] or []
    file_paths = {
        metadata["file_path"]
        for metadata in metadatas
        if metadata.get("file_path")
    }

    return {
        "repository_id": repository_id,
        "chunks_count": len(records["ids"]),
        "files_count": len(file_paths),
    }


# def list_indexed_repositories() -> list[dict]:
#     """List repositories that currently have indexed chunks."""
#     collection = get_collection()

#     records = collection.get(include=["metadatas"])
#     repository_stats = {}

#     for metadata in records["metadatas"] or []:
#         repository_id = metadata.get("repository_id")
#         file_path = metadata.get("file_path")

#         if not repository_id:
#             continue

#         if repository_id not in repository_stats:
#             repository_stats[repository_id] = {
#                 "repository_id": repository_id,
#                 "chunks_count": 0,
#                 "file_paths": set(),
#             }

#         repository_stats[repository_id]["chunks_count"] += 1

#         if file_path:
#             repository_stats[repository_id]["file_paths"].add(file_path)

#     repositories = []

#     for stats in repository_stats.values():
#         repositories.append({
#             "repository_id": stats["repository_id"],
#             "chunks_count": stats["chunks_count"],
#             "files_count": len(stats["file_paths"]),
#         })

#     return sorted(
#         repositories,
#         key=lambda repository: repository["repository_id"],
#     )

def list_indexed_repositories() -> list[dict]:
    """List indexed repositories with display names and paths."""
    collection = get_collection()
    records = collection.get(include=["metadatas"])

    repository_stats = {}

    for metadata in records["metadatas"] or []:
        repository_id = metadata.get("repository_id")
        if not repository_id:
            continue

        stats = repository_stats.setdefault(
            repository_id,
            {
                "repository_id": repository_id,
                "repository_path": metadata.get("repository_path", ""),
                "repository_name": metadata.get("repository_name", ""),
                "chunks_count": 0,
                "file_paths": set(),
            },
        )

        # Fill missing values if this repository has older records.
        if not stats["repository_path"] and metadata.get("repository_path"):
            stats["repository_path"] = metadata["repository_path"]

        if not stats["repository_name"] and metadata.get("repository_name"):
            stats["repository_name"] = metadata["repository_name"]

        stats["chunks_count"] += 1

        file_path = metadata.get("file_path")
        if file_path:
            stats["file_paths"].add(file_path)

    repositories = []

    for stats in repository_stats.values():
        path = stats["repository_path"]
        name = stats["repository_name"]

        # Older Chroma records may not have path/name metadata.
        if not name:
            name = Path(path).name if path else (
                f"Legacy repository {stats['repository_id'][:8]}"
            )

        repositories.append({
            "repository_id": stats["repository_id"],
            "repository_path": path,
            "repository_name": name,
            "chunks_count": stats["chunks_count"],
            "files_count": len(stats["file_paths"]),
        })

    return sorted(
        repositories,
        key=lambda repository: (
            repository["repository_name"].lower(),
            repository["repository_id"],
        ),
    )


def delete_repository_index(repository_id: str) -> int:
    """Delete only the indexed chunks belonging to one repository."""
    collection = get_collection()

    existing = collection.get(
        where={"repository_id": repository_id},
        include=["metadatas"],
    )

    deleted_count = len(existing["ids"])

    if deleted_count:
        collection.delete(
            where={"repository_id": repository_id},
        )

    return deleted_count
