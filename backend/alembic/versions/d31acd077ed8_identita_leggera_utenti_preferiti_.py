"""identita leggera: utenti, preferiti_utente, commenti, eventi_audit

Revision ID: d31acd077ed8
Revises: 1514d475e34d
Create Date: 2026-07-10 02:10:02.522812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd31acd077ed8'
down_revision: Union[str, Sequence[str], None] = '1514d475e34d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea le tabelle dell'identità leggera e migra i dati legacy.

    - utenti: lista nomi selezionabili al login (seed: "Admin")
    - preferiti_utente: preferiti personali (i vecchi is_preferito=1 migrano
      con nome "Team" così non si perde nulla)
    - commenti: thread firmati per documento (le vecchie annotazioni_team non
      vuote migrano come primo commento con autore "Team")
    - eventi_audit: tracciabilità di upload/validità/metadati/delete/restore

    I campi legacy is_preferito/annotazioni_team restano nello schema (i dati
    sono stati travasati nelle nuove tabelle), ma non vengono più letti.
    """
    op.create_table(
        "utenti",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.Text(), nullable=False, unique=True),
        sa.Column("attivo", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "preferiti_utente",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("utente_nome", sa.Text(), nullable=False),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documenti.id"), nullable=False),
        sa.UniqueConstraint("utente_nome", "documento_id"),
    )
    op.create_table(
        "commenti",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documenti.id"), nullable=False),
        sa.Column("autore", sa.Text(), nullable=False),
        sa.Column("testo", sa.Text(), nullable=False),
        sa.Column("creato_il", sa.Text(), nullable=False),
    )
    op.create_table(
        "eventi_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("documento_id", sa.Integer(), nullable=False),
        sa.Column("autore", sa.Text(), nullable=False),
        sa.Column("azione", sa.Text(), nullable=False),
        sa.Column("dettaglio", sa.Text(), nullable=False, server_default=""),
        sa.Column("creato_il", sa.Text(), nullable=False),
    )

    conn = op.get_bind()
    # Seed bootstrap: al primo avvio l'admin entra come "Admin" e crea i nomi del team.
    conn.exec_driver_sql("INSERT INTO utenti (nome, attivo) VALUES ('Admin', 1)")
    # Migrazione dati legacy (idempotente per costruzione: le tabelle sono appena nate).
    conn.exec_driver_sql(
        "INSERT INTO preferiti_utente (utente_nome, documento_id) "
        "SELECT 'Team', id FROM documenti WHERE is_preferito = 1"
    )
    conn.exec_driver_sql(
        "INSERT INTO commenti (documento_id, autore, testo, creato_il) "
        "SELECT id, 'Team', annotazioni_team, datetime('now') "
        "FROM documenti WHERE annotazioni_team != ''"
    )


def downgrade() -> None:
    """Rimuove le tabelle dell'identità leggera (i dati migrati vanno persi)."""
    op.drop_table("eventi_audit")
    op.drop_table("commenti")
    op.drop_table("preferiti_utente")
    op.drop_table("utenti")
