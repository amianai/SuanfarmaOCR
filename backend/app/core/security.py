"""Sicurezza: autenticazione a segreti condivisi + JWT con refresh scorrevole.

Modello a due livelli:
- viewer: sola lettura (consultazione, ricerca, download)
- admin: CRUD completo (upload, modifica, cancellazione)

Le due password sono segreti CONDIVISI di team, confrontati in tempo costante
(hmac.compare_digest). La sicurezza di sessione vera è data dal JWT firmato.
"""

import hmac
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from .config import settings


def _verify(plain: str, expected: str) -> bool:
    return bool(expected) and hmac.compare_digest(plain, expected)


def authenticate(password: str) -> str | None:
    """Ritorna il ruolo ('admin'/'viewer') se la password combacia, altrimenti None.

    L'admin ha precedenza: se qualcuno imposta la stessa password per entrambi,
    ottiene i privilegi più alti.
    """
    if _verify(password, settings.admin_password):
        return "admin"
    if _verify(password, settings.viewer_password):
        return "viewer"
    return None


def create_access_token(role: str, nome: str) -> tuple[str, int]:
    """Crea un JWT con ruolo e nome utente. Ritorna (token, secondi_di_validità)."""
    expires_in = settings.access_token_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "role": role,
        "nome": nome,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_token(token: str) -> dict | None:
    """Decodifica e valida il JWT. Ritorna il payload o None se non valido/scaduto."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
