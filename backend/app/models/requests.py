from pydantic import BaseModel
from typing import Optional, List


class PlateAnalysisRequest(BaseModel):
    """Usato per il solo step OCR."""
    image_base64: str
    image_mime: str = "image/jpeg"


class SaveManualRequest(BaseModel):
    # Macchina cercata dall'ispettore (contesto)
    search_brand: Optional[str] = None
    search_model: Optional[str] = None
    search_machine_type: Optional[str] = None
    # Manuale reale trovato (può essere di un modello simile)
    manual_brand: str
    manual_model: str
    manual_machine_type: str
    manual_year: Optional[str] = None
    manual_language: str = "en"
    # Link
    url: str
    title: Optional[str] = None
    is_pdf: bool = True
    # Note libere dell'ispettore
    notes: Optional[str] = None


class FullAnalysisRequest(BaseModel):
    """
    Usato per la pipeline completa (search → download → analisi).
    L'utente ha già confermato/corretto brand e model dopo l'OCR.
    """
    image_base64: str
    brand: str
    model: str
    machine_type: Optional[str] = None    # Tipo di macchina per ricerca INAIL
    machine_type_id: Optional[int] = None # ID nel catalogo machine_types (None = testo libero)
    year: Optional[str] = None            # Anno di fabbricazione dalla targa
    serial_number: Optional[str] = None   # Numero di serie dalla targa (per ricerca su portali produttore)
    norme: List[str] = []                 # Norme armonizzate estratte dalla targa
    qr_url: Optional[str] = None          # Primo URL QR (backward compat, usato se qr_urls vuoto)
    qr_urls: List[str] = []               # Tutti gli URL decodificati da QR Code sulla targa
    preferred_language: str = "it"
