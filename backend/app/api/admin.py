"""Router admin: CRUD documenti, gestione utenti, audit. Tutto dietro token admin."""

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..models.collab import EventoAudit, PreferitoUtente, Utente
from ..models.documento import Documento
from ..models.schemas import DocumentoDetail
from ..services import conversion, embeddings, excel_sync, ocr
from .deps import Identity, require_admin
from .documents import is_preferito_per_utente

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _audit(db: Session, doc_id: int, autore: str, azione: str, dettaglio: str = "") -> None:
    """Registra un evento di tracciabilità (committato insieme all'operazione)."""
    db.add(
        EventoAudit(
            documento_id=doc_id,
            autore=autore,
            azione=azione,
            dettaglio=dettaglio,
            creato_il=datetime.now(timezone.utc).isoformat(),
        )
    )

# Solo lettere/numeri/trattini/underscore: blocca path traversal sul nome faldone.
CARTELLA_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
DATA_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def calcola_prossimo_id(db: Session, cartella: str) -> str:
    """Prossimo ID libero nel faldone (es. dopo B07-D039 -> B07-D040)."""
    nomi = db.execute(
        select(Documento.nome_file).where(Documento.cartella == cartella)
    ).scalars().all()
    max_n = 0
    for nome in nomi:
        m = re.search(r"D(\d+)$", nome)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"{cartella}-D{max_n + 1:03d}"


class UploadResult(BaseModel):
    documento: DocumentoDetail
    ocr_ok: bool
    warning: str | None = None


@router.post("/documents", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
async def upload_documento(
    file: UploadFile = File(...),
    cartella: str = Form(...),
    descrizione: str = Form(""),
    data_documento: str = Form(""),
    validita: str = Form("si"),
    note: str = Form(""),
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_admin),
) -> UploadResult:
    cartella = cartella.strip().upper()
    if not CARTELLA_PATTERN.match(cartella):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Codice faldone non valido: solo lettere, numeri, trattini o underscore (max 20).",
        )
    if validita not in ("si", "no"):
        raise HTTPException(status_code=422, detail="validita deve essere 'si' o 'no'")
    if data_documento and not DATA_PATTERN.match(data_documento):
        raise HTTPException(status_code=422, detail="data_documento deve essere gg/mm/aaaa")

    raw = await file.read()
    nome_orig = (file.filename or "").lower()
    try:
        if nome_orig.endswith((".tif", ".tiff")):
            pdf_bytes = conversion.tiff_bytes_to_pdf_bytes(raw)
        else:
            pdf_bytes = raw
        num_pagine = conversion.pdf_page_count(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"File non leggibile come PDF/TIFF: {e}")

    nuovo_id = calcola_prossimo_id(db, cartella)
    pdf_dir = settings.documenti_pdf_dir / cartella
    md_dir = settings.testo_estratto_dir / cartella
    pdf_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{nuovo_id}.pdf"
    md_path = md_dir / f"{nuovo_id}.md"
    pdf_path.write_bytes(pdf_bytes)

    testo_ocr = ""
    warning = None
    try:
        testo_ocr = ocr.ocr_pdf_file(pdf_path)
        md_path.write_text(testo_ocr, encoding="utf-8")
    except Exception as e:  # OCR fallito: il PDF resta salvato, testo recuperabile dopo
        warning = f"OCR non riuscito: {e}. Il PDF è stato salvato; l'OCR può essere ripetuto."

    doc = Documento(
        nome_file=nuovo_id,
        cartella=cartella,
        percorso_pdf=f"documenti_pdf/{cartella}/{nuovo_id}.pdf",
        percorso_md=f"testo_estratto/{cartella}/{nuovo_id}.md",
        contenuto_md=testo_ocr,
        anteprima=" ".join(testo_ocr.split())[:300],
        descrizione=descrizione.strip(),
        data_documento=data_documento.strip(),
        num_pagine=num_pagine,
        note=note.strip(),
        validita=validita,
    )
    db.add(doc)
    db.flush()  # assegna l'id per l'audit
    _audit(db, doc.id, identity.nome, "upload", f"{nuovo_id} ({file.filename})")
    db.commit()  # i trigger FTS5 indicizzano automaticamente la ricerca per parola
    db.refresh(doc)

    # Indicizzazione semantica del nuovo documento (best-effort: un errore qui
    # non deve far fallire l'upload, il documento è già salvato e ricercabile per parola).
    if testo_ocr:
        try:
            embeddings.index_document(db, doc)
        except Exception as e:  # noqa: BLE001
            warning = (warning + " " if warning else "") + f"Indicizzazione semantica rimandata: {e}"
    return UploadResult(
        documento=_detail_per_utente(db, doc, identity.nome), ocr_ok=not warning, warning=warning
    )


