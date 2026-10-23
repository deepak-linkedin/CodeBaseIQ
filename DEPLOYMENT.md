# CodebaseIQ: finish setup and deploy

This version keeps the existing Tree-sitter chunking, local embeddings, ChromaDB, BM25 + reciprocal-rank-fusion retrieval, and Gemini answer generation. It adds public GitHub ingestion, Google sign-in, per-user repository ownership, and PostgreSQL-backed chat history.

## Important scope
- Public GitHub repositories only. Private GitHub and local-folder indexing are intentionally out of scope.
- The backend clones a shallow copy of each public repository into `DATA_DIR/repos/`.
- Conversations, messages, and repository ownership are stored in PostgreSQL when `DATABASE_URL` is configured.
- In local development without `GOOGLE_CLIENT_ID`, the app uses one `local-dev` identity. **Do not deploy with Google authentication disabled** if you need user-private history.
- The Chroma index and cloned repositories live on the backend filesystem. On hosts with ephemeral disks, they may disappear after a restart/redeploy. Attach persistent storage if the hosting plan supports it; otherwise users can reconnect/reindex repositories after the index is lost.

## 1. Local setup

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`:
- Set `GEMINI_API_KEY` to your Gemini API key.
- Keep `GOOGLE_CLIENT_ID` blank for local-only development without login, or configure Google sign-in as below.
- `DATABASE_URL` can stay blank locally; the app uses SQLite at `data/codebaseiq.db`.

Start the backend:

```powershell
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`.

## 2. Enable Google sign-in

1. Open Google Cloud Console and create/select a project.
2. Configure the OAuth consent screen.
3. Create an OAuth Client ID of type **Web application**.
4. Add these authorized JavaScript origins:
   - `http://localhost:5173`
   - your deployed frontend origin, e.g. `https://your-app.vercel.app`
5. Copy the client ID into both:
   - root `.env`: `GOOGLE_CLIENT_ID=...`
   - `frontend/.env`: `VITE_GOOGLE_CLIENT_ID=...`
6. Restart both apps.

The backend verifies the Google ID token and uses its Google `sub` claim as the ownership key. Do not put any client secret or database password in the frontend.

## 3. Use PostgreSQL for persistent chat history

Create a PostgreSQL database (for example, a Supabase project) and copy its connection URI into the backend environment:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE
```

The backend normalizes this URI for the installed `psycopg` driver and creates the required tables at startup. Use the provider's direct or session-pooler connection URI that is compatible with your host.

## 4. Deploy frontend

Deploy `frontend/` to Vercel:
- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variables:
  - `VITE_API_BASE_URL=https://YOUR-BACKEND-URL`
  - `VITE_GOOGLE_CLIENT_ID=YOUR_GOOGLE_WEB_CLIENT_ID`

Add the final Vercel domain to Google OAuth's authorized JavaScript origins.

## 5. Deploy backend

Deploy the repository to a Python host such as Render:
- Build command: `pip install -r requirements.txt`
- Start command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment variables:
  - `GOOGLE_CLIENT_ID` — same Google Web client ID as frontend
  - `DATABASE_URL` — PostgreSQL connection URI
  - `GEMINI_API_KEY` — secret, backend only
  - `GEMINI_MODEL=gemini-3.5-flash-lite`
  - `LLM_PROVIDER=gemini`
  - `FRONTEND_ORIGIN=https://YOUR-VERCEL-DOMAIN`
  - `DATA_DIR=/var/data` if you attach a persistent disk at `/var/data`; otherwise choose a writable path available to the host.

Check `https://YOUR-BACKEND-URL/health`. Ensure the backend's host permits installing the Python dependencies and downloading the Sentence Transformers embedding model. The first startup/indexing may be slow because the embedding model is downloaded.

## 6. Submission smoke test

1. Sign in with Google.
2. Connect a public repository URL, e.g. a repository you own or another public code sample.
3. Wait for indexing to finish.
4. Select the repository in the sidebar and ask a question about a real function/file.
5. Refresh the browser; verify the conversation remains in history.
6. Rename the conversation; refresh and verify the name remains.
7. Click **New conversation**; verify it is blank and no repository is selected.
8. Sign out and sign in as a different Google account; verify the first account's history/repository list is not shown.

## Notes
- The backend requires the `git` executable for public repository cloning.
- The current first version indexes `.py`, `.js`, `.jsx`, `.ts`, and `.tsx` files and skips common generated/vendor directories.
- Keep real `.env` files out of GitHub. The project `.gitignore` excludes environment files, local databases, Chroma data, and cloned repositories.


## Repository indexing progress

Connecting a public GitHub repository creates a short-lived indexing job. The frontend polls its status and displays cloning, parsing, embedding, and indexing progress. Job progress is held in backend memory and is intentionally temporary; repository records and conversation history are stored in the configured SQL database. If the backend process restarts during indexing, retry the repository connection.
