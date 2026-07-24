"""Model per l'identità leggera: utenti (nomi), preferiti personali, commenti, audit.

I nomi utente sono denormalizzati (TEXT, nessuna FK su utenti) nelle tabelle
dati: se un nome viene disattivato o cambiato, i dati storici restano leggibili
— comportamento corretto per commenti e audit trail.
"""

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class Utente(Base):
    """Nome selezionabile al login (lista gestita dall'admin)."""

    __tablename__ = "utenti"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    attivo: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class PreferitoUtente(Base):
    __tablename__ = "preferiti_utente"
    __table_args__ = (UniqueConstraint("utente_nome", "documento_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utente_nome: Mapped[str] = mapped_column(Text, nullable=False)
    documento_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documenti.id"), nullable=False
    )


class Commento(Base):
    __tablename__ = "commenti"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    documento_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documenti.id"), nullable=False
    )
    autore: Mapped[str] = mapped_column(Text, nullable=False)
    testo: Mapped[str] = mapped_column(Text, nullable=False)
    creato_il: Mapped[str] = mapped_column(Text, nullable=False)  # ISO 8601


class EventoAudit(Base):
    __tablename__ = "eventi_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    documento_id: Mapped[int] = mapped_column(Integer, nullable=False)
    autore: Mapped[str] = mapped_column(Text, nullable=False)
    azione: Mapped[str] = mapped_column(Text, nullable=False)  # upload|validita|metadati|delete|restore
    dettaglio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    creato_il: Mapped[str] = mapped_column(Text, nullable=False)  # ISO 8601
