from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.repositories import router as repositories_router
from app.api.chat import router as chat_router
from app.api.workspace import router as workspace_router
from app.db import init_db

from app.core.config import (
    APP_NAME,
    BACKEND_HOST,
    BACKEND_PORT,
    DATA_DIR,
    DEBUG,
    FRONTEND_ORIGIN,
)

app = FastAPI(
    title = APP_NAME,
    description="AI-powered codebase understanding assistant",
    version="0.1.0",
    debug=DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_ORIGIN,
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type","Authorization"],
)

app.include_router(repositories_router)
app.include_router(chat_router)
app.include_router(workspace_router)

@app.on_event("startup")
def create_data_directory():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    init_db()

@app.get("/")
def root():
    return {
        "message": "Codebase Intelligence Assistant API",
        "status": "running",
        "version": "0.1.0",
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "app": APP_NAME,
    }

if __name__=="__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        reload=DEBUG
    )