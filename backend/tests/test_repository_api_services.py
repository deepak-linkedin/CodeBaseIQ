
from app.services.repository_service import ingest_repository
from app.services.vector_store import (
    delete_repository_index,
    get_repository_id,
    get_repository_stats,
    list_indexed_repositories,
)


def test_repository_stats_report_files_and_chunks(tmp_path):
    (tmp_path / "main.py").write_text(
        "def first_function():\n    return 1\n\n"
        "def second_function():\n    return 2\n",
        encoding="utf-8",
    )

    ingest_repository(str(tmp_path))

    repository_id = get_repository_id(str(tmp_path))
    stats = get_repository_stats(repository_id)

    assert stats["repository_id"] == repository_id
    assert stats["chunks_count"] >= 1
    assert stats["files_count"] == 1


def test_list_indexed_repositories_includes_indexed_repository(tmp_path):
    (tmp_path / "main.py").write_text(
        "def listing_test_function():\n    return 1\n",
        encoding="utf-8",
    )

    ingest_repository(str(tmp_path))

    repository_id = get_repository_id(str(tmp_path))
    repositories = list_indexed_repositories()
    repository_ids = {
        repository["repository_id"]
        for repository in repositories
    }

    assert repository_id in repository_ids


def test_delete_repository_index_preserves_other_repositories(tmp_path):
    repository_a = tmp_path / "repository_a"
    repository_b = tmp_path / "repository_b"
    repository_a.mkdir()
    repository_b.mkdir()

    (repository_a / "main.py").write_text(
        "def delete_target_function():\n    return 1\n",
        encoding="utf-8",
    )
    (repository_b / "main.py").write_text(
        "def preserve_target_function():\n    return 2\n",
        encoding="utf-8",
    )

    ingest_repository(str(repository_a))
    ingest_repository(str(repository_b))

    repository_a_id = get_repository_id(str(repository_a))
    repository_b_id = get_repository_id(str(repository_b))

    deleted_count = delete_repository_index(repository_a_id)

    assert deleted_count > 0
    assert get_repository_stats(repository_a_id)["chunks_count"] == 0
    assert get_repository_stats(repository_b_id)["chunks_count"] > 0
