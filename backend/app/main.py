"""Entry point FastAPI dell'Archivio OCR."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import admin, auth, chat, documents
from .core.config import settings

app = FastAPI(title="Archivio OCR API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Il frontend deve poter leggere il token rinnovato dalla risposta.
    expose_headers=["X-Refreshed-Token"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(admin.router)
app.include_router(chat.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
