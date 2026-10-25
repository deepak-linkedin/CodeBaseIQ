# CodebaseIQ — AI Codebase Assistant

**CodebaseIQ** is an AI-powered codebase assistant that helps developers understand a public GitHub repository by asking questions in natural language. It indexes source code, retrieves relevant code sections using a hybrid search pipeline, and generates answers grounded in the retrieved files with source paths and line references.

## Project Links

- **Live application:** https://codebase-iq.vercel.app
- **Demo video:** https://drive.google.com/file/d/1rwHaB5WX4l34E6ppO9stDTmGP9GemNMt/view?usp=sharing

## Overview

Understanding an unfamiliar repository can require manually exploring many files and tracing how functions work together. CodebaseIQ provides a conversational interface for exploring code: connect a public GitHub repository, let the application index supported source files, and ask questions about the codebase.

The retrieval pipeline combines semantic similarity with keyword-based search. Retrieved code chunks are supplied to the language model as context so that answers can reference the source files and relevant line ranges instead of relying only on general model knowledge.

## Features

- **Public GitHub repository ingestion:** Connect a repository by its public GitHub URL.
- **Code-aware parsing and chunking:** Tree-sitter parses supported languages and creates chunks with file paths and line ranges.
- **Hosted embeddings:** Google's `gemini-embedding-001` generates vector embeddings for code chunks and natural-language queries.
- **Semantic retrieval:** ChromaDB stores and retrieves vector representations of code chunks.
- **Hybrid search:** BM25 keyword retrieval is combined with vector retrieval using Reciprocal Rank Fusion (RRF).
- **Context-grounded answers:** Gemini generates explanations using retrieved code context and references relevant files and line numbers.
- **Google sign-in:** Supports Google authentication when OAuth is configured.
- **User-specific data:** Repository ownership and conversation data are associated with the signed-in user.
- **Persistent chat history:** PostgreSQL can store conversations and messages across sessions.
- **Conversation management:** Start a new conversation, revisit previous chats, rename conversations, and delete them.
- **Interface preferences:** Light and dark themes.
- **Indexing progress:** The interface displays progress while a repository is being cloned, parsed, embedded, and indexed.

## Supported Source Files

The current indexing pipeline supports:

- Python (`.py`)
- JavaScript (`.js`)
- JSX (`.jsx`)
- TypeScript (`.ts`)
- TSX (`.tsx`)

The application is designed for **public GitHub repositories**.

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, Vite, JavaScript, React Markdown, Lucide React |
| Backend API | Python, FastAPI, Uvicorn |
| Repository ingestion | Git, GitPython |
| Parsing and chunking | Tree-sitter, language-specific Tree-sitter grammars |
| Embeddings | Google Gen AI SDK, `gemini-embedding-001` |
| Vector database | ChromaDB |
| Keyword search | BM25, `rank-bm25` |
| Hybrid ranking | Reciprocal Rank Fusion (RRF) |
| Answer generation | Gemini (`gemini-3.5-flash-lite` by default) |
| Persistence | SQLAlchemy, PostgreSQL with psycopg; SQLite for local development when configured by the application |
| Authentication | Google OAuth ID-token verification |
| Deployment | Vercel (frontend), Render (backend) |

## Architecture

```text
┌────────────────────────────────────┐
│          React + Vite UI           │
│ Repository sidebar · Chat · Theme  │
└──────────────────┬─────────────────┘
                   │ HTTP / JSON
                   ▼
┌────────────────────────────────────┐
│             FastAPI                │
│ API endpoints · Auth · Chat logic  │
└───────┬──────────────┬─────────────┘
        │              │
        ▼              ▼
┌────────────────┐  ┌────────────────────┐
│ Public GitHub  │  │ SQL database       │
│ clone via Git  │  │ Users' repository  │
└───────┬────────┘  │ ownership and chats│
        │           └────────────────────┘
        ▼
┌────────────────────────────────────┐
│ Tree-sitter parsing and chunking    │
│ File paths and line-number metadata │
└──────────────────┬─────────────────┘
                   ▼
┌────────────────────────────────────┐
│ Google hosted embeddings           │
│ gemini-embedding-001                │
└──────────────────┬─────────────────┘
                   ▼
┌────────────────────────────────────┐
│ ChromaDB vector search + BM25       │
│ Reciprocal Rank Fusion (RRF)        │
└──────────────────┬─────────────────┘
                   ▼
┌────────────────────────────────────┐
│ Gemini answer generation            │
│ Retrieved code context + references │
└────────────────────────────────────┘
```

