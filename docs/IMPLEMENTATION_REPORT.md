# Vertex Docs — Implementation Report (Round 1)

This round implements a **subset** of the 28-module specification. Nothing below is marked
complete unless it was built and tested as described. Items not listed under "Completed" were
**not done** in this round.

## 1. Completed (backend tested, frontend type-checked and built)

| Module | What now works |
|---|---|
| 1 Home | Recent documents: click the name to open; Open / Edit / Preview / Use with AI / Download / Delete buttons. Bell icon beside the moon with real notifications (read, mark-all-read, dismiss, clear). Moon icon already opened the Theme page (unchanged). |
| 5 Translation | Mixed-language prompt (every language in the document is translated), automatic strict retry when output still contains other-language text, warnings shown to the user. **Check language availability** button live-tests the 12 languages against your AI model and reports which are not reliable. "Download" buttons replaced with **Export As** (TXT, DOCX, PDF, PPTX, HTML, MD, RTF, JSON). Accept/Reject Changes and revised-text flow were already present and are unchanged. |
| 6 / 17 OCR | `POST /api/pdf/ocr` + `GET /api/pdf/ocr/status`. Page-by-page, multi-page, text-layer pages are not re-scanned, unreadable pages are reported (never faked), clear error if Tesseract is missing. OCR PDF tool now has a real panel with copy icon, Export As, and "Use text in AI Documents". |
| 10 Humanizer | Upload accepts every format the backend can read (24 extensions; the UI still shows only PDF/DOCX/TXT chips). The duplicate download icons are replaced by one Export As control (TXT, DOCX, PDF, PPTX, ...). |
| 12 Document History | Persistent `history_events` table. Upload time, file type, file name, operation, conversion, edit, share and signature events are stored and survive refresh. Actions: Open, Preview, Share, Annotate, Use with AI, Download, Delete. Filterable Activity list with per-entry delete. |
| 13 Settings | Pollachi, Tamil Nadu, India opens Google Maps. Everything else in Settings is untouched. |
| 19 PDF Annotator | Highlight, box, pen, text, eraser, undo. Annotations stored per document and page in the database, autosaved, restored on reopen and after refresh, and burned into the downloaded PDF. |
| 20 Share PDF | Share PDF tool opens Document History. Share creates a tokenised link with expiry, optional recipient e-mail, download counter, revoke. |
| 21 Request Signature | Choose a PDF, enter signer details, request is saved with status (pending / signed / declined / cancelled / expired). Signer opens `?sign=TOKEN` (no account), reviews the PDF, types a signature; a signed copy is stamped and saved to the owner's workspace. |

## 2. NOT done in this round

2 (Word-like PDF Studio editor), 3 (Export As 12+ formats on PDF tools, PDF info result view, extract-text copy icon), 4 (new conversion formats), 7 (Convert page "search + categories only" initial view, removing Summarizer/Translator from AI category), 8, 9 (100 Word-editor tools and dedicated Word Editor), 11 (Canva-like template editor), 14, 15 (chatbot compact UI/greeting/voice), 16 (Compare PDF was not changed or re-verified), 18 (PDF Reader), 22 (only Share PDF navigation done), the Theme/Settings tab restructure.

## 3. Fixes to existing problems found along the way
* `supabase` was imported but missing from `requirements.txt` (backend would not start on a clean install). Added.
* `main.py` loaded `.env` with `override=True` and ignored `VERTEX_IGNORE_ENV_FILE`, so the test-suite connected to the real Supabase database. Now honoured.
* Uploads failed with HTTP 502 whenever Supabase Storage was not configured. Upload/delete now fall back to local `backend/storage` (matching read), and path traversal is blocked.
* `backend/.env` and `.env.backup` containing real keys were inside the zip. They are **not** included in the output zip. Copy your own `.env` into `backend/`. Rotate those keys if the original zip was shared.

## 4. Database changes
New tables, created automatically at startup by the existing `create_all` (no existing table altered):
`history_events`, `notifications`, `document_shares`, `signature_requests`, `pdf_annotation_sets`.

## 5. APIs added
`/api/notifications` (list, read, read-all, delete, clear) · `/api/history/events`, `/api/history/documents` ·
`/api/documents/{id}/share|shares|text|page/{n}|annotations|annotated-pdf` · `/api/shares/{id}` · `/api/shared/{token}` ·
`/api/signatures` (+ `/public/{token}`, `/document`, `/sign`, `/decline`, `/{id}/cancel`) ·
`/api/export/text`, `/api/export/formats` · `/api/translation/languages` · `/api/pdf/ocr`, `/api/pdf/ocr/status`.

## 6. Tests performed
* Backend: **140 tests pass** (97 original + 43 new) — history, notifications, sharing, signatures end-to-end (including stamped PDF content), annotations (persist, validate, burn into PDF), OCR against real Tesseract (scanned multi-page, image, blank page), export of every format, translation retry/warning logic and availability probe (provider mocked).
* Frontend: `tsc --noEmit` and `vite build` pass.
* **Not performed:** browser click-through of the new UI (no browser was available). Please test the bell, Export As, Share dialog, annotator and signing page manually.

## 7. Needs configuration / external services
* **Tesseract** + language data (`eng`, `tam`, `hin`, …) for OCR. Without it OCR reports the reason instead of failing silently.
* **SMTP_*** variables for e-mailing share links / signature requests. Without them links are still created and the UI tells the user to send the link themselves; it never claims an e-mail was sent.
* **PUBLIC_APP_URL / PUBLIC_API_URL** so generated links point at your real hosts.
* Translation quality depends on the Ollama model. `llama3.2` is weak at Tamil, Malayalam, Telugu, Kannada, Bengali, Sanskrit and Japanese; use the availability check and consider a stronger model.

## 8. Known limitations
* Signatures are typed e-signatures stamped on the last page; they are not cryptographic/PKI signatures.
* Opening non-PDF documents in PDF Studio loads their text (formatting is simplified).
* Annotator supports one set per document (no multi-user collaboration).
* Stray `*.backup` files from the original project were left in place.
