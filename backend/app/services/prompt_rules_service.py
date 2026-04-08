"""
Cache TTL 15 min delle regole prompt per tipo macchina da Supabase (tabella machine_prompt_rules).
Permette di personalizzare il comportamento AI per categoria di macchina senza deploy.
Supporta auto-generazione tramite AI per tipi macchina non ancora in DB.
"""
import json
import re
import time as _time
from typing import Optional
from app.config import settings

_cache: dict[str, dict] = {}
_cache_ts: float = 0.0
_TTL = 900  # 15 minuti


def get_rules_for_machine_type(machine_type: str) -> Optional[dict]:
    """
    Cerca la regola prompt per il tipo macchina specificato (match parziale).
    Ritorna None se non trovata o se il DB non è disponibile.
    Cache in-memory TTL 15 min.
    """
    global _cache, _cache_ts
    now = _time.monotonic()
    if now - _cache_ts > _TTL:
        _refresh_cache()
    if not machine_type:
        return None
    mt = machine_type.lower().strip()
    # Match esatto prima, poi parziale (es. "piattaforma aerea a braccio" → "piattaforma aerea")
    if mt in _cache:
        return _cache[mt]
    for key, rule in _cache.items():
        if key in mt or mt in key:
            return rule
    return None


async def generate_and_save_rule(machine_type: str, provider: str) -> Optional[dict]:
    """
    Genera una regola prompt via AI (Haiku/Gemini-Flash) per un tipo macchina non ancora in DB.
    Salva in machine_prompt_rules con source='auto_generated'.
    Usa modello economico (~800 token, ~1-2s).
    Ritorna il dict della regola per uso immediato nell'analisi corrente.
    """
    if not machine_type or not machine_type.strip():
        return None

    meta_prompt = f"""Sei un esperto di sicurezza sul lavoro italiano (D.Lgs. 81/2008, Direttiva Macchine 2006/42/CE).
Genera le regole di analisi per il tipo di macchina: "{machine_type}"

Rispondi SOLO con JSON valido, nessun altro testo:
{{
  "extra_context": "Caratteristiche chiave di questa macchina per la sicurezza: classe di rischio, impieghi tipici, ambiente operativo, operatori tipici",
  "specific_risks": "Rischi di infortunio SPECIFICI di questa categoria da evidenziare SEMPRE nell'analisi. Elenca i 3-5 più frequenti con gravità [ALTA/MEDIA/BASSA]",
  "normative_refs": "Norme vigenti applicabili: direttive CE specifiche, norme EN/UNI EN pertinenti, articoli D.Lgs. 81/2008 e allegati rilevanti, Accordo Stato-Regioni se applicabile",
  "inspection_focus": "I 3-5 elementi che l'ispettore deve verificare FISICAMENTE in sopralluogo: cosa cercare, dove trovarlo sulla macchina, come giudicarne la conformità"
}}"""
    try:
        result = await _call_ai_for_rule(meta_prompt, provider)
        if not result:
            return None
        # Salva nel DB (ON CONFLICT DO NOTHING — non sovrascrive regole manuali)
        _save_generated_rule(machine_type, result, source="auto_generated")
        # Aggiorna cache in-memory per uso immediato
        rule_dict = {
            "machine_type": machine_type.lower().strip(),
            "extra_context": result.get("extra_context"),
            "specific_risks": result.get("specific_risks"),
            "normative_refs": result.get("normative_refs"),
            "inspection_focus": result.get("inspection_focus"),
            "is_active": True,
            "source": "auto_generated",
        }
        _cache[machine_type.lower().strip()] = rule_dict
        return rule_dict
    except Exception:
        return None


async def _call_ai_for_rule(prompt: str, provider: str) -> Optional[dict]:
    """
    Chiamata AI economica (Haiku/Gemini-Flash) per generare o migliorare prompt rules.
    Usata sia da generate_and_save_rule() che da prompt_optimizer_service.
    """
    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            r = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=900,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = r.content[0].text
        elif provider == "gemini":
            from google import genai
            from google.genai import types as gtypes
            client = genai.Client(api_key=settings.gemini_api_key)
            r = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=gtypes.GenerateContentConfig(max_output_tokens=900, temperature=0),
            )
            text = r.text
        else:
            return None
        # Estrai JSON dalla risposta (tollera testo prima/dopo il blocco JSON)
        m = re.search(r'\{[\s\S]+\}', text)
        if not m:
            return None
        return json.loads(m.group())
    except Exception:
        return None


def _save_generated_rule(machine_type: str, rule: dict, source: str = "auto_generated") -> None:
    """Salva la regola nel DB. ON CONFLICT DO NOTHING — non sovrascrive regole manuali."""
    if not settings.database_url:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(settings.database_url)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO machine_prompt_rules
                    (machine_type, extra_context, specific_risks, normative_refs,
                     inspection_focus, is_active, source, updated_at)
                VALUES (%s, %s, %s, %s, %s, true, %s, now())
                ON CONFLICT (machine_type) DO NOTHING
                """,
                (
                    machine_type.lower().strip(),
                    rule.get("extra_context"),
                    rule.get("specific_risks"),
                    rule.get("normative_refs"),
                    rule.get("inspection_focus"),
                    source,
                ),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _refresh_cache() -> None:
    global _cache, _cache_ts
    if not settings.database_url:
        _cache_ts = _time.monotonic()  # Evita refresh continui se DB non configurato
        return
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(settings.database_url)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM machine_prompt_rules WHERE is_active = true ORDER BY machine_type"
            )
            rows = cur.fetchall()
        conn.close()
        _cache = {r["machine_type"].lower().strip(): dict(r) for r in rows}
        _cache_ts = _time.monotonic()
    except Exception:
        _cache_ts = _time.monotonic()  # Segna come "aggiornato" per evitare retry loop


def invalidate_cache() -> None:
    """Invalida la cache — chiamato dopo ogni modifica alle regole."""
    global _cache_ts
    _cache_ts = 0.0
