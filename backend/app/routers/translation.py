import asyncio
import time

from fastapi import APIRouter, Depends

from ..security import current_user
from ..translation_engine import GOOGLE_CODES, FLORES_CODES, ARGOS_CODES, configured_providers, probe_providers, provider_order
from ..translation_quality import PROBE_SOURCE_FOR_ENGLISH, PROBE_TEXT, verify_probe
from .ai import LANGUAGE_NAMES, ai_completion, llm_models, llm_setting

router = APIRouter(prefix="/api/translation", tags=["Translation"])

# The 12 languages requested for the initial release, in the requested order.
INITIAL_LANGUAGES = ["en", "ta", "hi", "ml", "te", "ja", "de", "sa", "kn", "bn", "fr", "es"]
_CACHE: dict[tuple[str, str], tuple[float, list[dict]]] = {}
CACHE_SECONDS = 600


def _provider_state() -> tuple[bool, str, str]:
    key = llm_setting("LLM_API_KEY")
    base = llm_setting("LLM_BASE_URL", "https://api.openai.com/v1")
    return bool(key), ",".join(llm_models()), base


async def _probe(code: str) -> dict:
    name = LANGUAGE_NAMES[code]
    if code == "en":
        system = f"Translate the user's text into {name}. Return only the translation."
        text = PROBE_SOURCE_FOR_ENGLISH
    else:
        system = f"Translate the user's text into {name}. Return only the translation."
        text = PROBE_TEXT
    try:
        output = await ai_completion([{"role": "system", "content": system}, {"role": "user", "content": text}])
    except Exception as error:  # HTTPException from the provider or network failure
        detail = getattr(error, "detail", None) or "The provider could not be reached."
        return {"code": code, "name": name, "status": "unavailable", "detail": str(detail)}
    ok, detail = verify_probe(code, output)
    return {"code": code, "name": name, "status": "available" if ok else "unavailable", "detail": detail}


@router.get("/languages")
async def languages(probe: bool = False, u=Depends(current_user)):
    """List the supported languages. With probe=true each language is tested against the real provider."""
    engines = configured_providers()
    if engines:
        # A dedicated translation engine is configured: no chat-model probing is needed.
        def supported(code: str, engine: str) -> bool:
            if code == "tanglish":
                return engine in {"google", "google_free"}
            return {"google": code in GOOGLE_CODES, "google_free": code in GOOGLE_CODES,
                    "indictrans": code in FLORES_CODES, "argos": code in ARGOS_CODES}.get(engine, False)

        items = []
        for code in [*INITIAL_LANGUAGES, "tanglish"]:
            usable = [engine for engine in engines if supported(code, engine)]
            if usable:
                items.append({"code": code, "name": LANGUAGE_NAMES[code], "status": "available",
                              "detail": f"Translated with {usable[0].replace('_', ' ')}."})
            elif llm_setting("LLM_API_KEY"):
                items.append({"code": code, "name": LANGUAGE_NAMES[code], "status": "unverified",
                              "detail": "No translation engine covers this language; the chat model will be used."})
            else:
                items.append({"code": code, "name": LANGUAGE_NAMES[code], "status": "unavailable",
                              "detail": "None of the configured translation engines supports this language."})
        return {"provider_configured": True, "model": "engines: " + ", ".join(engines), "engines": engines,
                "probed": False, "languages": items}
    configured, model, base = _provider_state()
    if not configured:
        return {
            "provider_configured": False, "model": model, "probed": False,
            "languages": [
                {"code": code, "name": LANGUAGE_NAMES[code], "status": "unavailable",
                 "detail": "No translation engine is configured. Add GOOGLE_TRANSLATE_API_KEY (recommended) to backend/.env — see docs/TRANSLATION.md."}
                for code in INITIAL_LANGUAGES
            ],
        }
    if not probe:
        return {
            "provider_configured": True, "model": model, "probed": False,
            "languages": [
                {"code": code, "name": LANGUAGE_NAMES[code], "status": "unverified",
                 "detail": "Provider is configured. Run the availability check to verify this language."}
                for code in INITIAL_LANGUAGES
            ],
        }
    cache_key = (base, model)
    cached = _CACHE.get(cache_key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        results = cached[1]
    else:
        semaphore = asyncio.Semaphore(2)

        async def run(code: str) -> dict:
            async with semaphore:
                return await _probe(code)

        results = await asyncio.gather(*(run(code) for code in INITIAL_LANGUAGES))
        _CACHE[cache_key] = (time.time(), results)
    return {"provider_configured": True, "model": model, "probed": True, "languages": results}


@router.get("/diagnostics")
async def translation_diagnostics(u=Depends(current_user)):
    """Live check of every translation provider, in the order they are tried. Secret values are never returned."""
    providers = await probe_providers()
    return {
        "order": provider_order(),
        "providers": providers,
        "active": next((item["provider"] for item in providers if item.get("working")), None),
        "llm_configured": bool(llm_setting("LLM_API_KEY")),
    }
