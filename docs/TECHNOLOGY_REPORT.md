# Vertex Docs – Technology Report (Language Bridge, Vertex Assistant, platform)

**How to read the Status column**
- **Verified in code** = I read it in the project files you gave me.
- **Verified by test** = I ran it (sandbox, mocked/stand-in services only).
- **Reported by you / not in zip** = you described it, but the files I received do not contain it, so I could not inspect it.
- **Run `python backend/scripts/diagnose.py`** on your computer to see what is *actually installed and responding right now*. Nothing below
  should be trusted from `.env` alone.

## 1. Language Bridge (translation)

| Technology | Purpose | Installed / configured | Local or cloud | Languages | Actually working? | Endpoint / model |
|---|---|---|---|---|---|---|
| IndicTrans2 service | Main translation for Indian languages | **Reported by you / not in zip.** No service code, no `INDICTRANS_URL`, no `TRANSLATION_PROVIDERS` exist in the uploaded `.env`. Client for it now exists in `translation_engine.py` | Local (port 8001) | en, ta, hi, bn, kn, ml, te (+ sa if your model has it) | Client **verified by test** against a stand-in service. Your real service: unknown until `diagnose.py` | `INDICTRANS_URL=http://localhost:8001/translate` |
| IndicTransToolkit, PyTorch (CPU) | Pre/post-processing and running the model | Reported by you; lives in the 8001 service's own environment (the zip's virtualenvs are empty shells) | Local | – | Not checkable from the zip | – |
| Argos Translate | Offline fallback | Client added; package **not** in `requirements.txt` | Local | Only pairs whose language packs are installed. Argos has no Tamil/Telugu/Malayalam/Kannada models by default | Unknown until `diagnose.py` | provider name `argos` |
| Google Cloud Translation | Cloud provider | Client added; needs `GOOGLE_TRANSLATE_API_KEY` (not in uploaded `.env`) | Cloud (internet) | en ta hi ml te kn ja de sa bn fr es | Verified by test with a mocked response only | `translation.googleapis.com/language/translate/v2` |
| Google free | Keyless fallback | Enabled when `google_free` is listed in `TRANSLATION_PROVIDERS` | Cloud (internet) | Same as Google | Unofficial endpoint, can be rate-limited | `translate.googleapis.com` |
| Chat model (LLM) | Last-resort translation | Configured | Local (Ollama) in your `.env` | Any, weak for Indic with a 3B model | Only while Ollama runs | `llama3.2:latest` |

### What was active in the files you uploaded
The **only** translation path was the chat model (Ollama `llama3.2`). IndicTrans2, Argos and the Google options were not in the code.
That is why translation was weak/failing. The engine now tries providers in this order (override with `TRANSLATION_PROVIDERS`):

**IndicTrans2 → Argos → Google Cloud → Google free → chat model**

Unavailable providers are skipped quietly; a provider that errors passes control to the next one; if all fail you get the reasons.

### Unsupported pairs
- IndicTrans2: **ja, de, fr, es** (handled by Google / Argos / chat model). Indic→Indic is done by pivoting through English (two calls).
  Tanglish = Tamil from IndicTrans2 + transliteration to Latin letters (approximate, not natural chat-style Tanglish).
- Argos: anything without an installed pack (check with `diagnose.py`).
- Auto-detect: IndicTrans2 needs a known source; the app detects Indian scripts automatically but cannot tell Spanish from French.

## 2. Vertex Assistant (chatbot)

| Part | Detail | Status |
|---|---|---|
| UI | `frontend/src/features/assistant/VertexAssistant.tsx` | Verified in code |
| Active API | `POST /api/chat/message` (also `/api/chat/conversations`, `/attachments`, `/convert`) in `backend/app/chatbot/routes.py` | Verified in code. The older `/api/ai/chat*` routes are a second, separate implementation |
| Reply type | **Server-sent events streaming** (`stream: true`) with a normal JSON fallback | Verified in code and by test |
| Memory | Tables `AssistantConversation` / `AssistantMessage`; last 10 messages are sent back to the model; titles auto-generated | Verified in code |
| Documents | Attachments are read and injected into the prompt; tools below | Verified in code |
| Tools | `convert_document`, `read_document`, `get_document_info`, `summarize_document`, `calculator` (safe expression evaluator) + a deterministic "convert to X" fast path that needs no model | Verified in code |
| Summaries / Q&A | Summaries are **local extractive** (no model needed). Document chat uses the model, falls back to the document's own sentences | Verified by test |
| Active model in uploaded `.env` | `LLM_MODEL=llama3.2:latest` via `LLM_BASE_URL=http://localhost:11434/v1` (Ollama), key `ollama` | Verified in code/`.env` |
| `inclusionai/ling-3.2-flash:free`, `google/gemma-4-31b-it:free` | **Defined in code, not active.** They are appended only when *every* model in `LLM_MODEL` ends with `:free`, and (before this update) only the old `/api/ai/*` routes used that list – the assistant UI used a single model. No OpenRouter base URL or key was set in the uploaded `.env` | Verified in code |

