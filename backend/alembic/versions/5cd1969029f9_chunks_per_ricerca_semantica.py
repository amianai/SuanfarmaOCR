"""chunks per ricerca semantica

Revision ID: 5cd1969029f9
Revises: d31acd077ed8
Create Date: 2026-07-21 15:28:01.750607

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5cd1969029f9'
down_revision: Union[str, Sequence[str], None] = 'd31acd077ed8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabella dei chunk per la ricerca semantica.

    Vuota alla creazione: viene popolata dal servizio embeddings (reindex_all o
    l'hook di upload). L'embedding è un BLOB float32 già normalizzato.
    """
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documenti.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("testo", sa.Text(), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=False),
    )
    op.create_index("ix_chunks_documento_id", "chunks", ["documento_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_documento_id", table_name="chunks")
    op.drop_table("chunks")
