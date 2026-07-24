"""Model SQLAlchemy della tabella `documenti`.

La tabella e l'indice full-text FTS5 (con i relativi trigger di sincronizzazione)
sono preesistenti nel database dell'archivio; le colonne aggiunte dopo — come
`is_deleted` per il soft-delete — sono gestite dalle migrazioni Alembic.
"""

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class Documento(Base):
    __tablename__ = "documenti"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome_file: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    cartella: Mapped[str] = mapped_column(Text, nullable=False)
    percorso_pdf: Mapped[str] = mapped_column(Text, nullable=False)
    percorso_md: Mapped[str] = mapped_column(Text, nullable=False)
    contenuto_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    anteprima: Mapped[str] = mapped_column(Text, nullable=False, default="")
    descrizione: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data_documento: Mapped[str] = mapped_column(Text, nullable=False, default="")
    num_pagine: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scrittura: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    validita: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_preferito: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    annotazioni_team: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
