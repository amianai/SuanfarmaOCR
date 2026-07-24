"""Router documenti: lista/ricerca, dettaglio, PDF, testo, preferiti personali, commenti."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..models.collab import Commento, PreferitoUtente
from ..models.documento import Documento
from ..models.schemas import DocumentoDetail, DocumentoListItem, DocumentoListResponse
from ..services import search as search_service
from .deps import Identity, require_viewer

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentoListResponse)
def lista_documenti(
    q: str = "",
    cartella: list[str] = Query(default=[]),
    solo_preferiti: bool = False,
    validita: str = search_service.VALIDITA_TUTTI,
    anno_da: int | None = None,
    anno_a: int | None = None,
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_viewer),
) -> DocumentoListResponse:
    total, rows = search_service.search_documents(
        db, identity.nome, q, cartella, solo_preferiti, validita, anno_da, anno_a, limit, offset
    )
    items = [DocumentoListItem(**r) for r in rows]
    return DocumentoListResponse(total=total, items=items)


class CartellaInfo(BaseModel):
    cartella: str
    anno_min: int | None
    anno_max: int | None
    documenti: int


@router.get("/cartelle", response_model=list[CartellaInfo])
def lista_cartelle(
    db: Session = Depends(get_db),
    _identity: Identity = Depends(require_viewer),
) -> list[CartellaInfo]:
    """Faldoni con il range di anni dei documenti contenuti (per le etichette dei filtri)."""
    rows = db.execute(
        text(
            """
            SELECT cartella,
                   MIN(CASE WHEN data_documento != ''
                        THEN CAST(SUBSTR(data_documento, 7, 4) AS INTEGER) END) AS anno_min,
                   MAX(CASE WHEN data_documento != ''
                        THEN CAST(SUBSTR(data_documento, 7, 4) AS INTEGER) END) AS anno_max,
                   COUNT(*) AS documenti
            FROM documenti WHERE is_deleted = 0
            GROUP BY cartella ORDER BY cartella
            """
        )
    ).mappings().all()
    return [CartellaInfo(**r) for r in rows]


def _get_active_or_404(db: Session, doc_id: int) -> Documento:
    doc = db.get(Documento, doc_id)
    if doc is None or doc.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento non trovato")
    return doc


def is_preferito_per_utente(db: Session, doc_id: int, nome: str) -> bool:
    """Vero se il documento è tra i preferiti PERSONALI dell'utente.

    Da usare ovunque si ritorni un DocumentoDetail: il campo is_preferito
    dell'ORM è una colonna legacy CONDIVISA fra tutti gli utenti e non va mai
    esposta — mostrarla fa apparire preferiti 'fantasma'.
    """
    return (
        db.scalar(
            select(PreferitoUtente.id).where(
                PreferitoUtente.documento_id == doc_id,
                PreferitoUtente.utente_nome == nome,
            )
        )
        is not None
    )


@router.get("/{doc_id}", response_model=DocumentoDetail)
def dettaglio_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_viewer),
) -> DocumentoDetail:
    doc = _get_active_or_404(db, doc_id)
    det = DocumentoDetail.model_validate(doc)
    # is_preferito è personale: sovrascrive il campo legacy condiviso.
    return det.model_copy(
        update={"is_preferito": 1 if is_preferito_per_utente(db, doc_id, identity.nome) else 0}
    )


def _resolve_within(base_dir: Path, rel_path: str) -> Path:
    """Risolve rel_path dentro base_dir bloccando path traversal."""
    candidate = (settings.documenti_pdf_dir.parent / rel_path).resolve()
    base = base_dir.resolve()
    if base not in candidate.parents and candidate != base:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Percorso non valido")
    return candidate


@router.get("/{doc_id}/pdf")
def pdf_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    _identity: Identity = Depends(require_viewer),
) -> FileResponse:
    doc = _get_active_or_404(db, doc_id)
    pdf_path = _resolve_within(settings.documenti_pdf_dir, doc.percorso_pdf)
    if not pdf_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File PDF non trovato")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{doc.nome_file}.pdf")


@router.get("/{doc_id}/text", response_class=PlainTextResponse)
def testo_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    _identity: Identity = Depends(require_viewer),
) -> str:
    doc = _get_active_or_404(db, doc_id)
    return doc.contenuto_md or ""


# --- Preferiti personali ---


class PreferitoUpdate(BaseModel):
    preferito: bool


@router.put("/{doc_id}/preferito")
def set_preferito(
    doc_id: int,
    body: PreferitoUpdate,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_viewer),
) -> dict[str, bool]:
    _get_active_or_404(db, doc_id)
    existing = db.scalar(
        select(PreferitoUtente).where(
            PreferitoUtente.documento_id == doc_id,
            PreferitoUtente.utente_nome == identity.nome,
        )
    )
    if body.preferito and existing is None:
        db.add(PreferitoUtente(utente_nome=identity.nome, documento_id=doc_id))
        db.commit()
    elif not body.preferito and existing is not None:
        db.delete(existing)
        db.commit()
    return {"preferito": body.preferito}


# --- Commenti firmati ---


class CommentoIn(BaseModel):
    testo: str = Field(min_length=1, max_length=5000)


class CommentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    autore: str
    testo: str
    creato_il: str


@router.get("/{doc_id}/commenti", response_model=list[CommentoOut])
def lista_commenti(
    doc_id: int,
    db: Session = Depends(get_db),
    _identity: Identity = Depends(require_viewer),
) -> list[Commento]:
    _get_active_or_404(db, doc_id)
    return list(
        db.execute(
            select(Commento)
            .where(Commento.documento_id == doc_id)
            .order_by(Commento.creato_il, Commento.id)
        ).scalars()
    )


@router.post("/{doc_id}/commenti", response_model=CommentoOut, status_code=status.HTTP_201_CREATED)
def aggiungi_commento(
    doc_id: int,
    body: CommentoIn,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_viewer),
) -> Commento:
    _get_active_or_404(db, doc_id)
    commento = Commento(
        documento_id=doc_id,
        autore=identity.nome,
        testo=body.testo.strip(),
        creato_il=datetime.now(timezone.utc).isoformat(),
    )
    db.add(commento)
    db.commit()
    db.refresh(commento)
    return commento


@router.delete("/{doc_id}/commenti/{commento_id}", status_code=status.HTTP_204_NO_CONTENT)
def elimina_commento(
    doc_id: int,
    commento_id: int,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_viewer),
) -> None:
    commento = db.get(Commento, commento_id)
    if commento is None or commento.documento_id != doc_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commento non trovato")
    # Solo l'autore del commento o un admin possono eliminarlo.
    if identity.role != "admin" and commento.autore != identity.nome:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Puoi eliminare solo i tuoi commenti",
        )
    db.delete(commento)
    db.commit()
