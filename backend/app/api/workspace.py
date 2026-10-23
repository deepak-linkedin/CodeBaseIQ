import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session
import re

from app.db import SessionLocal

from app.auth import get_current_user_id
from app.core.config import DATA_DIR
from app.db import get_db
from app.models import Conversation, Message, Repository
from app.services.github_service import clone_and_index_public_repository, normalize_github_url
from app.services.indexing_jobs import create_or_get_job, get_job, update_job
from app.services.hybrid_search import hybrid_search
from app.services.llm_service import generate_answer
from app.services.vector_store import delete_repository_index, get_repository_id

router = APIRouter(prefix="/api/workspace", tags=["Workspace"])


def new_id() -> str:
    return uuid.uuid4().hex


def owned_conversation(db: Session, conversation_id: str, user_id: str) -> Conversation:
    item = db.scalar(select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == user_id
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return item


def owned_repository(db: Session, repository_id: str, user_id: str) -> Repository:
    item = db.scalar(select(Repository).where(
        Repository.id == repository_id, Repository.user_id == user_id
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    return item


class ConnectRepositoryRequest(BaseModel):
    github_url: str = Field(min_length=1, max_length=500)


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class RenameConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    repository_id: str = Field(min_length=1)


@router.get("/repositories")
def list_repositories(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    items = db.scalars(select(Repository).where(
        Repository.user_id == user_id
    ).order_by(desc(Repository.created_at))).all()
    response = []
    for item in items:
        stats = {}
        try:
            from app.services.vector_store import get_repository_stats
            stats = get_repository_stats(get_repository_id(item.local_path))
        except Exception:
            pass
        response.append({
            "id": item.id,
            "repository_id": get_repository_id(item.local_path),
            "github_url": item.github_url,
            "name": item.name,
            "chunks_count": stats.get("chunks_count", 0),
            "files_count": stats.get("files_count", 0),
            "created_at": item.created_at.isoformat() if item.created_at else None,
        })
    return {"repositories": response}


def _next_repository_display_name(db: Session, user_id: str, base_name: str) -> str:
    """Number repository labels per base name: project (1), project (2), etc."""
    existing_names = db.scalars(select(Repository.name).where(Repository.user_id == user_id)).all()
    pattern = re.compile(rf"^{re.escape(base_name)} \((\d+)\)$", re.IGNORECASE)
    used = []
    for name in existing_names:
        match = pattern.match(name or "")
        if match:
            used.append(int(match.group(1)))
        elif (name or "").casefold() == base_name.casefold():
            used.append(0)
    next_number = max(used, default=0) + 1
    return f"{base_name} ({next_number})"

def _run_repository_index_job(job_id: str, github_url: str, user_id: str) -> None:
    db = SessionLocal()
    try:
        update_job(job_id, status="running", stage="cloning", message="Starting repository clone…", progress=3)
        def report(stage: str, message: str, progress: int) -> None:
            update_job(job_id, status="running", stage=stage, message=message, progress=progress)
        normalized_url, base_name = normalize_github_url(github_url)
        result = clone_and_index_public_repository(normalized_url, user_id, progress_callback=report)
        existing = db.scalar(select(Repository).where(
            Repository.user_id == user_id,
            func.lower(Repository.github_url) == result["github_url"].lower(),
        ))
        if existing:
            existing.local_path = result["local_path"]
            item = existing
        else:
            item = Repository(
                id=result["id"], user_id=user_id, github_url=result["github_url"],
                name=_next_repository_display_name(db, user_id, base_name),
                local_path=result["local_path"],
            )
            db.add(item)
        db.commit()
        update_job(job_id, status="completed", stage="complete", message="Repository connected and indexed successfully.", progress=100, result={
            "id": item.id, "name": item.name, "github_url": item.github_url,
            "repository_id": get_repository_id(item.local_path),
            "files_processed": result.get("files_processed", 0),
            "chunks_indexed": result.get("chunks_indexed", 0),
        })
    except Exception as exc:
        db.rollback()
        update_job(job_id, status="failed", stage="failed", message="Repository indexing failed.", error=str(exc), progress=100)
    finally:
        db.close()

@router.post("/repositories", status_code=202)
def connect_repository(
    request: ConnectRepositoryRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        normalized_url, _repo_name = normalize_github_url(request.github_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = db.scalar(select(Repository).where(
        Repository.user_id == user_id,
        func.lower(Repository.github_url) == normalized_url.removesuffix(".git").lower(),
    ))

    # Reuse an active job if the user closed the tab or clicked Connect twice.
    # The HTTP client disconnect does not cancel FastAPI's background task.
    job_id, created = create_or_get_job(user_id, normalized_url)
    if not created:
        active_job = get_job(job_id, user_id) or {}
        return {
            "job_id": job_id,
            "status": active_job.get("status", "running"),
            "message": "This repository is already being indexed. Reusing the active job.",
            "existing_repository": bool(existing),
        }

    # If it is already connected and its index exists, don't destroy and rebuild
    # the same checkout just because the user clicks Connect again.
    if existing and Path(existing.local_path).is_dir():
        try:
            from app.services.vector_store import get_repository_stats
            stats = get_repository_stats(get_repository_id(existing.local_path))
        except Exception:
            stats = {"chunks_count": 0, "files_count": 0}
        if stats.get("chunks_count", 0) > 0:
            update_job(job_id, status="completed", stage="complete",
                       message="Repository is already connected and indexed.", progress=100,
                       result={"id": existing.id, "name": existing.name,
                               "github_url": existing.github_url,
                               "repository_id": get_repository_id(existing.local_path),
                               "files_processed": stats.get("files_count", 0),
                               "chunks_indexed": stats.get("chunks_count", 0)})
            return {"job_id": job_id, "status": "completed",
                    "message": "Repository is already connected and indexed.",
                    "existing_repository": True}

    background_tasks.add_task(_run_repository_index_job, job_id, normalized_url, user_id)
    return {"job_id": job_id, "status": "queued", "message": "Repository indexing queued.", "existing_repository": bool(existing)}

@router.get("/repositories/jobs/{job_id}")
def repository_indexing_status(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    job = get_job(job_id, user_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Indexing job not found.")
    return job


@router.delete("/repositories/{repository_id}")
def remove_repository(
    repository_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    item = owned_repository(db, repository_id, user_id)
    repository_name = item.name
    local_path = Path(item.local_path).resolve()
    owned_root = (DATA_DIR / "repos").resolve()
    try:
        delete_repository_index(get_repository_id(str(local_path)))
    except Exception:
        pass
    # Delete only clones within the app-managed repository directory.
    if local_path.is_relative_to(owned_root) and local_path.exists():
        shutil.rmtree(local_path, ignore_errors=True)
    db.execute(update(Conversation).where(Conversation.repository_id == item.id).values(repository_id=None))
    db.delete(item)
    db.commit()
    return {"message": f"Disconnected {repository_name}."}


@router.get("/conversations")
def list_conversations(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    items = db.scalars(select(Conversation).where(
        Conversation.user_id == user_id
    ).order_by(desc(Conversation.updated_at), desc(Conversation.created_at))).all()
    return {"conversations": [{
        "id": item.id, "title": item.title,
        "repository_id": item.repository_id,
        "repository_name": item.repository.name if item.repository else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    } for item in items]}


@router.post("/conversations")
def create_conversation(
    request: CreateConversationRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    item = Conversation(
        id=new_id(), user_id=user_id,
        title=(request.title or "").strip() or "New conversation",
        repository_id=None, created_at=now, updated_at=now,
    )
    db.add(item)
    db.commit()
    return {"id": item.id, "title": item.title, "repository_id": None, "messages": []}


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    item = owned_conversation(db, conversation_id, user_id)
    messages = db.scalars(select(Message).where(
        Message.conversation_id == item.id, Message.user_id == user_id
    ).order_by(Message.created_at)).all()
    return {
        "id": item.id, "title": item.title,
        "repository_id": item.repository_id,
        "repository_name": item.repository.name if item.repository else None,
        "messages": [{
            "id": m.id, "role": m.role, "content": m.content,
            "sources": m.sources or [],
            "created_at": m.created_at.isoformat() if m.created_at else None,
        } for m in messages],
    }


@router.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: str,
    request: RenameConversationRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    item = owned_conversation(db, conversation_id, user_id)
    cleaned_title = request.title.strip()
    if not cleaned_title:
        raise HTTPException(status_code=422, detail="Conversation title cannot be empty.")
    item.title = cleaned_title
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": item.id, "title": item.title}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    item = owned_conversation(db, conversation_id, user_id)
    db.delete(item)
    db.commit()
    return {"message": "Conversation deleted."}


@router.post("/conversations/{conversation_id}/messages")
def ask_in_conversation(
    conversation_id: str,
    request: AskRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    conversation = owned_conversation(db, conversation_id, user_id)
    repository = owned_repository(db, request.repository_id, user_id)
    if conversation.repository_id and conversation.repository_id != repository.id:
        raise HTTPException(
            status_code=400,
            detail="This conversation is already associated with a different repository. Start a new conversation to switch repositories.",
        )

    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    now = datetime.now(timezone.utc)
    if conversation.repository_id is None:
        conversation.repository_id = repository.id

    user_message = Message(
        id=new_id(), conversation_id=conversation.id, user_id=user_id,
        role="user", content=question, sources=[], created_at=now,
    )
    db.add(user_message)

    if conversation.title == "New conversation":
        conversation.title = question[:58] + ("…" if len(question) > 58 else "")

    try:
        chunks = hybrid_search(
            query=question, repository_path=repository.local_path, top_k=5
        )
        if chunks:
            answer = generate_answer(question=question, context_chunks=chunks)
            sources = [{
                "file_path": chunk.get("file_path", ""),
                "start_line": chunk.get("start_line"),
                "end_line": chunk.get("end_line"),
                "node_type": chunk.get("node_type", "unknown"),
            } for chunk in chunks]
        else:
            answer = "I couldn't find relevant indexed code for that question. Try asking about a function, file, or data flow present in this repository."
            sources = []
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to answer the repository question.") from exc

    assistant_message = Message(
        id=new_id(), conversation_id=conversation.id, user_id=user_id,
        role="assistant", content=answer, sources=sources,
        created_at=datetime.now(timezone.utc),
    )
    conversation.updated_at = datetime.now(timezone.utc)
    db.add(assistant_message)
    db.commit()
    return {
        "question": question, "answer": answer, "sources": sources,
        "conversation_id": conversation.id, "title": conversation.title,
        "repository_id": repository.id,
    }
