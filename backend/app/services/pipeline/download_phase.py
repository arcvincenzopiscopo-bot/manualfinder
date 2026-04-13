"""
Fase 2 della pipeline analyze: download e selezione PDF.
Estratto da routers/analyze._pipeline per testabilità e leggibilità.
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

_logger = logging.getLogger(__name__)

# Soglie qualità PDF — condivise con i commenti in analyze.py
_LOW_QUALITY_THRESHOLD = 8    # score minimo per PDF corti (< 30 pag.)
_MIN_MANUAL_PAGES = 5         # sotto questa soglia serve score >= 40
_SCANNED_PAGES_THRESHOLD = 30 # PDF lungo anche senza testo → probabilmente scansionato
_INAIL_MIN_SCORE = 5
_DATASHEET_MAX_PAGES = 20

# Domini INAIL mirror — fallback statico (il DB sovrascrive via config_service)
_FB_INAIL_MIRROR = {
    "necsi.it", "aliseo", "ispesl.it", "dors.it",
    "salute.gov.it", "lavoro.gov.it", "inail.it",
    "ausl.", "asl.", "spresal", "spisal",
    "portaleagenti.it", "sicurezzaentipubblici",
    "formediltorinofsc.it", "puntosicuro.it", "suva.ch",
}


def _get_inail_mirror_domains() -> set:
    try:
        from app.services.config_service import get_domains as _get_domains
        return _get_domains("inail_mirror") or _FB_INAIL_MIRROR
    except Exception:
        return _FB_INAIL_MIRROR


def _is_inail_mirror(url: str, mirror_domains: set) -> bool:
    from urllib.parse import urlparse
    full = (urlparse(url).netloc + urlparse(url).path).lower()
    return any(d in full for d in mirror_domains)


# ── Risultato ─────────────────────────────────────────────────────────────────

@dataclass
class DownloadPhaseResult:
    inail_bytes: Optional[bytes] = None
    inail_url: Optional[str] = None
    producer_bytes: Optional[bytes] = None
    producer_url: Optional[str] = None
    producer_pages: int = 0
    producer_match_type: str = "unknown"
    producer_source_label: str = ""
    datasheet_bytes: Optional[bytes] = None
    datasheet_url: Optional[str] = None
    supplemental_bytes: Optional[bytes] = None
    supplemental_url: Optional[str] = None
    supplemental_label: Optional[str] = None
    has_local_inail: bool = False   # può diventare False se ghost file
    brochure_note: Optional[str] = None
    producer_scored_count: int = 0
    similar_category_used: bool = False
    dl_message: str = "Nessun PDF disponibile. Analisi basata su conoscenza AI."


# ── Funzione principale ───────────────────────────────────────────────────────

async def run_download_phase(
    brand: str,
    model: str,
    machine_type: Optional[str],
    machine_type_id: Optional[int],
    pdf_candidates: list,
    qr_urls: list,
    has_local_inail: bool,
    local_inail: Optional[dict],
    analysis_provider: str,
) -> DownloadPhaseResult:
    """
    Scarica e seleziona i PDF migliori per ciascuna fonte (INAIL, produttore, datasheet, supplemental).
    Ritorna DownloadPhaseResult con tutti i bytes e metadati necessari all'analisi.
    """
    from app.services import pdf_service
    from app.models.responses import ManualSearchResult as _MSR
    from app.services.pipeline.producer_filter import filter_producer_candidates

    result = DownloadPhaseResult(
        has_local_inail=has_local_inail,
        producer_source_label=f"Produttore ({brand})",
    )

    # Inietta candidati QR Code come priorità assoluta
    if qr_urls:
        for i, qu in enumerate(qr_urls):
            qr_candidate = _MSR(
                url=qu,
                title=f"Manuale da QR Code — {brand} {model}",
                source_type="manufacturer",
                language="unknown",
                is_pdf=qu.lower().endswith(".pdf"),
                relevance_score=95 - i,
            )
            pdf_candidates.insert(i, qr_candidate)

    mirror_domains = _get_inail_mirror_domains()

    # Partiziona candidati per fonte
    supplemental_candidates = [r for r in pdf_candidates if r.source_type == "supplemental"]
    inail_candidates = [r for r in pdf_candidates
                        if r.source_type == "inail" or _is_inail_mirror(r.url, mirror_domains)]
    datasheet_candidates = [r for r in pdf_candidates
                            if r.source_type == "datasheet" and not _is_inail_mirror(r.url, mirror_domains)]
    producer_candidates = [r for r in pdf_candidates
                           if r.source_type not in ("inail", "datasheet", "supplemental")
                           and not _is_inail_mirror(r.url, mirror_domains)]

    # Inietta manuale INAIL locale come primo candidato (priorità assoluta)
    if has_local_inail and local_inail:
        _local_url = f"/manuals/local/{local_inail['filename']}"
        inail_candidates.insert(0, _MSR(
            url=_local_url,
            title=f"{local_inail['title']} (INAIL - Locale)",
            source_type="inail",
            language="it",
            is_pdf=True,
            relevance_score=100,
        ))

    # ── Download INAIL ──────────────────────────────────────────────────────
    async def _download_inail(candidate):
        pdf_data, _ = await pdf_service.download_pdf(candidate.url)
        if pdf_data:
            score = pdf_service.score_pdf_safety_relevance(
                pdf_data, brand=brand, model=model,
                machine_type=machine_type or "", machine_type_id=machine_type_id,
            )
            return (score, pdf_data, candidate.url)
        return None

    inail_downloads = await asyncio.gather(
        *[_download_inail(c) for c in inail_candidates[:3]], return_exceptions=True
    )
    inail_scored = sorted(
        [r for r in inail_downloads if isinstance(r, tuple)],
        key=lambda x: x[0], reverse=True,
    )

    if inail_scored:
        # Pass 1: priorità assoluta ai PDF locali (preapprovati, nessun controllo score)
        for _iscore, _ibytes, _iurl in inail_scored:
            if _iurl.startswith("/manuals/local/"):
                result.inail_bytes, result.inail_url = _ibytes, _iurl
                break
        # Pass 2: miglior PDF online con score sufficiente e non unrelated
        if result.inail_bytes is None:
            for _iscore, _ibytes, _iurl in inail_scored:
                if _iurl.startswith("/manuals/local/"):
                    continue
                if _iscore < _INAIL_MIN_SCORE:
                    continue
                if machine_type:
                    _imatch = pdf_service.classify_pdf_match(
                        _ibytes, brand, model, machine_type, machine_type_id=machine_type_id,
                    )
                    if _imatch == "unrelated":
                        continue
                result.inail_bytes, result.inail_url = _ibytes, _iurl
                break

    if has_local_inail and result.inail_bytes is None:
        result.has_local_inail = False
        _logger.warning("INAIL locale non trovato dopo pre-check (filesystem efimero?) — fallback ricerca online")

    # ── Download datasheet ──────────────────────────────────────────────────
    if datasheet_candidates:
        for ds_candidate in datasheet_candidates[:2]:
            try:
                ok, _ = await pdf_service.head_check_url(ds_candidate.url)
                if not ok:
                    continue
                ds_data, _ = await pdf_service.download_pdf(ds_candidate.url)
                if not ds_data:
                    continue
                ds_pages = pdf_service.count_pdf_pages(ds_data)
                if ds_pages > _DATASHEET_MAX_PAGES:
                    # Troppo lungo: trattalo come manuale produttore
                    if not result.producer_bytes:
                        result.producer_bytes = ds_data
                        result.producer_url = ds_candidate.url
                        result.producer_pages = ds_pages
                else:
                    _ds_text = pdf_service.extract_full_text(ds_data)[:8000].lower()
                    if brand.lower() in _ds_text or model.lower() in _ds_text:
                        result.datasheet_bytes = ds_data
                        result.datasheet_url = ds_candidate.url
                break
            except Exception:
                continue

    # ── Download produttore ─────────────────────────────────────────────────
    producer_candidates = filter_producer_candidates(
        producer_candidates, brand=brand, model=model, machine_type=machine_type
    )

    tier1 = [c for c in producer_candidates if c.relevance_score >= 55]
    tier2 = [c for c in producer_candidates if c.relevance_score < 55]
    ordered_candidates = (tier1 + tier2)[:5]

    async def _download_and_score(candidate):
        ok, reason = await pdf_service.head_check_url(candidate.url)
        if not ok:
            _logger.info("HEAD skip: %s — %s", candidate.url[:80], reason)
            return None
        pdf_data, err = await pdf_service.download_pdf(candidate.url)
        if pdf_data:
            pages = pdf_service.count_pdf_pages(pdf_data)
            score = pdf_service.score_pdf_safety_relevance(
                pdf_data, brand=brand, model=model,
                machine_type=machine_type or "", machine_type_id=machine_type_id,
            )
            if 5 <= score <= 30 and pages < 25 and analysis_provider in ("anthropic", "gemini"):
                is_manual = await pdf_service.ai_quick_validate(
                    pdf_data, brand, model, machine_type or "", analysis_provider
                )
                if not is_manual:
                    score = 0
            return (score, pdf_data, candidate.url, candidate.relevance_score, pages)
        _logger.info("PDF download failed: %s — %s", candidate.url[:80], err)
        return None

    download_tasks = [_download_and_score(c) for c in ordered_candidates]
    download_results = await asyncio.gather(*download_tasks)
    producer_scored: list[tuple[int, bytes, str, int, int]] = [r for r in download_results if r is not None]
    result.producer_scored_count = len(producer_scored)

    _brochure_note: Optional[str] = None
    best_score: Optional[int] = None

    if producer_scored:
        producer_scored.sort(key=lambda x: x[0] * 0.7 + x[3] * 0.3, reverse=True)

        _db_urls = {c.url for c in ordered_candidates if c.title.startswith("[DB]")}

        best = None
        rejection_reasons: list[str] = []

        # Pass 1: priorità manuali DB preapprovati
        _db_entries = [e for e in producer_scored if e[2] in _db_urls]
        if _db_entries:
            def _db_priority(entry):
                url = entry[2]
                cand = next((c for c in ordered_candidates if c.url == url), None)
                if cand is None:
                    return 0
                title = cand.title.lower()
                specific = brand.lower() in title and model.lower() in title
                return (2 if specific else 1, entry[0])
            _db_entries.sort(key=_db_priority, reverse=True)
            best = _db_entries[0]

        # Pass 2: selezione per qualità
        for entry in (producer_scored if best is None else []):
            score, pdf_data, url, rel_score, pages = entry
            short_url = url[-60:]
            if pages >= _SCANNED_PAGES_THRESHOLD:
                best = entry
                break
            if pages >= _MIN_MANUAL_PAGES and score >= _LOW_QUALITY_THRESHOLD:
                best = entry
                break
            if pages < _MIN_MANUAL_PAGES and score >= 40:
                best = entry
                break
            rejection_reasons.append(f"{pages}pp score={score} ({short_url})")

        if best is None:
            best_pages = producer_scored[0][4]
            best_score_val = producer_scored[0][0]
            reasons_str = "; ".join(rejection_reasons[:3])
            _brochure_note = (
                f"PDF scartato: {best_pages} pag., score {best_score_val}/100 "
                f"(brochure/datasheet). Dettagli: {reasons_str}. Procedo con analisi AI."
            )
        else:
            best_score, result.producer_bytes, result.producer_url, _, result.producer_pages = best

    # Libera memoria dei PDF scaricati ma non selezionati
    del download_results
    producer_scored = []

    # ── Classifica PDF produttore ───────────────────────────────────────────
    if result.producer_bytes:
        _producer_from_db = result.producer_url and any(
            c.url == result.producer_url and c.title.startswith("[DB]")
            for c in ordered_candidates
        )
        if _producer_from_db:
            _db_candidate = next(
                (c for c in ordered_candidates if c.url == result.producer_url and c.title.startswith("[DB]")),
                None,
            )
            _is_db_generic = _db_candidate and "generico" in _db_candidate.title.lower()
            _db_title_lower = (_db_candidate.title.lower() if _db_candidate else "")
            _is_db_exact_match = brand.lower() in _db_title_lower and model.lower() in _db_title_lower

            if _is_db_generic:
                result.producer_source_label = f"Manuale DB — categoria {machine_type or 'macchina'}"
                result.producer_match_type = "category"
            elif _is_db_exact_match:
                result.producer_source_label = f"Manuale DB {brand} {model}"
                result.producer_match_type = "exact"
            else:
                result.producer_source_label = f"Manuale DB categoria simile ({machine_type or 'macchina'})"
                result.producer_match_type = "category"
        else:
            result.producer_match_type = pdf_service.classify_pdf_match(
                result.producer_bytes, brand, model, machine_type or "",
                machine_type_id=machine_type_id,
            )
            if result.producer_match_type == "category":
                result.producer_source_label = f"Manuale categoria simile ({machine_type or 'macchina'})"
            elif result.producer_match_type == "unrelated":
                result.producer_bytes = None
                result.producer_source_label = "AI"
                _brochure_note = (
                    f"PDF scartato: non pertinente per {machine_type or brand} "
                    "(documento di categoria diversa). Procedo con analisi AI."
                )

    # ── Deduplica INAIL == produttore ───────────────────────────────────────
    if result.producer_bytes and result.inail_bytes:
        if pdf_service.are_pdfs_same_content(result.producer_bytes, result.inail_bytes):
            result.producer_bytes = None
            result.producer_source_label = "AI"
            _brochure_note = (
                "Manuale produttore identico alla scheda INAIL — "
                "raccomandazioni specifiche generate da conoscenza AI."
            )

    # ── Fallback categoria simile locale ─────────────────────────────────────
    if result.has_local_inail and result.producer_bytes is None and local_inail:
        try:
            from app.services.local_manuals_service import (
                find_similar_category_local_manuals as _find_similar_cat,
                PDF_MANUALS_DIR as _PDF_MANUALS_DIR,
            )
            _similar_candidates = _find_similar_cat(
                machine_type=machine_type or "",
                machine_type_id=machine_type_id,
                exclude_filename=local_inail.get("filename"),
            )
            if _similar_candidates:
                _scored_sim: list[tuple[int, bytes, dict]] = []
                for _sc in _similar_candidates:
                    try:
                        _sc_bytes = (_PDF_MANUALS_DIR / _sc["filename"]).read_bytes()
                        _sc_score = pdf_service.score_pdf_safety_relevance(
                            _sc_bytes, brand=brand, model=model,
                            machine_type=machine_type or "", machine_type_id=machine_type_id,
                        )
                        _scored_sim.append((_sc_score, _sc_bytes, _sc))
                    except Exception:
                        continue
                if _scored_sim:
                    _scored_sim.sort(key=lambda x: x[0], reverse=True)
                    if len(_scored_sim) >= 2:
                        _best_idx = await pdf_service.ai_compare_manuals(
                            _scored_sim[0][1], _scored_sim[1][1],
                            machine_type or "", analysis_provider,
                        )
                        _winner = _scored_sim[_best_idx]
                    else:
                        _winner = _scored_sim[0]
                    _w_score, result.producer_bytes, _w_cand = _winner
                    result.producer_url = f"/manuals/local/{_w_cand['filename']}"
                    result.producer_source_label = f"Manuale categoria ({machine_type or 'macchina'})"
                    result.producer_match_type = "category"
                    result.producer_pages = pdf_service.count_pdf_pages(result.producer_bytes)
                    result.similar_category_used = True
                    _brochure_note = None
        except Exception as _sim_err:
            _logger.warning("Ricerca categoria simile fallita: %s", _sim_err)

    # ── Supplemental (3ª fonte istituzionale) ─────────────────────────────
    if result.has_local_inail and supplemental_candidates and result.inail_bytes:
        for _supp_cand in supplemental_candidates[:2]:
            try:
                _supp_data, _ = await pdf_service.download_pdf(_supp_cand.url)
                if not _supp_data:
                    continue
                if pdf_service.are_pdfs_same_content(_supp_data, result.inail_bytes):
                    continue
                if machine_type:
                    _supp_match = pdf_service.classify_pdf_match(
                        _supp_data, brand, model, machine_type, machine_type_id=machine_type_id,
                    )
                    if _supp_match == "unrelated":
                        continue
                result.supplemental_bytes = _supp_data
                result.supplemental_url = _supp_cand.url
                break
            except Exception:
                continue

    if result.supplemental_url:
        from urllib.parse import urlparse as _urlparse
        _supp_domain = _urlparse(result.supplemental_url).netloc.lower()
        for _known in ("suva.ch", "cpt.", "formedil", "euosha", "eu-osha", "ucimu", "enama"):
            if _known in _supp_domain:
                result.supplemental_label = _known.upper().split(".")[0].replace("-", "")
                break
        result.supplemental_label = result.supplemental_label or "Fonte istituzionale"

    # ── Costruisce messaggio download ───────────────────────────────────────
    result.brochure_note = _brochure_note

    parts_ok = []
    if result.inail_bytes:
        parts_ok.append(f"INAIL ({pdf_service.count_pdf_pages(result.inail_bytes)} pag.)")
    if result.producer_bytes:
        safety_score = best_score if best_score is not None else 0
        quality_label = "" if safety_score >= _LOW_QUALITY_THRESHOLD else " ⚠ bassa pertinenza"
        match_label = "" if result.producer_match_type == "exact" else " ⚠ categoria simile"
        parts_ok.append(
            f"produttore ({result.producer_pages} pag., "
            f"selezionato tra {result.producer_scored_count} — "
            f"sicurezza: {safety_score}/100{quality_label}{match_label})"
        )
    if result.supplemental_bytes:
        parts_ok.append(
            f"3ª fonte istituzionale ({result.supplemental_label or 'supplemental'}, "
            f"{pdf_service.count_pdf_pages(result.supplemental_bytes)} pag.)"
        )

    n_pdf_found = len(pdf_candidates)
    n_downloaded = result.producer_scored_count + (1 if result.inail_bytes else 0)

    if not parts_ok and _brochure_note:
        result.dl_message = _brochure_note
    elif parts_ok:
        result.dl_message = f"Scaricati: {', '.join(parts_ok)}."
    elif n_pdf_found > 0 and n_downloaded == 0:
        result.dl_message = (
            f"Trovati {n_pdf_found} PDF ma nessuno scaricabile (timeout o accesso negato). "
            "Procedo con analisi AI."
        )
    elif n_pdf_found > 0 and n_downloaded > 0:
        result.dl_message = (
            f"Trovati {n_pdf_found} PDF, {n_downloaded} scaricati ma tutti scartati "
            "(score troppo basso o non pertinenti). Procedo con analisi AI."
        )
    else:
        result.dl_message = "Nessun PDF trovato nella ricerca. Procedo con analisi AI."

    return result