class MetadataUpdate(BaseModel):
    descrizione: str | None = None
    data_documento: str | None = None
    num_pagine: int | None = None
    scrittura: int | None = None
    note: str | None = None
    validita: str | None = None


def _get_or_404(db: Session, doc_id: int, include_deleted: bool = False) -> Documento:
    doc = db.get(Documento, doc_id)
    if doc is None or (doc.is_deleted and not include_deleted):
        raise HTTPException(status_code=404, detail="Documento non trovato")
    return doc


def _detail_per_utente(db: Session, doc: Documento, nome: str) -> DocumentoDetail:
    """DocumentoDetail con is_preferito PERSONALE dell'utente corrente.

    Mai ritornare l'ORM nudo: il suo is_preferito è la colonna legacy
    condivisa e farebbe apparire preferiti 'fantasma' dopo le operazioni admin.
    """
    det = DocumentoDetail.model_validate(doc)
    return det.model_copy(
        update={"is_preferito": 1 if is_preferito_per_utente(db, doc.id, nome) else 0}
    )


@router.patch("/documents/{doc_id}", response_model=DocumentoDetail)
def modifica_metadati(
    doc_id: int,
    body: MetadataUpdate,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_admin),
) -> DocumentoDetail:
    doc = _get_or_404(db, doc_id)
    if body.validita is not None and body.validita not in ("si", "no"):
        raise HTTPException(status_code=422, detail="validita deve essere 'si' o 'no'")
    if body.data_documento and not DATA_PATTERN.match(body.data_documento):
        raise HTTPException(status_code=422, detail="data_documento deve essere gg/mm/aaaa")

    campi_cambiati = []
    validita_precedente = doc.validita
    for campo, valore in body.model_dump(exclude_unset=True).items():
        if valore is not None:
            nuovo = valore.strip() if isinstance(valore, str) else valore
            if getattr(doc, campo) != nuovo:
                campi_cambiati.append(campo)
            setattr(doc, campo, nuovo)

    # La validità ha rilevanza operativa: evento dedicato con vecchio→nuovo valore.
    if "validita" in campi_cambiati:
        _audit(db, doc.id, identity.nome, "validita", f"{validita_precedente}→{doc.validita}")
        campi_cambiati.remove("validita")
    if campi_cambiati:
        _audit(db, doc.id, identity.nome, "metadati", ", ".join(sorted(campi_cambiati)))

    db.commit()
    db.refresh(doc)
    return _detail_per_utente(db, doc, identity.nome)


@router.delete("/documents/{doc_id}", response_model=DocumentoDetail)
def soft_delete_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_admin),
) -> DocumentoDetail:
    """Soft-delete: il documento sparisce dall'archivio ma file e riga restano.

    Scelta deliberata per materiale storico con nominativi: la cancellazione
    fisica è irreversibile e rischiosa. Il ripristino è possibile via /restore.
    """
    doc = _get_or_404(db, doc_id)
    doc.is_deleted = 1
    _audit(db, doc.id, identity.nome, "delete", doc.nome_file)
    db.commit()
    db.refresh(doc)
    return _detail_per_utente(db, doc, identity.nome)


@router.post("/documents/{doc_id}/restore", response_model=DocumentoDetail)
def restore_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_admin),
) -> DocumentoDetail:
    doc = _get_or_404(db, doc_id, include_deleted=True)
    doc.is_deleted = 0
    _audit(db, doc.id, identity.nome, "restore", doc.nome_file)
    db.commit()
    db.refresh(doc)
    return _detail_per_utente(db, doc, identity.nome)


