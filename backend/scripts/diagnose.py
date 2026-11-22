"""Vertex Docs diagnostic: what is INSTALLED, what is CONFIGURED, and what actually WORKS right now.

Read-only. Installs nothing, changes nothing, never prints secret values.

Run from the backend folder (with your virtualenv active):
    python scripts/diagnose.py            # full report incl. live provider calls
    python scripts/diagnose.py --offline  # skip live network/provider calls
"""

from __future__ import annotations

import asyncio
import importlib.metadata as md
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
OFFLINE = "--offline" in sys.argv

OK, BAD, WARN = "[ OK ]", "[FAIL]", "[ !! ]"


def line(status: str, text: str) -> None:
    print(f"  {status} {text}")


def section(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(3, 66 - len(title)))


def version(*names: str) -> str | None:
    for name in names:
        try:
            return md.version(name)
        except md.PackageNotFoundError:
            continue
    return None


def env(name: str, default: str = "") -> str:
    from app.translation_engine import setting  # honours backend/.env exactly like the app

    return setting(name, default)


SAFE_VALUES = {"LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "TRANSLATION_PROVIDERS", "INDICTRANS_URL", "TRANSLATION_ALLOW_UNOFFICIAL_GOOGLE"}


def host_only(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.netloc else url


def main() -> None:
    print("Vertex Docs diagnostic report")
    print(f"Python {platform.python_version()} on {platform.system()} | backend folder: {BACKEND}")
    env_file = BACKEND / ".env"
    print(f".env file: {'found' if env_file.exists() else 'NOT FOUND (using process environment only)'}")

    # ------------------------------------------------------------------ packages
    section("1. Installed Python packages (installed != working)")
    core = {
        "FastAPI": ("fastapi",), "Uvicorn": ("uvicorn",), "SQLAlchemy": ("sqlalchemy",), "Alembic": ("alembic",),
        "python-jose (JWT)": ("python-jose",), "passlib": ("passlib",), "Supabase client": ("supabase",),
        "httpx": ("httpx",), "psycopg (Postgres)": ("psycopg", "psycopg-binary"), "PyMuPDF": ("PyMuPDF", "pymupdf"),
        "pypdf": ("pypdf",), "ReportLab": ("reportlab",), "python-docx": ("python-docx",),
    }
    for label, names in core.items():
        found = version(*names)
        line(OK if found else BAD, f"{label}: {found or 'NOT INSTALLED'}")

    section("2. Translation model stack")
    ml = {
        "PyTorch": ("torch",), "Transformers": ("transformers",), "IndicTransToolkit": ("IndicTransToolkit", "indictranstoolkit"),
        "SentencePiece": ("sentencepiece",), "Argos Translate": ("argostranslate",),
    }
    for label, names in ml.items():
        found = version(*names)
        line(OK if found else WARN, f"{label}: {found or 'not installed in THIS Python environment'}")
    if version("argostranslate"):
        try:
            from argostranslate import translate as argos

            langs = sorted(language.code for language in argos.get_installed_languages())
            line(OK if langs else WARN, f"Argos language packs installed: {', '.join(langs) if langs else 'NONE (Argos cannot translate until packs are installed)'}")
        except Exception as error:  # noqa: BLE001
            line(BAD, f"Argos could not list languages: {error}")
    print("  note: the IndicTrans2 service (port 8001) normally has its OWN virtualenv; torch/IndicTransToolkit missing here is fine.")

    # ------------------------------------------------------------------ binaries
    section("3. External programs used for conversion / OCR")
    try:
        from app.conversion_service import _libreoffice_executable

        exe = _libreoffice_executable()
        line(OK if exe and Path(exe).exists() or shutil.which(str(exe)) else BAD, f"LibreOffice (Word/PPT/Excel conversions): {exe}")
    except Exception as error:  # noqa: BLE001
        line(BAD, f"LibreOffice NOT found - document conversions will fail ({str(error)[:80]})")
    tess = shutil.which("tesseract")
    line(OK if tess else WARN, f"Tesseract OCR: {tess or 'not on PATH (scanned PDFs/images cannot be read)'}")

    # ------------------------------------------------------------------ env
    section("4. Environment variables (secret values are never shown)")
    wanted = [
        "DATABASE_URL", "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SECRET_KEY", "CORS_ORIGINS",
        "LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY",
        "TRANSLATION_PROVIDERS", "INDICTRANS_URL", "INDICTRANS_TOKEN", "GOOGLE_TRANSLATE_API_KEY", "TRANSLATION_ALLOW_UNOFFICIAL_GOOGLE",
    ]
    for name in wanted:
        value = env(name)
        shown = (host_only(value) if name.endswith("URL") and name in SAFE_VALUES else value) if name in SAFE_VALUES and value else (f"set ({len(value)} chars)" if value else "NOT SET")
        line(OK if value else WARN, f"{name} = {shown}")
    database = env("DATABASE_URL")
    print(f"  database in use: {database.split(':', 1)[0] if database else 'sqlite (default file backend/vertex_docs.db)'}")

    # ------------------------------------------------------------------ llm
    section("5. Chatbot model (what the Vertex Assistant really uses)")
    base = env("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    key = env("LLM_API_KEY")
    try:
        from app.routers.ai import llm_models

        models = llm_models()
    except Exception as error:  # noqa: BLE001
        models = [m.strip() for m in env("LLM_MODEL", "gpt-4o-mini").split(",") if m.strip()]
        line(WARN, f"could not import the app's model list ({error}); using LLM_MODEL only")
    print(f"  provider endpoint: {host_only(base)}")
    print(f"  models tried in this order: {', '.join(models)}")
    if all(m.endswith(':free') for m in models):
        print("  (free OpenRouter fallbacks ling-3.2-flash / gemma-4-31b are appended automatically)")
    elif any(m in {'inclusionai/ling-3.2-flash:free', 'google/gemma-4-31b-it:free'} for m in models):
        pass
    else:
        print("  note: the built-in free fallbacks (ling-3.2-flash, gemma-4-31b) are NOT active because LLM_MODEL has a non-':free' model.")
    if "localhost" in base or "127.0.0.1" in base:
        print("  note: this is a LOCAL model server. It will not exist on Render/hosting, and only works while it is running.")
    active_model = None
    if OFFLINE:
        line(WARN, "skipped live model test (--offline)")
    elif not key:
        line(BAD, "LLM_API_KEY is empty - chatbot cannot answer")
    else:
        for model in models:
            try:
                response = httpx.post(base + "/chat/completions", headers={"Authorization": f"Bearer {key}"}, timeout=60,
                                      json={"model": model, "messages": [{"role": "user", "content": "Reply with the single word: ready"}], "max_tokens": 8})
                if response.status_code == 200:
                    text = (response.json()["choices"][0]["message"].get("content") or "").strip()[:30]
                    line(OK, f"{model}: answered ({text!r})")
                    active_model = active_model or model
                else:
                    line(BAD, f"{model}: HTTP {response.status_code} {response.text[:100]}")
            except Exception as error:  # noqa: BLE001
                line(BAD, f"{model}: {error.__class__.__name__} - {str(error)[:80]}")

    # ------------------------------------------------------------------ translation
    section("6. Translation engines (live test: English -> Hindi)")
    from app.translation_engine import configured_providers, probe_providers, provider_order

    print(f"  order tried: {' -> '.join(provider_order())}")
    print(f"  configured: {', '.join(configured_providers()) or 'none'}")
    active_engine = None
    if OFFLINE:
        line(WARN, "skipped live provider test (--offline)")
    else:
        for item in asyncio.run(probe_providers()):
            if item["provider"] == "llm":
                line(OK if item["configured"] else WARN, "llm: used last, only when every engine above fails")
                continue
            line(OK if item["working"] else (WARN if not item["configured"] else BAD), f"{item['provider']}: {item['detail']}" + (f"  e.g. {item['sample']}" if item.get("sample") else ""))
            if item["working"] and not active_engine:
                active_engine = item["provider"]

    # ------------------------------------------------------------------ services
    section("7. Local services and ports")
    checks = [("Vertex Docs backend", "http://localhost:8000/api/health")]
    url = env("INDICTRANS_URL")
    if url:
        checks.append(("IndicTrans2 service", url.rsplit("/", 1)[0] + "/docs"))
    if "11434" in base:
        checks.append(("Ollama", "http://localhost:11434/api/tags"))
    for label, target in checks:
        if OFFLINE:
            continue
        try:
            code = httpx.get(target, timeout=4).status_code
            line(OK if code < 500 else BAD, f"{label}: reachable at {target} (HTTP {code})")
        except Exception as error:  # noqa: BLE001
            line(BAD, f"{label}: NOT reachable at {target} ({error.__class__.__name__}) - is it running?")
    frontend_env = BACKEND.parent / "frontend" / ".env"
    if frontend_env.exists():
        for raw in frontend_env.read_text(encoding="utf-8").splitlines():
            if raw.startswith("VITE_API_URL="):
                value = raw.split("=", 1)[1].strip()
                bad = value.rstrip("/").endswith(":8001")
                line(BAD if bad else OK, f"frontend/.env VITE_API_URL = {value}" + ("   <-- WRONG: 8001 is the translation service; must be http://localhost:8000" if bad else ""))
    else:
        line(WARN, "frontend/.env not found (the app defaults to http://localhost:8000)")

    # ------------------------------------------------------------------ summary
    section("SUMMARY")
    print(f"  Active translation engine : {active_engine or 'NONE WORKING (or --offline)'}")
    print(f"  Active chatbot model      : {active_model or 'NONE WORKING (or --offline)'}")
    print("  Unsupported by IndicTrans2: ja, de, fr, es (handled by Google / Argos / LLM). Tanglish = Tamil from IndicTrans2 + transliteration.")
    print("  Needs internet            : Google / Google free / OpenRouter (cloud LLM), Supabase")
    print("  Fully local               : IndicTrans2, Argos, Ollama, extractive summaries, humanizer fallback, PDF tools")


if __name__ == "__main__":
    main()
