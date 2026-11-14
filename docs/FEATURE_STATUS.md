# Feature status

## Connected to the backend
- Account signup, login, current-user lookup, and sign-out. Signup starts an authenticated session immediately, the same credentials work after sign-out, and every account keeps its own private documents. The local SQLite database lives in `backend/` regardless of the launch folder.
- Per-user document upload, listing, download, and deletion.
- Persisted language, six color palettes with Light/Dark modes, and companion selection.
- PDF information, merge, split, rotate, remove/extract pages, organize pages (reorder/rotate/remove), scan photos to a multi-page PDF, password protect/unlock, text extraction, and content-stream compression.
- PDF page numbering, watermark, crop, form-field filling, typed/image signatures, text comparison, repair, alternate/mix, split by bookmarks/half/size/text, flatten, Bates numbering, bookmarks, metadata editing, image extraction, flip, grayscale, header/footer, N-up, rename, resize, annotation removal, and deskew.
- PDF Studio page editing, reading, and annotation, plus AI question generation through the configured backend LLM provider.
- Authenticated AI summary and document-grounded chat for saved PDF, DOCX, TXT, and Markdown files.
- Text and file translation into 12 supported languages plus Tanglish when `LLM_API_KEY` is configured.
- Browser speech recognition and speech playback controls for chat responses; available language voices depend on browser/OS support.
- Six editable PDF templates with live form preview, modern/classic/compact layouts, six accent palettes, and optional resume photo.
- Searchable and filterable document history with per-file download, delete, and "Use with AI" actions.

The frontend exposes these flows in the workspace, PDF Studio, AI Documents, templates, document history, companion settings, and assistant panel. AI Documents embeds its character assistant in the page and does not show the global floating assistant. Successful file actions trigger an encouraging, dismissible message from the selected companion. The API reports a configuration error when no LLM key is available rather than returning a fake AI result.

## Catalogue items that still need provider configuration
OCR PDF and Request Signature are not marked ready: the selected OCR API and email/e-sign provider details have not been configured. The UI explains this rather than claiming success. AI question generation requires `LLM_API_KEY` and reports a configuration/provider error when unavailable.

Translation currently returns translated text and does not preserve the source document's exact layout. Speech input/output uses built-in browser/OS support, not a dedicated speech provider. Template designs are original Vertex Docs layouts; photo uploads are supported in the resume template. Companion choices use the built-in Robo, Nova, Finn, Milo, Pip, and Wiz characters; selected characters and palette preferences sync to the signed-in account.

## Local API verification
Run `python -m unittest discover -s tests -p "test_*.py" -v` from `backend/` to verify sign-in persistence, owner isolation, six PDF templates including a resume photo, and the explicit missing-LLM-key behavior. Use `/docs` on the local API to inspect the available routes.
