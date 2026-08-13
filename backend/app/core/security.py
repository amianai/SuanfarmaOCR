"""Sicurezza: autenticazione con credenziali individuali + JWT con refresh scorrevole.

Ogni utente ha la propria password (hash salted nella tabella `utenti`, vedi
core/passwords.py) e un flag `amministratore` che determina il ruolo:
- viewer: sola lettura (consultazione, ricerca, download)
- admin: CRUD completo (upload, modifica, cancellazione)

Il ruolo è quindi una proprietà della persona, non di quale password si digita.
Nel JWT continuano a viaggiare `role` e `nome`, così tutta l'autorizzazione a
valle (require_admin/require_viewer) resta invariata.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from . import passwords
from .config import settings


def ruolo_di(utente) -> str:
    """Ruolo derivato dal flag amministratore dell'account."""
    return "admin" if utente.amministratore == 1 else "viewer"


def authenticate(db: Session, nome: str, password: str):
    """Verifica le credenziali sul database.

    Ritorna l'utente se nome e password combaciano ed è attivo, altrimenti None.
    Un utente senza password impostata (password_hash vuoto) non può accedere:
    deve prima riceverne una dall'amministratore.
    """
    from ..models.collab import Utente

    utente = db.query(Utente).filter(Utente.nome == nome, Utente.attivo == 1).first()
    if utente is None:
        return None
    if not passwords.verify_password(password, utente.password_hash):
        return None
    return utente


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
