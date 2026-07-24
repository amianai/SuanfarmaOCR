"""add is_deleted soft-delete column

Revision ID: 1514d475e34d
Revises: 
Create Date: 2026-07-09 19:12:19.167172

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1514d475e34d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aggiunge la colonna is_deleted (soft-delete) alla tabella esistente.

    La tabella `documenti` è preesistente (creata da init_db.py di Streamlit).
    Aggiungiamo solo la colonna, con default 0 così i 257 documenti esistenti
    restano tutti attivi. I trigger FTS5 non sono impattati (referenziano
    colonne esplicite, non is_deleted).
    """
    # Idempotenza: aggiungi solo se la colonna non esiste già.
    conn = op.get_bind()
    cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(documenti)")]
    if "is_deleted" not in cols:
        op.add_column(
            "documenti",
            sa.Column("is_deleted", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    """Rimuove la colonna is_deleted."""
    conn = op.get_bind()
    cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(documenti)")]
    if "is_deleted" in cols:
        op.drop_column("documenti", "is_deleted")
