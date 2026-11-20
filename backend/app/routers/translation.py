import asyncio
import time

from fastapi import APIRouter, Depends

from ..security import current_user
from ..translation_quality import PROBE_SOURCE_FOR_ENGLISH, PROBE_TEXT, verify_probe
from .ai import LANGUAGE_NAMES, ai_completion, llm_models, llm_setting

router = APIRouter(prefix="/api/translation", tags=["Translation"])

# The 12 languages requested for the initial release, in the requested order.
INITIAL_LANGUAGES = ["en", "ta", "hi", "ml", "te", "ja", "de", "sa", "kn", "bn", "fr", "es"]
_CACHE: dict[tuple[str, str], tuple[float, list[dict]]] = {}
CACHE_SECONDS = 600


def _provider_state() -> tuple[bool, str, str]:
    provider = llm_setting("LLM_PROVIDER", "").lower()
    key = llm_setting("LLM_API_KEY")
    is_ollama = provider == "ollama" or not key or key.lower() == "ollama"
    if is_ollama:
        ollama_base = llm_setting("OLLAMA_BASE_URL") or llm_setting("LLM_BASE_URL", "http://127.0.0.1:11434")
        ollama_model = llm_setting("OLLAMA_MODEL") or llm_setting("LLM_MODEL", "llama3.2")
        return True, ollama_model, ollama_base
    base = llm_setting("LLM_BASE_URL", "https://api.openai.com/v1")
    return True, ",".join(llm_models()), base


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
    configured, model, base = _provider_state()
    if not configured:
        return {
            "provider_configured": False, "model": model, "probed": False,
            "languages": [
                {"code": code, "name": LANGUAGE_NAMES[code], "status": "unavailable",
                 "detail": "No AI provider is configured. Add LLM_API_KEY (and LLM_BASE_URL / LLM_MODEL) to backend/.env."}
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