@router.get("/documents/deleted", response_model=list[DocumentoDetail])
def lista_eliminati(db: Session = Depends(get_db)) -> list[Documento]:
    """Cestino: documenti soft-deleted, ripristinabili."""
    return list(
        db.execute(
            select(Documento).where(Documento.is_deleted == 1).order_by(Documento.nome_file)
        ).scalars()
    )


@router.post("/reindex")
def reindex_semantico(
    tutti: bool = False, db: Session = Depends(get_db)
) -> dict:
    """(Ri)costruisce l'indice semantico. Con tutti=true ricalcola anche i già indicizzati."""
    return embeddings.reindex_all(db, solo_mancanti=not tutti)


@router.post("/resync-excel")
def resync_excel(db: Session = Depends(get_db)) -> dict:
    """Riallinea i metadati dal file Excel (senza toccare validità/preferiti/annotazioni)."""
    try:
        return excel_sync.resync_metadata(db)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Gestione utenti (lista nomi selezionabili al login) ---


class UtenteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    attivo: int


class UtenteIn(BaseModel):
    nome: str = Field(min_length=1, max_length=50)


class UtenteUpdate(BaseModel):
    attivo: bool


@router.get("/utenti", response_model=list[UtenteOut])
def lista_utenti(db: Session = Depends(get_db)) -> list[Utente]:
    return list(db.execute(select(Utente).order_by(Utente.nome)).scalars())


@router.post("/utenti", response_model=UtenteOut, status_code=status.HTTP_201_CREATED)
def crea_utente(body: UtenteIn, db: Session = Depends(get_db)) -> Utente:
    nome = body.nome.strip()
    if not nome:
        raise HTTPException(status_code=422, detail="Il nome non può essere vuoto")
    esistente = db.scalar(select(Utente).where(Utente.nome == nome))
    if esistente is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nome già presente")
    utente = Utente(nome=nome, attivo=1)
    db.add(utente)
    db.commit()
    db.refresh(utente)
    return utente


def _ultimo_attivo(db: Session, utente: Utente) -> bool:
    """Vero se questo è l'unico utente attivo rimasto.

    Guardia anti-lockout: senza nomi attivi il login diventa impossibile
    per chiunque (admin compreso).
    """
    if utente.attivo != 1:
        return False
    altri = db.scalar(
        select(Utente.id).where(Utente.attivo == 1, Utente.id != utente.id)
    )
    return altri is None


@router.patch("/utenti/{utente_id}", response_model=UtenteOut)
def aggiorna_utente(
    utente_id: int, body: UtenteUpdate, db: Session = Depends(get_db)
) -> Utente:
    utente = db.get(Utente, utente_id)
    if utente is None:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if not body.attivo and _ultimo_attivo(db, utente):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossibile disattivare l'ultimo utente attivo: nessuno potrebbe più accedere",
        )
    utente.attivo = 1 if body.attivo else 0
    db.commit()
    db.refresh(utente)
    return utente


@router.delete("/utenti/{utente_id}", status_code=status.HTTP_204_NO_CONTENT)
def elimina_utente(utente_id: int, db: Session = Depends(get_db)) -> None:
    """Elimina definitivamente un profilo.

    I suoi preferiti personali vengono rimossi (dati del profilo); commenti ed
    eventi audit restano perché sono storia condivisa firmata col nome.
    """
    utente = db.get(Utente, utente_id)
    if utente is None:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if _ultimo_attivo(db, utente):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossibile eliminare l'ultimo utente attivo: nessuno potrebbe più accedere",
        )
    db.query(PreferitoUtente).filter(PreferitoUtente.utente_nome == utente.nome).delete()
    db.delete(utente)
    db.commit()


# --- Audit (storico modifiche) ---


class EventoAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    documento_id: int
    autore: str
    azione: str
    dettaglio: str
    creato_il: str


@router.get("/audit", response_model=list[EventoAuditOut])
def lista_audit(
    documento_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[EventoAudit]:
    stmt = select(EventoAudit).order_by(EventoAudit.creato_il.desc(), EventoAudit.id.desc())
    if documento_id is not None:
        stmt = stmt.where(EventoAudit.documento_id == documento_id)
    return list(db.execute(stmt.limit(min(limit, 1000))).scalars())
