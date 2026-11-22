# VERTEX DOCS — Full-stack starter

React + TypeScript + Vite frontend; FastAPI backend.

## Included
- Persistent signup/login, JWT-protected API, profile preferences, and owner-scoped document access. Creating an account signs you in immediately; after signing out, use the same email and password to return. Multiple people can keep separate accounts on one device, and each account only sees its own documents.
- Document upload/list/download/delete.
- Working PDF info, merge, split, rotate, remove/extract pages, protect/unlock, text extraction and content-stream compression endpoints.
- AI Documents: summarize a selected workspace file, ask context-aware questions, and translate PDF/DOCX/TXT/Markdown files into any of 12 languages plus Tanglish. AI actions need `LLM_API_KEY`.
- Browser voice input and speech playback for chat and document responses, using the language selected in the workspace. Available voices depend on the browser and operating system.
- Six editable PDF templates (resume, cover letter, business letter, meeting notes, proposal, invoice), with layout/color options and an optional resume photo.
- Searchable, type-filtered document history with private download, delete, and AI actions.
- 72-tool catalogue with backend availability clearly labeled.
- Forest, Rose, Graphite, Cocoa, Amber and Ocean palettes, each with a soft Light/Dark mode; language and six companion choices are saved to account preferences.
- Configurable character companion and friendly operation messages; the global assistant bubble is hidden on AI Documents, where the companion is part of the document chat experience.
- Modular folders and feature-status documentation.

## Run backend (PowerShell)
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --reload-dir app --port 8000
```
API docs: http://localhost:8000/docs

## Run frontend
```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```
Open http://localhost:5173

Add `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` to `backend/.env`.
SQLite is used locally. PostgreSQL can be configured through `DATABASE_URL`.

## Connect the backend to Supabase Postgres

The backend uses SQLAlchemy, so use Supabase's PostgreSQL connection URI. The `psycopg` driver is included in `backend/requirements.txt`; no Supabase client SDK or Supabase API key is required for this database connection.

1. Create a Supabase project and set or note its **database password**.
2. In the Supabase Dashboard, open **Connect** and copy the **Session pooler** connection URI. The backend is a long-running FastAPI service, so use the session pooler (or direct connection if your host supports IPv6). The copied URI provides the correct username, host, port, and database name for your project.
3. Copy `backend/.env.example` to `backend/.env` if you have not already, then replace `DATABASE_URL` with the copied URI. Keep `?sslmode=require` in the connection string. The backend accepts Supabase's `postgresql://` URI format and routes it through psycopg.
4. From `backend`, install the requirements and start/restart the API:

   ```powershell
   pip install -r requirements.txt
   uvicorn app.main:app --reload --reload-dir app --port 8000
   ```

The API creates missing tables from its SQLAlchemy models when it starts. This does not migrate existing SQLite data into Supabase; export/import that data separately if you need to retain it.

### Supabase values you need

- **Database connection URI** from **Connect → Session pooler**. It includes the database username, pooler host, port, and database name.
- **Database password** for the Supabase project's Postgres database. This is the value used in the URI in place of `[YOUR-PASSWORD]`; reset it in the Supabase project settings if you do not know it. URL-encode reserved characters in the password before inserting it into the URI.

This app currently uses its own JWT authentication and connects to Postgres from the backend. It does **not** need the Supabase project URL, publishable/anon key, or secret/service-role key. Never put a database password or service-role/secret key in the frontend. The database connection stores document metadata; uploaded document files remain in the backend's local `backend/storage` folder, so a deployed backend also needs persistent file storage or a separate Supabase Storage integration.

See [Supabase's Postgres connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres) for connection modes and connection-string details.

## Tests
Run the backend API tests with:
```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

## Important
These are original Vertex Docs templates, not downloaded Canva assets. Translation produces translated text, not a layout-preserving replacement PDF. Speech uses built-in browser/OS speech support rather than a hosted voice service. This does not claim all 72 processing tools are production-complete; unavailable catalog tools remain marked as requiring an engine. See [docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md).
