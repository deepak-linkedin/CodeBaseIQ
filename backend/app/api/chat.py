
from pathlib import Path
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.hybrid_search import hybrid_search
from app.services.llm_service import generate_answer
from app.services.vector_store import get_repository_id


router = APIRouter(
    prefix="/api/chat",
    tags=["Chat"],
)


class ChatRequest(BaseModel):
    repository_path: str = Field(
        min_length=1,
        description="Absolute path to the indexed local repository",
    )
    question: str = Field(
        min_length=1,
        description="Question about the repository's source code",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of code chunks to retrieve",
    )


@router.post("")
def chat(request: ChatRequest):
    """Legacy local-path chat endpoint for local development only."""
    if os.getenv("GOOGLE_CLIENT_ID", "").strip() or os.getenv("AUTH_REQUIRED", "false").lower() == "true":
        raise HTTPException(status_code=410, detail="Use /api/workspace/conversations/{conversation_id}/messages.")

    try:
        root = Path(request.repository_path).expanduser().resolve()

        if not root.exists() or not root.is_dir():
            raise HTTPException(
                status_code=404,
                detail="Repository path does not exist or is not a directory.",
            )

        repository_id = get_repository_id(str(root))

        chunks = hybrid_search(
            query=request.question,
            repository_path=str(root),
            top_k=request.top_k,
        )

        if not chunks:
            return {
                "repository_id": repository_id,
                "question": request.question,
                "answer": (
                    "I couldn't find relevant indexed code to answer "
                    "this question. Please check that this repository "
                    "has been indexed."
                ),
                "sources": [],
            }

        answer = generate_answer(
            question=request.question,
            context_chunks=chunks,
        )

        sources = [
            {
                "file_path": chunk.get("file_path", ""),
                "start_line": chunk.get("start_line"),
                "end_line": chunk.get("end_line"),
                "node_type": chunk.get("node_type", "unknown"),
            }
            for chunk in chunks
        ]

        return {
            "repository_id": repository_id,
            "question": request.question,
            "answer": answer,
            "sources": sources,
        }

    except HTTPException:
        raise

    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to answer the repository question.",
        ) from exc
