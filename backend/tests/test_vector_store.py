

import pytest

from app.services.vector_store import (
    get_collection,
    get_repository_id,
    index_chunks,
    search_code,
)


def make_chunk(chunk_id, content, file_path="sample.py"):
    return {
        "chunk_id": chunk_id,
        "file_path": file_path,
        "node_type": "function_definition",
        "start_line": 1,
        "end_line": 2,
        "content": content,
    }


def test_index_chunks_replaces_previous_repository_index(tmp_path):
    repository = str(tmp_path / "repo")
    other_repository = str(tmp_path / "other")

    index_chunks(
        repository,
        [make_chunk("old", "def old_function(): return 1")],
    )
    index_chunks(
        other_repository,
        [make_chunk("other", "def other_function(): return 2")],
    )

    index_chunks(
        repository,
        [make_chunk("new", "def new_function(): return 3")],
    )

    collection = get_collection()
    repo_id = get_repository_id(repository)
    other_id = get_repository_id(other_repository)

    repo_records = collection.get(
        where={"repository_id": repo_id},
        include=["metadatas"],
    )
    other_records = collection.get(
        where={"repository_id": other_id},
        include=["metadatas"],
    )

    assert len(repo_records["ids"]) == 1
    assert len(other_records["ids"]) == 1
    assert search_code(
        "old_function",
        repository,
    ) == [] or all(
        "old_function" not in result["content"]
        for result in search_code("old_function", repository)
    )


def test_empty_chunks_clear_only_target_repository(tmp_path):
    repository = str(tmp_path / "empty-repo")
    other_repository = str(tmp_path / "preserved-repo")

    index_chunks(
        repository,
        [make_chunk("old", "def old_function(): return 1")],
    )
    index_chunks(
        other_repository,
        [make_chunk("keep", "def keep_function(): return 2")],
    )

    assert index_chunks(repository, []) == 0

    collection = get_collection()

    assert collection.get(
        where={"repository_id": get_repository_id(repository)},
        include=["metadatas"],
    )["ids"] == []

    assert len(collection.get(
        where={"repository_id": get_repository_id(other_repository)},
        include=["metadatas"],
    )["ids"]) == 1


def test_invalid_chunks_do_not_delete_existing_index(tmp_path):
    repository = str(tmp_path / "validation-repo")

    index_chunks(
        repository,
        [make_chunk("existing", "def existing_function(): return 1")],
    )

    with pytest.raises(ValueError):
        index_chunks(repository, [{
            "chunk_id": "invalid",
            "content": "def invalid_function(): return 2",
        }])

    records = get_collection().get(
        where={"repository_id": get_repository_id(repository)},
        include=["documents"],
    )

    assert len(records["ids"]) == 1
    assert "existing_function" in records["documents"][0]


def test_duplicate_chunk_ids_are_rejected_before_replacement(tmp_path):
    repository = str(tmp_path / "duplicate-repo")

    index_chunks(
        repository,
        [make_chunk("existing", "def existing_function(): return 1")],
    )

    with pytest.raises(ValueError, match="Duplicate chunk_id"):
        index_chunks(repository, [
            make_chunk("duplicate", "def first(): return 1"),
            make_chunk("duplicate", "def second(): return 2"),
        ])

    records = get_collection().get(
        where={"repository_id": get_repository_id(repository)},
        include=["documents"],
    )

    assert len(records["ids"]) == 1
    assert "existing_function" in records["documents"][0]


def test_repository_id_is_stable():
    first = get_repository_id(".")
    second = get_repository_id(".")

    assert first == second


def test_repository_ids_are_different():
    first = get_repository_id("D:/projects/project-a")
    second = get_repository_id("D:/projects/project-b")

    assert first != second
