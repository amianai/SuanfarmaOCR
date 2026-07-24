"""Router di autenticazione: password condivisa + identità leggera (nome da lista)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import security
from ..core.db import get_db
from ..models.collab import Utente
from .deps import Identity, get_current_identity

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str
    nome: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    nome: str
    expires_in: int


@router.get("/utenti", response_model=list[str])
def lista_nomi(db: Session = Depends(get_db)) -> list[str]:
    """Nomi attivi selezionabili al login.

    Endpoint pubblico: serve a popolare il menu del form di login prima
    dell'autenticazione. Espone solo i nomi (nessun ruolo/segreto) — dato a
    bassa sensibilità per un'applicazione interna.
    """
    return list(
        db.execute(
            select(Utente.nome).where(Utente.attivo == 1).order_by(Utente.nome)
        ).scalars()
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    role = security.authenticate(body.password)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Password errata"
        )

    nome = body.nome.strip()
    utente = db.scalar(select(Utente).where(Utente.nome == nome, Utente.attivo == 1))
    if utente is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nome non riconosciuto: scegli il tuo nome dalla lista",
        )

    token, expires_in = security.create_access_token(role, nome)
    return TokenResponse(access_token=token, role=role, nome=nome, expires_in=expires_in)


@router.get("/me")
def me(identity: Identity = Depends(get_current_identity)) -> dict[str, str]:
    """Verifica il token corrente e ritorna ruolo e nome (usato dal frontend al load)."""
    return {"role": identity.role, "nome": identity.nome}