### Question-answering flow

1. The user connects a public GitHub repository.
2. The backend clones the repository and discovers supported source files.
3. Tree-sitter parses the files and creates code chunks with file and line metadata.
4. The embedding service generates vector representations and stores the chunks in ChromaDB.
5. When the user asks a question, the system retrieves relevant chunks through semantic vector search and BM25 keyword search.
6. Reciprocal Rank Fusion combines the retrieval rankings.
7. The retrieved source context is sent to Gemini to generate an explanation grounded in the code.
8. The answer is returned in the chat interface with source file and line references where available.

## Run Locally

### Prerequisites

- Python 3.10 or newer
- Node.js and npm
- Git installed and available on your PATH
- A Google Gemini API key for hosted embeddings and answer generation

### 1. Configure the backend

From the project root, create and activate a virtual environment, then install the Python dependencies.

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit the root `.env` file and set the Gemini configuration:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Keep secret values in `.env`; do not commit API keys or database credentials.

Start the backend from the project root:

```powershell
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at `http://127.0.0.1:8000`. The health endpoint is `/health`.

### 2. Configure and run the frontend

Open a second terminal from the project root:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

For local development, `frontend/.env` should contain:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_GOOGLE_CLIENT_ID=
```

Open the local Vite URL shown in the terminal, normally `http://localhost:5173`.

### 3. Configure authentication and persistent chat history

Google sign-in can be enabled by creating a Google OAuth Web client and configuring the same client ID in both places:

- Root `.env`: `GOOGLE_CLIENT_ID=...`
- `frontend/.env`: `VITE_GOOGLE_CLIENT_ID=...`

Set `DATABASE_URL` in the backend environment to a PostgreSQL connection string to use PostgreSQL for persisted conversations, messages, and repository ownership. Local development can use the application's local database configuration when `DATABASE_URL` is not set.

For deployment, configure authentication and the database in the hosting environment rather than committing secrets to source control.

## Deployment

The project is deployed with the frontend on Vercel and the backend on Render.

### Frontend — Vercel

- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variables:
  - `VITE_API_BASE_URL=https://codebaseiq-backend.onrender.com`
  - `VITE_GOOGLE_CLIENT_ID=<Google OAuth Web client ID>`

### Backend — Render

- Build command: `pip install -r requirements.txt`
- Start command:

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Configure the backend environment variables in Render:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=<Gemini API key>
GEMINI_MODEL=<GEMINI_MODEL>
GOOGLE_CLIENT_ID=<Google OAuth Web client ID>
DATABASE_URL=<PostgreSQL connection string>
FRONTEND_ORIGIN=<FRONTEND_URL>
```

For additional environment and OAuth setup details, see [`DEPLOYMENT.md`](DEPLOYMENT.md).

## Security and Configuration

- API keys and database credentials belong in environment variables, not source control.
- Google sign-in requires a configured OAuth Web client ID in the frontend and backend.
- Configure the allowed frontend origin to match the deployed frontend URL.
- Repository access is scoped to public GitHub URLs in this version.
- For deployment, configure a persistent database and appropriate persistent storage for indexed repository data when supported by the hosting provider.

## Testing

The backend includes a pytest test suite. From the project root, run:

```powershell
python -m pytest
```

## Future Enhancements

Potential extensions include broader language support, richer code navigation, more retrieval evaluation, and additional repository-analysis capabilities.

## Author

**Deepak**

GitHub: [deepak-linkedin](https://github.com/deepak-linkedin)
