"""Hashing delle password degli utenti.

Algoritmo: SHA-1 con **salt casuale per-utente**, come concordato col committente.
Formato memorizzato: ``sha1$<salt>$<digest>``

Il salt (stringa casuale diversa per ogni utente) fa sì che due persone con la
stessa password abbiano hash diversi, e rende inutilizzabili le rainbow table.
Il prefisso con il nome dell'algoritmo permette in futuro di introdurre un
hashing più robusto senza invalidare le password già memorizzate.

Nota: SHA-1 è un hash veloce; per le password gli standard attuali sono bcrypt,
scrypt o PBKDF2. Scelta del committente, documentata qui per trasparenza.
"""

import hashlib
import hmac
import secrets
import string

ALGORITMO = "sha1"
_SALT_BYTES = 16

# Alfabeto per le password generate: senza caratteri ambigui (O/0, l/1/I) così
# sono leggibili e dettabili a voce senza errori.
_ALFABETO = "".join(
    c for c in (string.ascii_letters + string.digits) if c not in "O0lI1"
)


def genera_password(lunghezza: int = 12) -> str:
    """Password casuale leggibile, da comunicare all'utente."""
    return "".join(secrets.choice(_ALFABETO) for _ in range(lunghezza))


def _digest(password: str, salt: str) -> str:
    return hashlib.sha1(f"{salt}{password}".encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """Ritorna la stringa da salvare nel DB: ``sha1$<salt>$<digest>``."""
    salt = secrets.token_hex(_SALT_BYTES)
    return f"{ALGORITMO}${salt}${_digest(password, salt)}"


def verify_password(password: str, memorizzato: str) -> bool:
    """Verifica la password contro l'hash memorizzato (confronto a tempo costante)."""
    if not password or not memorizzato:
        return False
    try:
        algoritmo, salt, digest = memorizzato.split("$", 2)
    except ValueError:
        return False  # formato non riconosciuto: password non impostata o corrotta
    if algoritmo != ALGORITMO:
        return False
    return hmac.compare_digest(_digest(password, salt), digest)
