"""
Router AI centralizzato con fallback automatico e tracking utilizzo giornaliero.

Logica di fallback per task testo (default):
    Gemini < 1.400 → Groq account1 < 900 → Groq account2 < 900 → LLMQuotaExceededError

Per task vision/OCR: solo Gemini (Groq non supporta immagini).
    Se Gemini esaurito → lancia LLMQuotaExceededError (il caller gestisce Tesseract).

Per task PDF diretto: Gemini (PDF nativo) → testo estratto + Groq via generate_text().

L'ordine dei provider per ogni tipo di funzione è configurabile dal pannello admin
tramite config_maps (map_key='ai_provider_order', k=task_type, v=JSON array).

Contatori reset automatico: la tabella ai_usage ha PK (provider, date) →
ogni nuovo giorno crea una riga nuova, le vecchie restano come log storico.
"""
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Limiti giornalieri (con margine di sicurezza) ───────────────────────────
DAILY_LIMITS: dict[str, int] = {
    "gemini": 1400,
    "groq1":   900,
    "groq2":   900,
}

# Provider che supportano solo testo (nessuna immagine/PDF diretto)
_TEXT_ONLY_PROVIDERS = {"groq1", "groq2"}

# Ordine predefinito se config_maps non è ancora seedato
_DEFAULT_ORDER: dict[str, list[str]] = {
    "ocr":           ["gemini", "tesseract"],
    "pdf_analysis":  ["gemini", "groq1", "groq2"],
    "text_analysis": ["gemini", "groq1", "groq2"],
    "machine_type":  ["gemini", "groq1", "groq2"],
    "url_rule":      ["gemini", "groq1", "groq2"],
    "prompt_rule":   ["gemini", "groq1", "groq2"],
    "quality_check": ["gemini", "groq1", "groq2"],
}

# Modelli Groq
_GROQ_MODEL_FULL = "llama-3.3-70b-versatile"   # task complessi (analisi, machine_type)
_GROQ_MODEL_FAST = "llama-3.1-8b-instant"       # task leggeri (url_rule, prompt_rule, quality)

# Modello Gemini
_GEMINI_MODEL = "gemini-2.5-flash"


class LLMQuotaExceededError(Exception):
    """Tutti i provider disponibili hanno superato la quota giornaliera."""


