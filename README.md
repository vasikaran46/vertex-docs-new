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
uvicorn app.main:app --reload --port 8000
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

## Tests
Run the backend API tests with:
```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

## Important
These are original Vertex Docs templates, not downloaded Canva assets. Translation produces translated text, not a layout-preserving replacement PDF. Speech uses built-in browser/OS speech support rather than a hosted voice service. This does not claim all 72 processing tools are production-complete; unavailable catalog tools remain marked as requiring an engine. See [docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md).
