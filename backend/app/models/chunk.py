"""Model dei chunk per la ricerca semantica.

Ogni documento viene spezzato in più chunk; per ciascuno salviamo il testo e il
vettore di embedding (BLOB float32) direttamente in SQLite. Nessun database
vettoriale: a questa scala (~migliaia di chunk) il confronto in memoria con
numpy è questione di millisecondi.
"""

from sqlalchemy import ForeignKey, Integer, LargeBinary, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    documento_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documenti.id"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    testo: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # float32 normalizzato
