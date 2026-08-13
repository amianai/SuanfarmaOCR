"""Inizializzazione al primo avvio: schema del database e utente amministratore.

Se il database non esiste (o è vuoto) viene creato da zero:
1. schema base: tabella `documenti` + indice full-text FTS5 con i suoi trigger;
2. migrazioni Alembic, che aggiungono tutto il resto (utenti, commenti, chunk…);
3. utente `Admin` con una password casuale, **stampata a video** una sola volta.

I documenti NON vengono creati qui: restano nella cartella `DATA_DIR` e si
caricano dall'interfaccia (upload) o si indicizzano con `POST /admin/reindex`.
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import passwords
from .config import PROJECT_ROOT, settings
from .db import SessionLocal, engine

logger = logging.getLogger(__name__)

NOME_ADMIN = "Admin"

# Schema base (documenti + FTS5 + trigger di sincronizzazione dell'indice).
# Le migrazioni Alembic partono dal presupposto che questa tabella esista.
_SCHEMA_BASE = """
CREATE TABLE IF NOT EXISTS documenti (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_file        TEXT    NOT NULL UNIQUE,
    cartella         TEXT    NOT NULL,
    percorso_pdf     TEXT    NOT NULL,
    percorso_md      TEXT    NOT NULL,
    contenuto_md     TEXT    NOT NULL DEFAULT '',
    anteprima        TEXT    NOT NULL DEFAULT '',
    descrizione      TEXT    NOT NULL DEFAULT '',
    data_documento   TEXT    NOT NULL DEFAULT '',
    num_pagine       INTEGER NOT NULL DEFAULT 0,
    scrittura        INTEGER NOT NULL DEFAULT 0,
    note             TEXT    NOT NULL DEFAULT '',
    validita         TEXT    NOT NULL DEFAULT '',
    is_preferito     INTEGER NOT NULL DEFAULT 0,
    annotazioni_team TEXT    NOT NULL DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS documenti_fts USING fts5(
    nome_file, contenuto_md, descrizione, annotazioni_team,
    content='documenti', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS documenti_ai AFTER INSERT ON documenti BEGIN
    INSERT INTO documenti_fts(rowid, nome_file, contenuto_md, descrizione, annotazioni_team)
    VALUES (new.id, new.nome_file, new.contenuto_md, new.descrizione, new.annotazioni_team);
END;

CREATE TRIGGER IF NOT EXISTS documenti_au AFTER UPDATE ON documenti BEGIN
    INSERT INTO documenti_fts(documenti_fts, rowid, nome_file, contenuto_md, descrizione, annotazioni_team)
    VALUES ('delete', old.id, old.nome_file, old.contenuto_md, old.descrizione, old.annotazioni_team);
    INSERT INTO documenti_fts(rowid, nome_file, contenuto_md, descrizione, annotazioni_team)
    VALUES (new.id, new.nome_file, new.contenuto_md, new.descrizione, new.annotazioni_team);
END;

CREATE TRIGGER IF NOT EXISTS documenti_ad AFTER DELETE ON documenti BEGIN
    INSERT INTO documenti_fts(documenti_fts, rowid, nome_file, contenuto_md, descrizione, annotazioni_team)
    VALUES ('delete', old.id, old.nome_file, old.contenuto_md, old.descrizione, old.annotazioni_team);
END;
"""


def _tabella_esiste(nome: str) -> bool:
    with engine.connect() as conn:
        return (
            conn.execute(
                text("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = :n"),
                {"n": nome},
            ).first()
            is not None
        )


def _crea_schema_base() -> None:
    """Crea documenti + FTS5 + trigger se mancano (idempotente)."""
    raw = engine.raw_connection()
    try:
        raw.executescript(_SCHEMA_BASE)
        raw.commit()
    finally:
        raw.close()


def _applica_migrazioni() -> None:
    """Porta lo schema alla versione più recente (equivale a `alembic upgrade head`)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "alembic"))
    command.upgrade(cfg, "head")


def _stampa_credenziali(nome: str, password: str) -> None:
    """Banner ben visibile: è l'unica occasione per leggere la password in chiaro."""
    riga = "=" * 68
    print(
        f"\n{riga}\n"
        f"  UTENTE AMMINISTRATORE CREATO\n"
        f"{riga}\n"
        f"    Nome utente:  {nome}\n"
        f"    Password:     {password}\n\n"
        f"  Annotala adesso: non sarà più visibile (nel database è salvata\n"
        f"  solo in forma cifrata). Se la perdi, rigenerala con:\n"
        f"      python -m app.reset_admin\n"
        f"{riga}\n",
        flush=True,
    )


def assicura_admin(db: Session) -> str | None:
    """Garantisce che esista un `Admin` attivo e con password.

    Ritorna la password generata (da stampare) se l'ha dovuta creare, altrimenti
    None. Copre due casi: database nuovo, e database in cui l'utente Admin
    esiste già ma è senza password (è così che lo crea la migrazione
    dell'identità) — senza questo passaggio non si potrebbe accedere.
    """
    from ..models.collab import Utente

    admin = db.query(Utente).filter(Utente.nome == NOME_ADMIN).first()
    if admin is None:
        admin = Utente(nome=NOME_ADMIN, attivo=1, amministratore=1, password_hash="")
        db.add(admin)

    # L'account amministratore principale è sempre attivo e sempre admin.
    admin.attivo = 1
    admin.amministratore = 1

    password = None
    if not admin.password_hash:
        password = passwords.genera_password()
        admin.password_hash = passwords.hash_password(password)
    db.commit()
    return password


def inizializza() -> None:
    """Prepara il database all'avvio dell'applicazione (idempotente)."""
    nuovo = not _tabella_esiste("documenti")
    if nuovo:
        logger.info("Database non trovato in %s: creazione da zero.", settings.data_dir)
        _crea_schema_base()
    _applica_migrazioni()

    with SessionLocal() as db:
        password = assicura_admin(db)
    if password:
        _stampa_credenziali(NOME_ADMIN, password)
