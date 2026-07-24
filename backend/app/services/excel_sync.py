"""Re-sync dei metadati dal file Excel (porta la logica di init_db.py).

Regole di protezione (le stesse dell'UPSERT storico):
- `validita`, `is_preferito`, `annotazioni_team` NON vengono MAI toccati:
  sono di proprietà dell'interfaccia (modifiche del team).
- descrizione/data/pagine/note vengono aggiornati solo se il valore Excel
  in arrivo è non vuoto, così i documenti caricati via upload (senza riga
  Excel) non vengono azzerati.
"""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import settings


def carica_metadati_excel() -> dict[str, dict]:
    """Legge l'Excel e ritorna {ID documento: metadati}."""
    if not settings.excel_path.exists():
        raise FileNotFoundError(f"File Excel non trovato: {settings.excel_path}")

    import openpyxl

    wb = openpyxl.load_workbook(settings.excel_path, read_only=True, data_only=True)
    try:
        ws = wb["Database"]
        metadati: dict[str, dict] = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            doc_id = row[0]
            if not doc_id or not isinstance(doc_id, str):
                continue
            data_raw = row[2]
            if isinstance(data_raw, datetime):
                data_str = data_raw.strftime("%d/%m/%Y")
            else:
                data_str = str(data_raw) if data_raw else ""
            try:
                pagine = int(row[1]) if row[1] else 0
            except (TypeError, ValueError):
                pagine = 0
            try:
                scrittura = int(row[3]) if row[3] else 0
            except (TypeError, ValueError):
                scrittura = 0
            metadati[doc_id.strip()] = {
                "pagine": pagine,
                "data": data_str,
                "scrittura": scrittura,
                "note": str(row[4]).strip() if row[4] else "",
                "descrizione": str(row[5]).strip() if row[5] else "",
            }
        return metadati
    finally:
        wb.close()


def resync_metadata(db: Session) -> dict:
    """Aggiorna i metadati delle righe esistenti dai dati Excel.

    Non crea righe nuove (l'ingest di nuovi documenti passa dall'upload o
    dallo script batch init_db.py) e non tocca mai i campi del team.
    Gli ID Excel senza riga DB corrispondente vengono riportati nella risposta
    invece di essere ignorati in silenzio (è così che è stato scoperto il
    refuso storico D07/B07 che lasciava il faldone B07 senza metadati).
    """
    metadati = carica_metadati_excel()
    aggiornati = 0
    non_corrisposti: list[str] = []
    for doc_id, meta in metadati.items():
        result = db.execute(
            text(
                """
                UPDATE documenti SET
                    descrizione = COALESCE(NULLIF(:descrizione, ''), descrizione),
                    data_documento = COALESCE(NULLIF(:data, ''), data_documento),
                    num_pagine = CASE WHEN :pagine > 0 THEN :pagine ELSE num_pagine END,
                    scrittura = :scrittura,
                    note = COALESCE(NULLIF(:note, ''), note)
                WHERE nome_file = :nome_file AND is_deleted = 0
                """
            ),
            {**meta, "nome_file": doc_id},
        )
        if result.rowcount:
            aggiornati += result.rowcount
        else:
            non_corrisposti.append(doc_id)
    db.commit()
    return {
        "righe_excel": len(metadati),
        "documenti_aggiornati": aggiornati,
        "id_non_corrisposti": non_corrisposti,
    }
