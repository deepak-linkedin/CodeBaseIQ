import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(PROJECT_ROOT / ".env")

APP_NAME = os.getenv(
    "APP_NAME",
    "Codebase Intelligence Assistant",
)

DEBUG = os.getenv("DEBUG","true").lower() == "true"

BACKEND_HOST = os.getenv("BACKEND_HOST","127.0.0.1")

BACKEND_PORT = int(os.getenv("BACKEND_PORT","8000"))

FRONTEND_ORIGIN = os.getenv(
    "FRONTEND_ORIGIN",
    "http://localhost:5173",
)

DATA_DIR = Path(
    os.getenv("DATA_DIR",str(PROJECT_ROOT / "data"))
).resolve()

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "gemini-embedding-001",
)

LLM_PROVIDER = os.getenv("LLM_PROVIDER","local")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","")

GEMINI_MODEL = os.getenv("GEMINI_MODEL","gemini-3.5-flash-lite")