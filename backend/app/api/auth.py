"""Router di autenticazione: credenziali individuali e cambio password."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import passwords, security
from ..core.bootstrap import NOME_ADMIN
from ..core.config import settings
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


class CambioPasswordRequest(BaseModel):
    password_attuale: str
    password_nuova: str = Field(min_length=8, max_length=128)


@router.get("/utenti", response_model=list[str])
def lista_nomi(db: Session = Depends(get_db)) -> list[str]:
    """Nomi attivi selezionabili al login.

    Endpoint pubblico: popola il menu del form di login. Espone solo i nomi
    (nessuna password né ruolo) — dato a bassa sensibilità per un'app interna.
    """
    return list(
        db.execute(
            select(Utente.nome).where(Utente.attivo == 1).order_by(Utente.nome)
        ).scalars()
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    utente = security.authenticate(db, body.nome.strip(), body.password)
    if utente is None:
        # Messaggio volutamente generico: non rivela se il nome esiste o se è
        # la password a essere sbagliata.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Nome o password non validi"
        )
    ruolo = security.ruolo_di(utente)
    token, expires_in = security.create_access_token(ruolo, utente.nome)
    return TokenResponse(
        access_token=token, role=ruolo, nome=utente.nome, expires_in=expires_in
    )


@router.get("/me")
def me(identity: Identity = Depends(get_current_identity)) -> dict:
    """Ruolo e nome dell'utente collegato, più i flag di funzionalità attive."""
    return {
        "role": identity.role,
        "nome": identity.nome,
        "puo_cambiare_password": identity.nome != NOME_ADMIN,
        "chat_enabled": settings.chat_enabled,
    }


@router.patch("/password", status_code=status.HTTP_204_NO_CONTENT)
def cambia_password(
    body: CambioPasswordRequest,
    db: Session = Depends(get_db),
    identity: Identity = Depends(get_current_identity),
) -> None:
    """L'utente cambia la PROPRIA password (serve quella attuale).

    L'account `Admin` è escluso: è l'account di servizio immutabile, la sua
    password si rigenera solo dal server con `python -m app.reset_admin`.
    """
    if identity.nome == NOME_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"La password dell'account {NOME_ADMIN} non è modificabile dall'interfaccia",
        )
    utente = db.query(Utente).filter(Utente.nome == identity.nome).first()
    if utente is None:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if not passwords.verify_password(body.password_attuale, utente.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password attuale errata"
        )
    utente.password_hash = passwords.hash_password(body.password_nuova)
    db.commit()
