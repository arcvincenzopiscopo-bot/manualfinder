from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # === Livello 1 - API a pagamento (qualità massima) ===
    anthropic_api_key: Optional[str] = None
    perplexity_api_key: Optional[str] = None

    # === Livello 2 - API gratuite (fallback) ===
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None   # GROQ_API_KEY  — account 1
    groq_api_key2: Optional[str] = None  # GROQ_API_KEY2 — account 2
    brave_search_api_key: Optional[str] = None
    google_cse_api_key: Optional[str] = None
    google_cse_cx: Optional[str] = None
    # Tavily: 1000 query/mese gratis, nessuna carta — https://app.tavily.com
    tavily_api_key: Optional[str] = None

    # === Selezione livello: "auto" | "1" | "2" ===
    api_tier: str = "auto"

    # === Configurazione PDF ===
    max_pdf_size_mb: int = 50
    max_pdf_pages_per_chunk: int = 30

    # === Database ===
    database_url: Optional[str] = None  # postgresql://postgres.[PWD]@aws-0-eu-west-1.pooler.supabase.com:6543/postgres

    # === Admin ===
    # Se impostato, tutti gli endpoint /admin/* e /rag/* richiedono header X-Admin-Token con questo valore.
    # Lasciare vuoto per disabilitare l'autenticazione (solo ambienti di sviluppo).
    admin_token: Optional[str] = None

    # === Upload manuali ===
    upload_dir: str = "manuali_locali"  # relativo a backend/ — cartella dove vengono salvati i PDF caricati dagli ispettori

    # === Supabase Storage (per persistenza PDF su cloud) ===
    # Se configurati, i PDF caricati dagli ispettori vengono anche caricati su Supabase Storage
    # e l'URL pubblico viene usato al posto del percorso locale (sopravvive ai redeploy su Render).
    # supabase_url: es. https://xxxx.supabase.co (senza slash finale)
    # supabase_service_key: service_role key del progetto (non anon key)
    # supabase_storage_bucket: nome del bucket pubblico (default: "manuali")
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None
    supabase_storage_bucket: str = "manuali"

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
        if self.tavily_api_key:
            return "tavily"
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
