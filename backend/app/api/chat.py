"""Router del chatbot RAG."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..services import rag
from ..services.llm import LLMError
from .deps import Identity, require_viewer

router = APIRouter(prefix="/chat", tags=["chat"])


def _verifica_abilitato() -> None:
    """Il chatbot è una funzione opzionale, spenta per default.

    Nascondere il pulsante non basterebbe: senza questo controllo l'endpoint
    resterebbe raggiungibile chiamando direttamente l'API.
    """
    if not settings.chat_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Funzione non disponibile"
        )


class ChatRequest(BaseModel):
    domanda: str = Field(min_length=1, max_length=2000)


class Fonte(BaseModel):
    doc_id: int
    nome_file: str
    descrizione: str


class ChatResponse(BaseModel):
    risposta: str
    fonti: list[Fonte]


@router.post("", response_model=ChatResponse)
def chiedi(
    body: ChatRequest,
    db: Session = Depends(get_db),
    _identity: Identity = Depends(require_viewer),
    _abilitato: None = Depends(_verifica_abilitato),
) -> dict:
    try:
        return rag.answer(db, body.domanda.strip())
    except LLMError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Il modello del chatbot non è raggiungibile. {e}",
        )
