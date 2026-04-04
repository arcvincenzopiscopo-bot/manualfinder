"""
Integrazione Safety Gate EU (ex-RAPEX).
Sistema di allerta rapido europeo per prodotti pericolosi non alimentari.
Verifica se un macchinario specifico è stato soggetto a richiami o avvisi di sicurezza.

API pubblica: https://ec.europa.eu/safety-gate-alerts/screen/webReport
Endpoint dati: https://www.safetygate.eu (con accesso JSON tramite parametri)
"""
import re
import httpx
from typing import Optional


class SafetyAlert:
    """Avviso Safety Gate trovato per la macchina."""
    def __init__(
        self,
        title: str,
        risk_level: str,       # "serious" | "high" | "medium" | "unknown"
        description: str,
        measures: str,
        reference: str,
        date: str,
        url: str,
    ):
        self.title = title
        self.risk_level = risk_level
        self.description = description
        self.measures = measures
        self.reference = reference
        self.date = date
        self.url = url

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "risk_level": self.risk_level,
            "description": self.description,
            "measures": self.measures,
            "reference": self.reference,
            "date": self.date,
            "url": self.url,
        }


async def check_safety_alerts(brand: str, model: str) -> list[SafetyAlert]:
    """
    Cerca avvisi Safety Gate per la combinazione brand+model.
    Usa l'API pubblica Safety Gate con parametri di ricerca.
    Restituisce lista di alert (vuota se nessun problema trovato).
    """
    alerts: list[SafetyAlert] = []

    # Safety Gate mette a disposizione un endpoint di ricerca web
    # con risultati paginati in HTML — estraiamo i dati con scraping leggero
    search_terms = [
        f"{brand} {model}",
        brand,  # fallback solo brand se il modello non trova nulla
    ]

    for term in search_terms:
        found = await _search_safety_gate(term)
        if found:
            alerts.extend(found)
            break  # Se abbiamo trovato alert specifici, non cercare solo per brand

    # Deduplicazione per reference number
    seen_refs: set[str] = set()
    unique: list[SafetyAlert] = []
    for alert in alerts:
        if alert.reference not in seen_refs:
            seen_refs.add(alert.reference)
            unique.append(alert)

    return unique


async def _search_safety_gate(query: str) -> list[SafetyAlert]:
    """
    Cerca nel portale Safety Gate europeo.
    Il portale ha un'API REST pubblica documentata.
    """
    alerts: list[SafetyAlert] = []

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ManualFinder-SafetyCheck/1.0)",
        "Accept": "application/json, text/html",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    }

    try:
        # API REST Safety Gate — endpoint di ricerca pubblico
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            # Tentativo 1: API JSON ufficiale Safety Gate
            response = await client.get(
                "https://ec.europa.eu/safety-gate-alerts/screen/webReport/export",
                params={
                    "keyWords": query,
                    "alertNumber": "",
                    "category": "Machinery and mechanical appliances",
                    "notifyingCountries": "",
                    "fromAlertDate": "",
                    "toAlertDate": "",
                    "format": "json",
                    "limit": 10,
                },
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    alerts.extend(_parse_safety_gate_json(data, query))
                except Exception:
                    pass

            # Tentativo 2: ricerca HTML come fallback
            if not alerts:
                response = await client.get(
                    "https://ec.europa.eu/safety-gate-alerts/screen/webReport",
                    params={
                        "keyWords": query,
                        "category": "Machinery",
                    },
                )
                if response.status_code == 200:
                    alerts.extend(_parse_safety_gate_html(response.text, query))

    except Exception:
        pass

    return alerts


def _parse_safety_gate_json(data: dict | list, query: str) -> list[SafetyAlert]:
    """Parsa la risposta JSON del Safety Gate API."""
    alerts = []

    items = data if isinstance(data, list) else data.get("alerts", data.get("items", data.get("results", [])))
    if not isinstance(items, list):
        return alerts

    query_lower = query.lower()

    for item in items:
        if not isinstance(item, dict):
            continue

        title = (
            item.get("productName") or
            item.get("title") or
            item.get("product", {}).get("name", "") if isinstance(item.get("product"), dict) else ""
        ) or ""

        # Filtra: mantieni solo alert pertinenti alla query
        if query_lower not in title.lower() and query_lower not in str(item).lower():
            continue

        risk_level = _normalize_risk_level(
            item.get("riskLevel") or item.get("risk_level") or
            item.get("risk", {}).get("level", "") if isinstance(item.get("risk"), dict) else ""
        )

        alerts.append(SafetyAlert(
            title=title or query,
            risk_level=risk_level,
            description=item.get("description") or item.get("hazard") or "",
            measures=item.get("measures") or item.get("requiredMeasures") or "",
            reference=item.get("alertNumber") or item.get("reference") or item.get("id", ""),
            date=item.get("notificationDate") or item.get("date") or "",
            url=f"https://ec.europa.eu/safety-gate-alerts/screen/webReport/detail/{item.get('alertNumber', '')}",
        ))

    return alerts


def _parse_safety_gate_html(html: str, query: str) -> list[SafetyAlert]:
    """Parsa la pagina HTML di risultati Safety Gate come fallback."""
    from bs4 import BeautifulSoup

    alerts = []
    query_lower = query.lower()

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Safety Gate usa una tabella con classe specifica per i risultati
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            row_text = row.get_text(" ", strip=True).lower()
            if query_lower not in row_text:
                continue

            # Estrai link all'alert
            link = row.find("a", href=True)
            alert_url = ""
            alert_ref = ""
            if link:
                href = link["href"]
                alert_url = f"https://ec.europa.eu{href}" if href.startswith("/") else href
                # Estrai numero di riferimento dall'URL o dal testo
                ref_match = re.search(r'(\d{2}/\d+/[A-Z]+)', href + link.get_text())
                alert_ref = ref_match.group(1) if ref_match else href.split("/")[-1]

            title = cells[0].get_text(strip=True) if cells else query
            risk_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            risk_level = _normalize_risk_level(risk_text)

            alerts.append(SafetyAlert(
                title=title,
                risk_level=risk_level,
                description=cells[1].get_text(strip=True) if len(cells) > 1 else "",
                measures="",
                reference=alert_ref,
                date=cells[-1].get_text(strip=True) if cells else "",
                url=alert_url,
            ))

    except Exception:
        pass

    return alerts[:5]  # Massimo 5 alert per query


def _normalize_risk_level(raw: str) -> str:
    """Normalizza il livello di rischio in un valore coerente."""
    raw_lower = (raw or "").lower()
    if any(w in raw_lower for w in ["serious", "grave", "serio", "high", "alto"]):
        return "serious"
    if any(w in raw_lower for w in ["medium", "medio", "moderate", "moderato"]):
        return "medium"
    if any(w in raw_lower for w in ["low", "basso", "lieve"]):
        return "low"
    return "unknown"
