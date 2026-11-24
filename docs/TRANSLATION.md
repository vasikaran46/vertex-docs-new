# Translation, Humanizer and AI setup

## Why translation said "not translating"
Translation used to depend entirely on the chat model in `backend/.env` (a small local Ollama model). That model is
weak at Indian languages, and a local Ollama does not exist on Render. Translation now goes through a provider chain
(`backend/app/translation_engine.py`); the chat model is only the last resort.

## Provider order (`TRANSLATION_PROVIDERS`)
1. **google** – Google Cloud Translation. Set `GOOGLE_TRANSLATE_API_KEY`. Supports en, ta, hi, ml, te, kn, ja, de, sa, bn, fr, es.
   Tanglish = Tamil translation transliterated to Latin letters.
2. **indictrans** – your own AI4Bharat IndicTrans2 service at `INDICTRANS_URL`.
   Contract: `POST {"texts": ["..."], "src_lang": "eng_Latn", "tgt_lang": "tam_Taml"}` → `{"translations": ["..."]}`
   (FLORES-200 codes; optional `Authorization: Bearer INDICTRANS_TOKEN`). IndicTrans2 needs a GPU/large RAM host, so it
   will not fit Render's free tier; host it elsewhere (e.g. a Hugging Face Space) and point `INDICTRANS_URL` at it.
3. **argos** – offline Argos Translate (`pip install argostranslate` + install language packs). Only pairs with installed packs are used.
4. **google_free** – unofficial keyless endpoint, only if `TRANSLATION_ALLOW_UNOFFICIAL_GOOGLE=true`. Development only.
5. **llm** – the configured chat model.

If a provider fails (bad key, quota, network) the next one is tried; if everything fails the API returns the reason.
Open **Language Bridge** → the language check shows which engine is active.

## Humanizer
Tries the chat model first (45 s timeout, output sanity-checked). If no model is configured or it fails, a built-in
rule-based editor rewrites English text (wordy phrases, contractions by style, long-sentence splitting). Non-English
text is round-tripped through the translation engine. The response includes `engine` and a `notice`.

## AI Documents speed
Extracted text is cached, only passages relevant to the question are sent to the model, and if no model is available the
answer is built from the document's own best-matching sentences.

## Deploying on Render
Backend (Web Service): root `backend`, build `pip install -r requirements.txt`, start
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set the variables from `backend/.env.example` in the Render dashboard.
Frontend (Static Site): root `frontend`, build `npm install && npm run build`, publish `dist`, env `VITE_API_URL=https://<your-backend>.onrender.com`
(plus your `VITE_SUPABASE_*` values). Add the frontend URL to `CORS_ORIGINS`.
