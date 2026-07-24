"""Schemi Pydantic per input/output delle API."""

from pydantic import BaseModel, ConfigDict


class DocumentoBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome_file: str
    cartella: str
    descrizione: str
    data_documento: str
    num_pagine: int
    validita: str
    is_preferito: int


class DocumentoListItem(DocumentoBase):
    """Voce sintetica per la lista (con anteprima/snippet)."""

    anteprima: str = ""
    snippet: str = ""
    # True se il documento è emerso SOLO per vicinanza semantica (nessun match
    # per parola): la UI mostra il badge "Trovato per significato".
    match_semantico: bool = False


class DocumentoDetail(DocumentoBase):
    """Dettaglio completo del documento."""

    percorso_pdf: str
    percorso_md: str
    contenuto_md: str
    scrittura: int
    note: str
    annotazioni_team: str


class DocumentoListResponse(BaseModel):
    total: int
    items: list[DocumentoListItem]
