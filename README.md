# CodebaseIQ — AI Codebase Assistant

CodebaseIQ lets a developer connect a **public GitHub repository**, ask questions about its code, and receive an answer grounded in retrieved source chunks.

## Features
- Public GitHub repository cloning and indexing
- Tree-sitter parsing and code-aware chunks with file/line references
- Local Sentence Transformers embeddings + ChromaDB vector retrieval
- BM25 keyword retrieval combined with vector search using reciprocal rank fusion
- Gemini-generated answers with source references
- Google sign-in and per-user repository/conversation ownership
- PostgreSQL-backed conversations and messages, ordered by recent activity
- Create blank conversations, reopen history, rename/delete chats, light/dark theme

## Architecture

```text
React + Vite
   │ Google ID token / JSON API
   ▼
FastAPI ─────── Google token verification
   │
   ├── PostgreSQL: repository ownership, conversations, messages
   ├── Git: shallow clone of public GitHub repositories
   ├── Tree-sitter: parse and chunk source files
   ├── Sentence Transformers + ChromaDB: semantic retrieval
   ├── BM25 + RRF: hybrid retrieval
   └── Gemini: answer grounded in retrieved code
```

## Quick start

See [DEPLOYMENT.md](DEPLOYMENT.md) for local setup, Google OAuth, PostgreSQL, deployment, and the submission smoke test.

1. Copy `.env.example` to `.env` and configure `GEMINI_API_KEY`.
2. Install backend dependencies with `pip install -r requirements.txt`.
3. Run the API from `backend/`: `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
4. Copy `frontend/.env.example` to `frontend/.env`, then run `npm install` and `npm run dev` from `frontend/`.

## Scope and limitations
- Only public GitHub repository URLs are supported. Private GitHub repositories and local folder paths are intentionally deferred.
- Current code file support: Python, JavaScript, JSX, TypeScript, and TSX.
- For account-private history in deployment, configure the same Google Web Client ID in both frontend and backend, and set `DATABASE_URL` to PostgreSQL. Do not deploy with Google auth disabled.
- ChromaDB and repository clones are stored on the backend filesystem. Use persistent storage if available; on ephemeral hosting, the vector index may need to be rebuilt after a restart.
