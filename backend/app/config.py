from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # === Livello 1 - API a pagamento (qualità massima) ===
    anthropic_api_key: Optional[str] = None
    perplexity_api_key: Optional[str] = None

    # === Livello 2 - API gratuite (fallback) ===
    gemini_api_key: Optional[str] = None
    brave_search_api_key: Optional[str] = None
    google_cse_api_key: Optional[str] = None
    google_cse_cx: Optional[str] = None

    # === Selezione livello: "auto" | "1" | "2" ===
    api_tier: str = "auto"

    # === Configurazione PDF ===
    max_pdf_size_mb: int = 50
    max_pdf_pages_per_chunk: int = 30

    # === Database ===
    database_url: Optional[str] = None  # postgresql://postgres.[PWD]@aws-0-eu-west-1.pooler.supabase.com:6543/postgres

    # === Upload manuali ===
    upload_dir: str = "manuali_locali"  # relativo a backend/ — cartella dove vengono salvati i PDF caricati dagli ispettori

    # === Server ===
    # In produzione su Render, sovrascrivere con l'URL reale del frontend via variabile ALLOWED_ORIGINS
    allowed_origins: str = "http://localhost:5173,https://manualfinder.vercel.app,https://manualfinder-frontend.onrender.com"
    environment: str = "development"
    rate_limit_per_minute: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_vision_provider(self) -> str:
        """Restituisce il provider da usare per OCR/Vision."""
        if self.api_tier == "1" or (self.api_tier == "auto" and self.anthropic_api_key):
            return "anthropic"
        if self.gemini_api_key:
            return "gemini"
        return "tesseract"

    def get_search_provider(self) -> str:
        """Restituisce il provider da usare per la ricerca manuale."""
        if self.api_tier == "1" or (self.api_tier == "auto" and self.perplexity_api_key):
            return "perplexity"
        if self.brave_search_api_key:
            return "brave"
        if self.google_cse_api_key and self.google_cse_cx:
            return "google_cse"
        if self.gemini_api_key:
            return "gemini_search"   # Google Search grounding via Gemini API
        return "duckduckgo"

    def get_analysis_provider(self) -> str:
        """Restituisce il provider da usare per l'analisi dei manuali."""
        if self.api_tier == "1" or (self.api_tier == "auto" and self.anthropic_api_key):
            return "anthropic"
        if self.gemini_api_key:
            return "gemini"
        return "none"


settings = Settings()
