
from pathlib import Path
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.repository_service import ingest_repository
from app.services.vector_store import (
    delete_repository_index,
    get_repository_id,
    get_repository_stats,
    list_indexed_repositories,
)

router = APIRouter(
    prefix="/api/repositories",
    tags=["Repositories"],
)


class IndexRepositoryRequest(BaseModel):
    repository_path: str = Field(
        min_length=1,
        description="Absolute path to the local repository",
    )


@router.post("/index")
def index_repository(request: IndexRepositoryRequest):
    """Legacy local-path indexing endpoint for local development only."""
    if os.getenv("GOOGLE_CLIENT_ID", "").strip() or os.getenv("AUTH_REQUIRED", "false").lower() == "true":
        raise HTTPException(status_code=410, detail="Local-path indexing is disabled in the deployed app. Connect a public GitHub repository instead.")
    try:
        root = Path(request.repository_path).expanduser().resolve()

        if not root.exists():
            raise HTTPException(
                status_code=404,
                detail="Repository path does not exist.",
            )

        if not root.is_dir():
            raise HTTPException(
                status_code=400,
                detail="Repository path must be a directory.",
            )

        result = ingest_repository(str(root))
        repository_id = get_repository_id(str(root))

        return {
            "repository_id": repository_id,
            **result,
        }

    except HTTPException:
        raise
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("")
def get_repositories():
    """Legacy repository list for local development only."""
    if os.getenv("GOOGLE_CLIENT_ID", "").strip() or os.getenv("AUTH_REQUIRED", "false").lower() == "true":
        raise HTTPException(status_code=410, detail="Use /api/workspace/repositories.")
    try:
        return {
            "repositories": list_indexed_repositories(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve indexed repositories.",
        ) from exc


@router.get("/{repository_id}/status")
def get_repository_status(repository_id: str):
    """Get indexing statistics for a repository."""
    if os.getenv("GOOGLE_CLIENT_ID", "").strip() or os.getenv("AUTH_REQUIRED", "false").lower() == "true":
        raise HTTPException(status_code=410, detail="Use /api/workspace/repositories.")
    try:
        stats = get_repository_stats(repository_id)

        if stats["chunks_count"] == 0:
            raise HTTPException(
                status_code=404,
                detail="Repository not found or has no indexed chunks.",
            )

        return stats

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve repository status.",
        ) from exc


@router.delete("/{repository_id}")
def delete_repository(repository_id: str):
    """Legacy index deletion for local development only."""
    if os.getenv("GOOGLE_CLIENT_ID", "").strip() or os.getenv("AUTH_REQUIRED", "false").lower() == "true":
        raise HTTPException(status_code=410, detail="Use /api/workspace/repositories/{repository_id}.")
    try:
        deleted_count = delete_repository_index(repository_id)

        if deleted_count == 0:
            raise HTTPException(
                status_code=404,
                detail="Repository not found or has no indexed chunks.",
            )

        return {
            "repository_id": repository_id,
            "deleted_chunks": deleted_count,
            "message": "Repository index deleted successfully.",
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete repository index.",
        ) from exc
