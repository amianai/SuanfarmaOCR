"""Fixture condivise: utenti di test con credenziali individuali note.

Dal passaggio alle password per-utente i test non possono più usare password
condivise di configurazione: servono account veri nel database. Qui creiamo due
utenti dedicati (uno amministratore, uno di sola consultazione) con password
note, e li rimuoviamo alla fine della sessione di test.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import passwords
from app.core.db import SessionLocal
from app.main import app
from app.models.collab import Utente

client = TestClient(app)

# Prefisso "Zz" per non confondersi con gli utenti reali e ordinarsi in fondo.
UTENTE_ADMIN = "ZzTestAdmin"
UTENTE_VIEWER = "ZzTestViewer"
PASSWORD_TEST = "password-di-test-123"


def crea_utente(nome: str, password: str, amministratore: bool = False) -> None:
    """Crea (o reimposta) un utente con password nota."""
    with SessionLocal() as db:
        utente = db.query(Utente).filter(Utente.nome == nome).first()
        if utente is None:
            utente = Utente(nome=nome)
            db.add(utente)
        utente.attivo = 1
        utente.amministratore = 1 if amministratore else 0
        utente.password_hash = passwords.hash_password(password)
        db.commit()


def rimuovi_utenti(nomi: list[str]) -> None:
    with SessionLocal() as db:
        for nome in nomi:
            db.execute(
                text("DELETE FROM preferiti_utente WHERE utente_nome = :n"), {"n": nome}
            )
            db.execute(text("DELETE FROM commenti WHERE autore = :n"), {"n": nome})
            db.execute(text("DELETE FROM utenti WHERE nome = :n"), {"n": nome})
        db.commit()


def login(nome: str, password: str = PASSWORD_TEST) -> dict:
    """Header Authorization per l'utente indicato."""
    r = client.post("/auth/login", json={"nome": nome, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session", autouse=True)
def _utenti_di_test():
    """Crea gli utenti di test per tutta la sessione e li ripulisce alla fine."""
    crea_utente(UTENTE_ADMIN, PASSWORD_TEST, amministratore=True)
    crea_utente(UTENTE_VIEWER, PASSWORD_TEST, amministratore=False)
    yield
    rimuovi_utenti([UTENTE_ADMIN, UTENTE_VIEWER])


@pytest.fixture()
def admin_headers() -> dict:
    return login(UTENTE_ADMIN)


@pytest.fixture()
def viewer_headers() -> dict:
    return login(UTENTE_VIEWER)


@pytest.fixture()
def admin_token() -> str:
    r = client.post("/auth/login", json={"nome": UTENTE_ADMIN, "password": PASSWORD_TEST})
    return r.json()["access_token"]


@pytest.fixture()
def viewer_token() -> str:
    r = client.post("/auth/login", json={"nome": UTENTE_VIEWER, "password": PASSWORD_TEST})
    return r.json()["access_token"]
