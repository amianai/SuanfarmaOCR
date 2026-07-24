"""Configurazione centralizzata (pydantic-settings).

I dati (database, PDF, testi, Excel) sono SEPARATI dal codice: la loro posizione
è configurabile con la variabile d'ambiente DATA_DIR. Così il codice sta su
GitHub e i dati stanno altrove (Drive, disco del server, volume Docker) — basta
puntare DATA_DIR alla cartella che li contiene. Default: la root del progetto,
comodo in sviluppo locale.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] = root del progetto
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Cartella dati (configurabile: dove stanno DB, PDF, testi, Excel) ---
    data_dir: Path = PROJECT_ROOT

    # --- Autenticazione ---
    # jwt_secret / viewer_password / admin_password: SEGRETI, vanno impostati nel
    # .env (gitignored). I valori qui sotto sono solo segnaposto di sviluppo:
    # NON sono le password reali (quelle vivono nel .env locale, mai su git).
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    viewer_password: str = "changeme"
    admin_password: str = "changeme-admin"

    # --- CORS (origine del frontend Vite in sviluppo) ---
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- OCR (documenti nuovi caricati dall'interfaccia) ---
    # Motore locale Tesseract: nessuna API esterna, gira su CPU. Il binario e la
    # lingua vanno installati nel sistema (brew/apt) o cotti nell'immagine Docker.
    ocr_lang: str = "ita"          # codice lingua Tesseract (es. "ita", "ita+eng")
    ocr_dpi: int = 300             # risoluzione di rendering delle pagine PDF per l'OCR
    ocr_tesseract_cmd: str = ""    # percorso al binario tesseract, se non nel PATH

    # --- Ricerca semantica (Fase 4) ---
    # Modello di embedding locale (fastembed/ONNX, gira su CPU, nessuna API).
    # Default: multilingue, testato e leggero (~220MB), ottimo con l'italiano.
    # Sostituibile da .env (es. "intfloat/multilingual-e5-large" per più qualità).
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_chunk_size: int = 1000      # caratteri per spezzone
    embedding_chunk_overlap: int = 200    # sovrapposizione tra spezzoni
    # 60 è il k standard della Reciprocal Rank Fusion (costante di smorzamento).
    rrf_k: int = 60
    # La semantica contribuisce al più i primi N documenti sopra una soglia minima
    # di similarità: evita che "tutti i documenti" entrino nei risultati di ricerca.
    semantic_top_n: int = 30
    semantic_min_score: float = 0.35

    # --- Servizi esterni ---
    # mistral_api_key: legacy, non più usata dall'upload (OCR ora è locale via
    # Tesseract). Restava per la vecchia pipeline; conservata solo per compatibilità.
    mistral_api_key: str = ""

    # --- LLM / RAG (Fase 5) — tutto configurabile da .env come da indicazione del prof ---
    # Client OpenAI-compatibile: funziona con Ollama (dev), vLLM (self-host) o API a consumo.
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5:3b"
    llm_api_key: str = ""
    # Timeout generoso: i modelli locali grandi su CPU possono essere lenti.
    llm_timeout: float = 300.0
    # Stile API: "openai" (default, generico: vLLM/hosted/Ollama-v1) oppure
    # "ollama" (endpoint nativo /api/chat, che permette di disattivare il
    # ragionamento dei modelli "thinking" con think=false — l'endpoint OpenAI
    # di Ollama lo ignora). La produzione resta su "openai".
    llm_api_style: str = "openai"

    # --- Percorsi derivati da data_dir (non sono campi env: seguono DATA_DIR) ---
    @property
    def database_url(self) -> str:
        return f"sqlite:///{(self.data_dir / 'archivio.db').as_posix()}"

    @property
    def documenti_pdf_dir(self) -> Path:
        return self.data_dir / "documenti_pdf"

    @property
    def testo_estratto_dir(self) -> Path:
        return self.data_dir / "testo_estratto"

    @property
    def excel_path(self) -> Path:
        return self.data_dir / "OCR database.xlsx"


settings = Settings()
