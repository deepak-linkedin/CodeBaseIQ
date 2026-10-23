
from pathlib import Path
from typing import Callable

from app.services.chunker import chunk_source_file
from app.services.repository_loader import discover_source_files
from app.services.vector_store import index_chunks


def ingest_repository(repository_path: str, preserve_index_on_empty: bool = False, progress_callback: Callable[[str, str, int], None] | None = None) -> dict:
    """
    Discover files, parse them into code chunks, and index them.
    """
    root = Path(repository_path).expanduser().resolve()

    if not root.exists() or not root.is_dir():
        raise ValueError("Please provide a valid repository directory.")

    source_files = discover_source_files(str(root))
    if progress_callback:
        progress_callback("parsing", f"Found {len(source_files)} supported source files. Parsing code…", 42)
    all_chunks = []
    files_with_errors = []

    for file_index, relative_path in enumerate(source_files, start=1):
        try:
            file_chunks = chunk_source_file(
                str(root),
                relative_path,
            )
            all_chunks.extend(file_chunks)
            if progress_callback and (file_index == len(source_files) or file_index % 10 == 0):
                parse_progress = 42 if not source_files else 42 + int(13 * file_index / len(source_files))
                progress_callback("parsing", f"Parsed {file_index}/{len(source_files)} source files…", parse_progress)
        except (OSError, UnicodeError, ValueError) as exc:
            files_with_errors.append({
                "file_path": relative_path.as_posix(),
                "error": str(exc),
            })

    # if not all_chunks:
    #     return {
    #         "repository_path": str(root),
    #         "files_discovered": len(source_files),
    #         "files_processed": 0,
    #         "chunks_created": 0,
    #         "chunks_indexed": 0,
    #         "files_with_errors": files_with_errors,
    #         "message": "No indexable source chunks were found.",
    #     }

    # if not all_chunks and files_with_errors:
    #     return {
    #         "repository_path": str(root),
    #         "files_discovered": len(source_files),
    #         "files_processed": len(source_files) - len(files_with_errors),
    #         "chunks_created": 0,
    #         "chunks_indexed": 0,
    #         "files_with_errors": files_with_errors,
    #         "message": (
    #             "Index unchanged because source files could not be "
    #             "processed successfully."
    #         ),
    #     }

    if files_with_errors:
        return {
            "repository_path": str(root),
            "files_discovered": len(source_files),
            "files_processed": len(source_files) - len(files_with_errors),
            "chunks_created": len(all_chunks),
            "chunks_indexed": 0,
            "files_with_errors": files_with_errors,
            "message": (
                "Index unchanged because one or more source files "
                "could not be processed successfully."
            ),
        }

    if not all_chunks and preserve_index_on_empty:
        return {
            "repository_path": str(root),
            "files_discovered": len(source_files),
            "files_processed": len(source_files),
            "chunks_created": 0,
            "chunks_indexed": 0,
            "files_with_errors": [],
            "message": "No supported source chunks were found; the previous index was left unchanged.",
        }

    if progress_callback:
        progress_callback("embedding", f"Generating embeddings for {len(all_chunks)} code chunks…", 58)
    indexed_count = index_chunks(
        str(root),
        all_chunks,
        progress_callback=progress_callback,
    )

    return {
        "repository_path": str(root),
        "files_discovered": len(source_files),
        "files_processed": len(source_files) - len(files_with_errors),
        "chunks_created": len(all_chunks),
        "chunks_indexed": indexed_count,
        "files_with_errors": files_with_errors,
        "message": "Repository indexed successfully.",
    }