### What changed in this update
`/api/chat/message` now uses the same model list: it tries each model in `LLM_MODEL` (plus the two free fallbacks when all are `:free`), retries a
model **without tools** when the provider says it does not support them (common on free OpenRouter models), and reports a rejected key clearly.
Verified by 5 tests with mocked providers. Whether *your* key and those model names currently work on OpenRouter can only be confirmed by `diagnose.py`
(free model names come and go).

## 3. Main application

| Technology | Status | Notes |
|---|---|---|
| React, TypeScript, Vite | In `package.json` as `latest` (unpinned) | Pin versions before production; `latest` can break a future install |
| Python / FastAPI / Uvicorn | In `requirements.txt` | Venvs in the zip were created on Python 3.12 (Windows) |
| SQLAlchemy + Alembic | Present, migrations folder exists | |
| SQLite | `vertex_docs.db` exists | Default only when `DATABASE_URL` is empty |
| Supabase / PostgreSQL | `DATABASE_URL`, `SUPABASE_*` are set in the uploaded `.env` | So Postgres is the active database there |
| JWT auth | `python-jose`; legacy tokens signed with `SECRET_KEY` | **`SECRET_KEY` was not set → falls back to a public default.** Set a long random value |

## 4. Local vs internet
- **Local, no internet:** IndicTrans2 service, Argos, Ollama, extractive summaries, humanizer fallback, all PDF tools, template editing.
- **Needs internet:** Google / Google free, OpenRouter (any hosted LLM), Supabase.
- **Needs software on your PC:** LibreOffice (Word/PowerPoint/Excel conversions), Tesseract (OCR). `diagnose.py` checks both.

## 5. Variables required (names only)
`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SECRET_KEY`, `CORS_ORIGINS`,
`LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`,
`TRANSLATION_PROVIDERS`, `INDICTRANS_URL`, `INDICTRANS_TOKEN` (optional), `INDICTRANS_TIMEOUT` (optional, seconds),
`GOOGLE_TRANSLATE_API_KEY` (optional), `TRANSLATION_ALLOW_UNOFFICIAL_GOOGLE` (optional).
Frontend: `VITE_API_URL` (**must be the backend, port 8000**), `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`.

## 6. The most likely cause of "nothing works"
`frontend/.env.example` set `VITE_API_URL=http://localhost:8001`. 8001 is the **translation service**, not the app backend, so if that
value was copied into `frontend/.env`, every login, upload, conversion and translation request goes to the wrong server. The app now shows a red
"Backend not connected" banner in that situation, and the example file is corrected to 8000.

## 7. Translation flow (simple language)
1. You type text or upload a file. A PDF/Word file is first read into text (OCR if it is a scan).
2. The app splits long text into pieces and sends them to the backend (`/api/ai/translate`).
3. The backend asks IndicTrans2 first. If that language pair is supported and the service answers, that is the result.
4. If not (service off, unsupported language like Japanese, error), it moves to Argos, then Google, then Google free, then the chat model.
5. The pieces are joined back together, checked, and shown. You can edit, download (PDF, Word, text...) and a notification is added.

## 8. Chatbot flow (simple language)
1. You send a message (and optionally attach files). It is saved into your private conversation.
2. If you simply asked to "convert to X", the server does it directly, with no AI involved.
3. Otherwise the server sends your message, the last 10 messages and the attached document text to the model, along with the list of tools.
4. If the first model is unavailable or cannot use tools, the server tries the next model / retries without tools.
5. If the model asks for a tool (calculate, read, summarise, convert), the server runs it and gives the result back to the model.
6. The final answer streams to your screen word by word and is saved to the conversation history.
