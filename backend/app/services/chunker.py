from pathlib import Path

from app.services.code_parser import extract_code_units
from app.services.repository_loader import read_source_file

def chunk_source_file(
    repository_path: str,
    relative_path: Path,
) -> list[dict]:
    source = read_source_file(repository_path,relative_path)

    parsed = extract_code_units(
        source,
        relative_path.suffix,
    )

    chunks = []

    for index,unit in enumerate(parsed["units"]):
        chunks.append({
            "chunk_id": (
                f"{relative_path.as_posix()}:"
                f"{unit['start_line']}:"
                f"{index}"
            ),
            "file_path": relative_path.as_posix(),
            "node_type": unit["node_type"],
            "start_line": unit["start_line"],
            "end_line": unit["end_line"],
            "content": unit["code"],
        })

     # If Tree-sitter finds no target nodes, preserve the file
    # as a single chunk instead of silently losing its contents.
    if not chunks and source.strip():
        chunks.append({
            "chunk_id": f"{relative_path.as_posix()}:file",
            "file_path": relative_path.as_posix(),
            "node_type": "file",
            "start_line": 1,
            "end_line": len(source.splitlines()),
            "content": source,
        })

    return chunks