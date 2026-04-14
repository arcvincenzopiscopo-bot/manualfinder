"""
Router AI centralizzato con fallback automatico e tracking utilizzo giornaliero.

Logica di fallback per task testo (default):
    Groq account1 < 900 → Groq account2 < 900 → LLMQuotaExceededError

Per task vision/OCR: Groq Vision (llama-3.2-11b-vision-preview) con account1→account2.
    Se entrambi esauriti → lancia LLMQuotaExceededError (il caller gestisce Tesseract).

Per task PDF:
    Fase 1 — Mistral OCR (mistral-ocr-latest): estrae markdown da PDF (nativo o scansionato).
    Fase 2 — Groq testo: analizza il markdown estratto.
    Se Mistral non disponibile → fallback a testo pdfminer già estratto.

L'ordine dei provider per ogni tipo di funzione è configurabile dal pannello admin
tramite config_maps (map_key='ai_provider_order', k=task_type, v=JSON array).

Contatori reset automatico: la tabella ai_usage ha PK (provider, date) →
ogni nuovo giorno crea una riga nuova, le vecchie restano come log storico.
"""
import asyncio
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Limiti giornalieri (con margine di sicurezza) ───────────────────────────
DAILY_LIMITS: dict[str, int] = {
    "groq1":   900,
    "groq2":   900,
    "mistral": 100,   # ~4 RPM max → 100/giorno conservativo
}

# Provider che supportano solo testo (nessuna immagine)
# Groq ora supporta vision tramite modello dedicato → _TEXT_ONLY_PROVIDERS vuoto
_TEXT_ONLY_PROVIDERS: set[str] = set()

# Ordine predefinito se config_maps non è ancora seedato
_DEFAULT_ORDER: dict[str, list[str]] = {
    "ocr":           ["groq1", "groq2", "tesseract"],
    "pdf_analysis":  ["mistral", "groq1", "groq2"],
    "text_analysis": ["groq1", "groq2"],
    "machine_type":  ["groq1", "groq2"],
    "url_rule":      ["groq1", "groq2"],
    "prompt_rule":   ["groq1", "groq2"],
    "quality_check": ["groq1", "groq2"],
}

# Modelli Groq
_GROQ_MODEL_FULL   = "llama-3.3-70b-versatile"      # task complessi (analisi, machine_type)
_GROQ_MODEL_FAST   = "llama-3.1-8b-instant"          # task leggeri (url_rule, prompt_rule, quality)
_GROQ_VISION_MODEL = "llama-3.2-11b-vision-preview"  # OCR targhe immagini

# Modello Mistral OCR
_MISTRAL_OCR_MODEL = "mistral-ocr-latest"

