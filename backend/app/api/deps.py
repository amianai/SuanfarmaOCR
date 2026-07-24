"""Dependency di autenticazione/autorizzazione FastAPI.

Usa `HTTPBearer(auto_error=False)` così gestiamo noi la risposta 401 quando il
token manca. Il token porta ruolo (viewer/admin) e nome utente (identità
leggera scelta al login dalla lista gestita dall'admin).

Refresh scorrevole: se al token resta meno di metà vita, ne emettiamo uno nuovo
nell'header `X-Refreshed-Token` che il frontend sostituisce in trasparenza.
"""

from datetime import datetime, timezone
from typing import NamedTuple

from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core import security
from ..core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


class Identity(NamedTuple):
    role: str
    nome: str


def get_current_identity(
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Identity:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticazione richiesta",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = security.decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = payload.get("role")
    nome = payload.get("nome", "")
    exp = payload.get("exp")
    if not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token non valido")

    # Refresh scorrevole
    if exp:
        remaining = exp - datetime.now(timezone.utc).timestamp()
        if remaining < (settings.access_token_minutes * 60) / 2:
            new_token, _ = security.create_access_token(role, nome)
            response.headers["X-Refreshed-Token"] = new_token

    return Identity(role=role, nome=nome)


def require_viewer(identity: Identity = Depends(get_current_identity)) -> Identity:
    """Sia viewer che admin possono accedere alle risorse di lettura."""
    return identity


def require_admin(identity: Identity = Depends(get_current_identity)) -> Identity:
    """Solo admin: operazioni CRUD."""
    if identity.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permessi di amministratore richiesti",
        )
    return identity