class LLMRouter:
    """
    Router centralizzato per tutte le chiamate AI del progetto.
    Gestisce fallback, tracking utilizzo e selezione provider per tipo di task.
    """

    # Cache in-memory dei contatori (provider → (count, timestamp))
    # TTL 30s: evita una SELECT per ogni chiamata AI
    _usage_cache: dict[str, tuple[int, float]] = {}
    _CACHE_TTL = 30.0

    # Cache ordine provider (task_type → (order_list, timestamp))
    _order_cache: dict[str, tuple[list[str], float]] = {}
    _ORDER_CACHE_TTL = 60.0

    # ── Tracking utilizzo ─────────────────────────────────────────────────────

    def _get_cached_usage(self, provider: str) -> Optional[int]:
        entry = self._usage_cache.get(provider)
        if entry and (time.monotonic() - entry[1]) < self._CACHE_TTL:
            return entry[0]
        return None

    def _set_cached_usage(self, provider: str, count: int) -> None:
        self._usage_cache[provider] = (count, time.monotonic())

    def invalidate_usage_cache(self) -> None:
        """Invalida la cache dei contatori (utile per test e dopo PUT admin)."""
        self._usage_cache.clear()

    def invalidate_order_cache(self) -> None:
        """Invalida la cache dell'ordine provider (chiamata dopo PUT admin)."""
        self._order_cache.clear()

    async def _get_today_usage(self, provider: str) -> int:
        cached = self._get_cached_usage(provider)
        if cached is not None:
            return cached
        try:
            from app.services.db_pool import get_conn
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT request_count FROM ai_usage WHERE provider = %s AND date = CURRENT_DATE",
                        (provider,),
                    )
                    row = cur.fetchone()
                    count = row[0] if row else 0
            self._set_cached_usage(provider, count)
            return count
        except Exception as e:
            logger.warning("llm_router: impossibile leggere ai_usage per %s: %s", provider, e)
            return 0

    async def _increment_usage(self, provider: str) -> None:
        """Incrementa atomicamente il contatore giornaliero per il provider."""
        try:
            from app.services.db_pool import get_conn
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO ai_usage (provider, date, request_count, updated_at)
                        VALUES (%s, CURRENT_DATE, 1, NOW())
                        ON CONFLICT (provider, date)
                        DO UPDATE SET
                            request_count = ai_usage.request_count + 1,
                            updated_at    = NOW()
                        RETURNING request_count
                        """,
                        (provider,),
                    )
                    new_count = cur.fetchone()[0]
                conn.commit()
            self._set_cached_usage(provider, new_count)
        except Exception as e:
            logger.warning("llm_router: impossibile incrementare ai_usage per %s: %s", provider, e)

    # ── Selezione provider ─────────────────────────────────────────────────────

    async def _get_order(self, task_type: str) -> list[str]:
        """Legge l'ordine provider dal DB (con cache 60s). Fallback ai default."""
        entry = self._order_cache.get(task_type)
        if entry and (time.monotonic() - entry[1]) < self._ORDER_CACHE_TTL:
            return entry[0]
        try:
            from app.services.config_service import get_map
            val = get_map("ai_provider_order").get(task_type)
            if val and isinstance(val, list):
                self._order_cache[task_type] = (val, time.monotonic())
                return val
        except Exception as e:
            logger.debug("llm_router: get_order fallback per %s: %s", task_type, e)
        order = _DEFAULT_ORDER.get(task_type, ["gemini", "groq1", "groq2"])
        self._order_cache[task_type] = (order, time.monotonic())
        return order

    async def _pick_provider(self, task_type: str, vision: bool = False) -> str:
        """
        Ritorna il primo provider disponibile per il task_type dato.
        Lancia LLMQuotaExceededError se tutti esauriti.
        vision=True esclude i provider solo-testo.
        """
        order = await self._get_order(task_type)
        for provider in order:
            if provider == "tesseract":
                # Tesseract è locale, senza quota — ritornarlo come segnale
                return "tesseract"
            if vision and provider in _TEXT_ONLY_PROVIDERS:
                continue
            limit = DAILY_LIMITS.get(provider)
            if limit is None:
                continue
            usage = await self._get_today_usage(provider)
            if usage < limit:
                return provider
        raise LLMQuotaExceededError(
            "Limite giornaliero raggiunto per tutti i provider AI, riprova domani."
        )

    # ── Chiamate AI ────────────────────────────────────────────────────────────

    async def generate_text(
        self,
        task_type: str,
        prompt: str,
        system: Optional[str] = None,
        fast: bool = False,
        max_tokens: int = 8192,
    ) -> str:
        """
        Genera testo con fallback automatico tra i provider disponibili.
        fast=True usa il modello Groq veloce (llama-3.1-8b-instant) per task leggeri.
        """
        provider = await self._pick_provider(task_type)
        await self._increment_usage(provider)

        if provider == "gemini":
            return await self._call_gemini_text(prompt, system, max_tokens)
        elif provider in ("groq1", "groq2"):
            return await self._call_groq_text(provider, prompt, system, max_tokens, fast)
        else:
            raise LLMQuotaExceededError("Nessun provider AI di testo disponibile.")

    async def generate_vision(self, image_b64: str, prompt: str, max_tokens: int = 1024) -> str:
        """
        Genera testo da immagine (solo Gemini supporta vision).
        Lancia LLMQuotaExceededError se Gemini è esaurito — il caller gestisce il fallback
        (es. Tesseract per OCR).
        """
        provider = await self._pick_provider("ocr", vision=True)
        if provider == "tesseract":
            raise LLMQuotaExceededError("Gemini esaurito — usa Tesseract come fallback.")
        await self._increment_usage(provider)
        return await self._call_gemini_vision(image_b64, prompt, max_tokens)

    async def generate_with_pdf(
        self,
        task_type: str,
        pdf_b64: str,
        pdf_text_fallback: str,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 16000,
    ) -> str:
        """
        Analisi PDF: prova prima con Gemini (PDF nativo).
        Se Gemini è esaurito, usa il testo estratto (pdf_text_fallback) con il provider di testo.
        """
        order = await self._get_order(task_type)
        # Se Gemini è primo nell'ordine e disponibile → PDF nativo
        if order and order[0] == "gemini":
            usage = await self._get_today_usage("gemini")
            if usage < DAILY_LIMITS.get("gemini", 1400):
                await self._increment_usage("gemini")
                return await self._call_gemini_pdf(pdf_b64, prompt, system, max_tokens)

        # Fallback: testo estratto + router testo
        if not pdf_text_fallback:
            raise LLMQuotaExceededError(
                "Gemini esaurito e nessun testo estratto disponibile per il fallback."
            )
        return await self.generate_text(task_type, prompt, system, max_tokens=max_tokens)

    # ── Implementazioni provider ───────────────────────────────────────────────

    async def _call_gemini_text(
        self, prompt: str, system: Optional[str], max_tokens: int
    ) -> str:
        from app.config import settings
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.gemini_api_key)
        config_kwargs: dict = dict(
            max_output_tokens=max_tokens,
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        if system:
            config_kwargs["system_instruction"] = system
        response = await client.aio.models.generate_content(
            model=_GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return response.text or ""

    async def _call_gemini_vision(
        self, image_b64: str, prompt: str, max_tokens: int
    ) -> str:
        import base64 as _b64
        from app.config import settings
        from google import genai
        from google.genai import types

        b64_data = image_b64
        media_type = "image/jpeg"
        if image_b64.startswith("data:"):
            header, b64_data = image_b64.split(",", 1)
            if "png" in header:
                media_type = "image/png"
            elif "webp" in header:
                media_type = "image/webp"
        img_bytes = _b64.b64decode(b64_data)
        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model=_GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type=media_type),
                prompt,
            ],
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return response.text or ""

    async def _call_gemini_pdf(
        self, pdf_b64: str, prompt: str, system: Optional[str], max_tokens: int
    ) -> str:
        from app.config import settings
        from google import genai
        from google.genai import types
        import base64 as _b64

        pdf_bytes = _b64.b64decode(pdf_b64)
        client = genai.Client(api_key=settings.gemini_api_key)
        config_kwargs: dict = dict(
            max_output_tokens=max_tokens,
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        if system:
            config_kwargs["system_instruction"] = system
        response = await client.aio.models.generate_content(
            model=_GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                prompt,
            ],
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return response.text or ""

    async def _call_groq_text(
        self,
        provider: str,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        fast: bool,
    ) -> str:
        from app.config import settings
        from groq import AsyncGroq

        api_key = settings.groq_api_key if provider == "groq1" else settings.groq_api_key2
        if not api_key:
            raise LLMQuotaExceededError(f"API key non configurata per {provider}.")

        model = _GROQ_MODEL_FAST if fast else _GROQ_MODEL_FULL
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        client = AsyncGroq(api_key=api_key)
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.0,
        )
        return response.choices[0].message.content or ""

    # ── Utility: lettura contatori per admin ──────────────────────────────────

    async def get_all_usage_today(self) -> dict[str, dict]:
        """Ritorna i contatori odierni per tutti i provider (usato dall'endpoint admin)."""
        result = {}
        for provider, limit in DAILY_LIMITS.items():
            # Forza lettura da DB (invalida cache per avere dato fresco)
            try:
                from app.services.db_pool import get_conn
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT request_count FROM ai_usage WHERE provider = %s AND date = CURRENT_DATE",
                            (provider,),
                        )
                        row = cur.fetchone()
                        count = row[0] if row else 0
                self._set_cached_usage(provider, count)
            except Exception:
                count = self._get_cached_usage(provider) or 0
            result[provider] = {
                "usage": count,
                "limit": limit,
                "available": count < limit,
            }
        return result


# Singleton — importato da tutti i servizi
llm_router = LLMRouter()