# Limite caratteri per singola chiamata Groq (Groq TPM 12K ≈ ~16K chars safe)
_PDF_CHUNK_MAX_CHARS = 16000


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

    # Rate limiting Mistral OCR: max 4 RPM (1 ogni 15s) sul modello OCR
    # Usiamo 15s come gap minimo (= 4 RPM conservativo, il limite reale è 2-5 RPM)
    _mistral_last_call: float = 0.0
    _MISTRAL_MIN_INTERVAL = 15.0  # secondi tra una chiamata Mistral e la successiva

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
        order = _DEFAULT_ORDER.get(task_type, ["groq1", "groq2"])
        self._order_cache[task_type] = (order, time.monotonic())
        return order

    async def _pick_provider(self, task_type: str, vision: bool = False) -> str:
        """
        Ritorna il primo provider disponibile per il task_type dato.
        Lancia LLMQuotaExceededError se tutti esauriti.
        vision=True esclude i provider solo-testo (attualmente nessuno).
        """
        order = await self._get_order(task_type)
        for provider in order:
            if provider == "tesseract":
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
        debug_info: Optional[dict] = None,
    ) -> str:
        """
        Genera testo con fallback automatico tra i provider disponibili.
        fast=True usa il modello Groq veloce (llama-3.1-8b-instant) per task leggeri.
        debug_info: se passato, viene popolato con provider scelto, modello e usage.
        """
        order = await self._get_order(task_type)
        provider = await self._pick_provider(task_type)
        await self._increment_usage(provider)
        if debug_info is not None:
            model_id = _GROQ_MODEL_FAST if fast else _GROQ_MODEL_FULL
            debug_info.update({
                "provider": provider,
                "model": model_id,
                "task_type": task_type,
                "order_tried": order,
                "usage_today": {p: (await self._get_today_usage(p)) for p in DAILY_LIMITS},
            })

        if provider in ("groq1", "groq2"):
            return await self._call_groq_text(provider, prompt, system, max_tokens, fast)
        else:
            raise LLMQuotaExceededError("Nessun provider AI di testo disponibile.")

    async def generate_vision(
        self,
        image_b64: str,
        prompt: str,
        max_tokens: int = 1024,
        debug_info: Optional[dict] = None,
    ) -> str:
        """
        Genera testo da immagine usando Groq Vision (llama-3.2-11b-vision-preview).
        Lancia LLMQuotaExceededError se tutti i provider Groq sono esauriti —
        il caller gestisce il fallback (es. Tesseract per OCR).
        """
        provider = await self._pick_provider("ocr", vision=True)
        if provider == "tesseract":
            raise LLMQuotaExceededError("Groq esaurito — usa Tesseract come fallback.")
        await self._increment_usage(provider)
        if debug_info is not None:
            debug_info.update({
                "provider": provider,
                "model": _GROQ_VISION_MODEL,
                "task_type": "ocr",
                "usage_today": {p: (await self._get_today_usage(p)) for p in DAILY_LIMITS},
            })
        return await self._call_groq_vision(provider, image_b64, prompt, max_tokens)

    async def extract_pdf_markdown(self, pdf_b64: str, progress_fn=None) -> str:
        """
        Estrae il testo da un PDF (nativo o scansionato) usando Mistral OCR.
        Ritorna il testo in formato Markdown.
        Ritorna stringa vuota se Mistral non è disponibile o fallisce —
        il caller deve gestire il fallback a pdfminer.
        progress_fn: async callable(message: str, progress: int) — emette sub-eventi SSE.
        """
        mistral_usage = await self._get_today_usage("mistral")
        if mistral_usage >= DAILY_LIMITS.get("mistral", 100):
            logger.info("llm_router: quota Mistral giornaliera raggiunta")
            return ""
        from app.config import settings
        if not settings.mistral_api_key:
            logger.debug("llm_router: MISTRAL_API_KEY non configurata")
            return ""
        try:
            markdown = await self._call_mistral_ocr(pdf_b64, progress_fn=progress_fn)
            await self._increment_usage("mistral")
            logger.info("llm_router: Mistral OCR OK (%d chars)", len(markdown))
            return markdown
        except Exception as e:
            logger.warning("llm_router: Mistral OCR fallito (%s) — il caller userà pdfminer", e)
            return ""

    async def generate_with_pdf(
        self,
        task_type: str,
        pdf_b64: str,
        pdf_text_fallback: str,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 16000,
        debug_info: Optional[dict] = None,
        progress_fn=None,
    ) -> str:
        """
        Analisi PDF: Mistral OCR → markdown → Groq testo.
        Se Mistral non disponibile → usa pdf_text_fallback (testo pdfminer).
        Il testo viene troncato a _PDF_CHUNK_MAX_CHARS per rispettare il TPM Groq.
        Per PDF grandi con map-reduce, usare extract_pdf_markdown() + generate_text() direttamente.
        progress_fn: async callable(message: str, progress: int) — emette sub-eventi SSE.
        """
        # Fase 1: estrai markdown con Mistral OCR
        if progress_fn:
            await progress_fn("Estrazione testo PDF con Mistral OCR...", 68)
        markdown = await self.extract_pdf_markdown(pdf_b64, progress_fn=progress_fn)
        text_to_analyze = markdown or pdf_text_fallback

        if not text_to_analyze:
            raise LLMQuotaExceededError(
                "Mistral OCR non disponibile e nessun testo estratto per il fallback."
            )

        # Fase 2: tronca se necessario per rispettare il limite TPM di Groq
        if len(text_to_analyze) > _PDF_CHUNK_MAX_CHARS:
            logger.info(
                "generate_with_pdf: testo troncato da %d a %d chars (limite TPM Groq)",
                len(text_to_analyze), _PDF_CHUNK_MAX_CHARS,
            )
            text_to_analyze = text_to_analyze[:_PDF_CHUNK_MAX_CHARS]

        if progress_fn:
            await progress_fn("Analisi AI del contenuto PDF...", 74)
        full_prompt = f"{prompt}\n\nTESTO DEL MANUALE (Markdown):\n{text_to_analyze}"
        return await self.generate_text(
            task_type, full_prompt, system, max_tokens=max_tokens, debug_info=debug_info
        )

    # ── Implementazioni provider ───────────────────────────────────────────────

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

    async def _call_groq_vision(
        self,
        provider: str,
        image_b64: str,
        prompt: str,
        max_tokens: int,
    ) -> str:
        from app.config import settings
        from groq import AsyncGroq

        api_key = settings.groq_api_key if provider == "groq1" else settings.groq_api_key2
        if not api_key:
            raise LLMQuotaExceededError(f"API key non configurata per {provider}.")

        # Costruisce data URI se non già presente
        if image_b64.startswith("data:"):
            image_url = image_b64
        else:
            image_url = f"data:image/jpeg;base64,{image_b64}"

        client = AsyncGroq(api_key=api_key)
        response = await client.chat.completions.create(
            model=_GROQ_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=max_tokens,
            temperature=0.0,
        )
        return response.choices[0].message.content or ""

    async def _call_mistral_ocr(self, pdf_b64: str, progress_fn=None) -> str:
        """
        Chiama Mistral OCR API per estrarre testo da un PDF (nativo o scansionato).
        Ritorna il testo in formato Markdown concatenando tutte le pagine.
        Rate limit: max 4 RPM (1 ogni 15s) → attende il gap minimo se necessario.
        progress_fn: async callable(message: str, progress: int) — emette sub-eventi SSE.
        """
        import httpx
        from app.config import settings

        # Rispetta il rate limit RPM di Mistral OCR (2-5 RPM → gap minimo 15s)
        elapsed = time.monotonic() - self._mistral_last_call
        if elapsed < self._MISTRAL_MIN_INTERVAL:
            wait = self._MISTRAL_MIN_INTERVAL - elapsed
            logger.info("llm_router: attendo %.1fs per rate limit Mistral OCR", wait)
            if progress_fn:
                await progress_fn(f"Ottimizzazione rate limit OCR (attesa {wait:.0f}s)...", 66)
            await asyncio.sleep(wait)
        self._mistral_last_call = time.monotonic()
        if progress_fn:
            await progress_fn("Mistral OCR: lettura del PDF in corso...", 70)

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.mistral.ai/v1/ocr",
                headers={
                    "Authorization": f"Bearer {settings.mistral_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _MISTRAL_OCR_MODEL,
                    "document": {
                        "type": "document_url",
                        "document_url": f"data:application/pdf;base64,{pdf_b64}",
                    },
                },
            )
            resp.raise_for_status()

        data = resp.json()
        pages = data.get("pages", [])
        return "\n\n".join(p.get("markdown", "") for p in pages)

    # ── Utility: lettura contatori per admin ──────────────────────────────────

    async def get_all_usage_today(self) -> dict[str, dict]:
        """Ritorna i contatori odierni per tutti i provider (usato dall'endpoint admin)."""
        result = {}
        for provider, limit in DAILY_LIMITS.items():
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
