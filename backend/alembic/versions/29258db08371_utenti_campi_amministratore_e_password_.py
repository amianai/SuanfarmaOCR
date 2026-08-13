"""utenti: campi amministratore e password_hash

Revision ID: 29258db08371
Revises: 5cd1969029f9
Create Date: 2026-07-25 19:21:39.102251

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29258db08371'
down_revision: Union[str, Sequence[str], None] = '5cd1969029f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Credenziali individuali: flag amministratore + hash della password.

    Sostituisce il modello a password condivise: il ruolo diventa una proprietà
    dell'account (`amministratore`) invece di dipendere da quale password
    condivisa si digita.

    `password_hash` vuoto = password non ancora assegnata (l'utente non può
    accedere finché l'admin non gliene imposta una). L'utente `Admin` viene
    promosso ad amministratore; la sua password viene creata dal bootstrap al
    primo avvio se assente.
    """
    op.add_column(
        "utenti",
        sa.Column("amministratore", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "utenti",
        sa.Column("password_hash", sa.Text(), nullable=False, server_default=""),
    )
    op.get_bind().exec_driver_sql(
        "UPDATE utenti SET amministratore = 1 WHERE nome = 'Admin'"
    )


def downgrade() -> None:
    op.drop_column("utenti", "password_hash")
    op.drop_column("utenti", "amministratore")
