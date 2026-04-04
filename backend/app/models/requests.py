from pydantic import BaseModel
from typing import Optional, List


class PlateAnalysisRequest(BaseModel):
    """Usato per il solo step OCR."""
    image_base64: str
    image_mime: str = "image/jpeg"


class FullAnalysisRequest(BaseModel):
    """
    Usato per la pipeline completa (search → download → analisi).
    L'utente ha già confermato/corretto brand e model dopo l'OCR.
    """
    image_base64: str
    brand: str
    model: str
    machine_type: Optional[str] = None    # Tipo di macchina per ricerca INAIL
    year: Optional[str] = None            # Anno di fabbricazione dalla targa
    serial_number: Optional[str] = None   # Numero di serie dalla targa (per ricerca su portali produttore)
    norme: List[str] = []                 # Norme armonizzate estratte dalla targa
    qr_url: Optional[str] = None          # URL da QR Code sulla targa (link diretto al manuale)
    preferred_language: str = "it"
