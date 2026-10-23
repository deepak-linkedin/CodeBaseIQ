
from pathlib import Path

from app.services.repository_service import ingest_repository
from app.services.vector_store import get_collection, get_repository_id


def get_indexed_records(repository_path: Path) -> dict:
    """Return indexed chunks belonging to one repository."""
    collection = get_collection()
    repository_id = get_repository_id(str(repository_path))

    return collection.get(
        where={"repository_id": repository_id},
        include=["documents", "metadatas"],
    )


def test_reindex_replaces_modified_file_content(tmp_path):
    source_file = tmp_path / "main.py"
    source_file.write_text(
        "def old_calculation_marker():\n"
        "    return 101\n",
        encoding="utf-8",
    )

    ingest_repository(str(tmp_path))

    old_records = get_indexed_records(tmp_path)
    assert old_records["documents"]
    assert any(
        "old_calculation_marker" in document
        for document in old_records["documents"]
    )

    source_file.write_text(
        "def new_calculation_marker():\n"
        "    return 202\n",
        encoding="utf-8",
    )

    result = ingest_repository(str(tmp_path))
    updated_records = get_indexed_records(tmp_path)

    assert result["message"] == "Repository indexed successfully."
    assert any(
        "new_calculation_marker" in document
        for document in updated_records["documents"]
    )
    assert all(
        "old_calculation_marker" not in document
        for document in updated_records["documents"]
    )


def test_reindex_removes_deleted_file_chunks(tmp_path):
    keep_file = tmp_path / "keep.py"
    delete_file = tmp_path / "delete_me.py"

    keep_file.write_text(
        "def retained_function_marker():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    delete_file.write_text(
        "def deleted_function_marker():\n"
        "    return 2\n",
        encoding="utf-8",
    )

    ingest_repository(str(tmp_path))

    initial_records = get_indexed_records(tmp_path)
    assert len(initial_records["documents"]) >= 2

    delete_file.unlink()
    ingest_repository(str(tmp_path))

    updated_records = get_indexed_records(tmp_path)

    assert any(
        "retained_function_marker" in document
        for document in updated_records["documents"]
    )
    assert all(
        "deleted_function_marker" not in document
        for document in updated_records["documents"]
    )
    assert all(
        metadata["file_path"] != "delete_me.py"
        for metadata in updated_records["metadatas"]
    )


def test_empty_repository_clears_its_previous_index(tmp_path):
    source_file = tmp_path / "main.py"
    source_file.write_text(
        "def temporary_function_marker():\n"
        "    return 3\n",
        encoding="utf-8",
    )

    ingest_repository(str(tmp_path))
    assert get_indexed_records(tmp_path)["documents"]

    source_file.unlink()
    result = ingest_repository(str(tmp_path))

    records = get_indexed_records(tmp_path)

    assert result["chunks_indexed"] == 0
    assert records["documents"] == []
    assert records["metadatas"] == []


def test_reindexing_one_repository_preserves_another(tmp_path):
    repository_a = tmp_path / "repository_a"
    repository_b = tmp_path / "repository_b"

    repository_a.mkdir()
    repository_b.mkdir()

    (repository_a / "main.py").write_text(
        "def repository_a_marker():\n"
        "    return 10\n",
        encoding="utf-8",
    )
    (repository_b / "main.py").write_text(
        "def repository_b_marker():\n"
        "    return 20\n",
        encoding="utf-8",
    )

    ingest_repository(str(repository_a))
    ingest_repository(str(repository_b))

    (repository_a / "main.py").unlink()
    ingest_repository(str(repository_a))

    records_a = get_indexed_records(repository_a)
    records_b = get_indexed_records(repository_b)

    assert records_a["documents"] == []
    assert any(
        "repository_b_marker" in document
        for document in records_b["documents"]
    )


def test_all_file_processing_failures_leave_index_unchanged(
    tmp_path, monkeypatch
):
    import app.services.repository_service as repository_service

    source_file = tmp_path / "main.py"
    source_file.write_text(
        "def existing_function_marker():\n"
        "    return 42\n",
        encoding="utf-8",
    )

    ingest_repository(str(tmp_path))
    before = get_indexed_records(tmp_path)

    def fail_chunking(repository_path, relative_path):
        raise OSError("Simulated file read failure")

    def unexpected_index_call(repository_path, chunks):
        raise AssertionError(
            "Indexing should not run when all files fail."
        )

    monkeypatch.setattr(
        repository_service,
        "chunk_source_file",
        fail_chunking,
    )
    monkeypatch.setattr(
        repository_service,
        "index_chunks",
        unexpected_index_call,
    )

    result = ingest_repository(str(tmp_path))
    after = get_indexed_records(tmp_path)

    assert result["files_with_errors"]
    assert "Index unchanged" in result["message"]
    assert before["documents"] == after["documents"]
    assert before["metadatas"] == after["metadatas"]


def test_partial_file_processing_failure_preserves_entire_index(
    tmp_path, monkeypatch
):
    import app.services.repository_service as repository_service

    failing_file = tmp_path / "problem.py"
    healthy_file = tmp_path / "healthy.py"

    failing_file.write_text(
        "def original_problem_marker():\n    return 11\n",
        encoding="utf-8",
    )
    healthy_file.write_text(
        "def original_healthy_marker():\n    return 22\n",
        encoding="utf-8",
    )

    ingest_repository(str(tmp_path))
    before = get_indexed_records(tmp_path)

    # Change the healthy file, but simulate a failure on the other file.
    healthy_file.write_text(
        "def updated_healthy_marker():\n    return 33\n",
        encoding="utf-8",
    )

    original_chunk_source_file = repository_service.chunk_source_file

    def fail_one_file(repository_path, relative_path):
        if relative_path.as_posix() == "problem.py":
            raise OSError("Simulated file read failure")

        return original_chunk_source_file(repository_path, relative_path)

    monkeypatch.setattr(
        repository_service,
        "chunk_source_file",
        fail_one_file,
    )

    result = ingest_repository(str(tmp_path))
    after = get_indexed_records(tmp_path)

    assert result["files_with_errors"]
    assert result["chunks_indexed"] == 0
    assert "Index unchanged" in result["message"]

    # Neither file's old indexed content should have been replaced or lost.
    assert before["documents"] == after["documents"]
    assert before["metadatas"] == after["metadatas"]
