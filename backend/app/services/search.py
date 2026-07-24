"""Ricerca documenti: filtri + ricerca ibrida (full-text FTS5 + semantica).

- filtro soft-delete (is_deleted = 0)
- preferiti PER-UTENTE: `is_preferito` via LEFT JOIN su `preferiti_utente`
  (il campo legacy condiviso `documenti.is_preferito` non è più usato)
- quando c'è un testo di ricerca, i risultati per parola (FTS5) e quelli per
  significato (embedding, services/embeddings.py) vengono fusi con la Reciprocal
  Rank Fusion. Così `valido` trova anche `validità`/`validazione`, mantenendo la
  precisione dei match esatti. Senza testo, si comporta come una sfoglia filtrata.

Se l'indice semantico è vuoto (prima del reindex), la ricerca degrada in modo
pulito alla sola FTS5.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import settings
from . import embeddings

# Valori ammessi per il filtro validità.
VALIDITA_TUTTI = "tutti"
VALIDITA_VALIDI = "validi"
VALIDITA_NON_VALIDI = "non_validi"

# Colonne della lista: niente contenuto_md (pesante) e is_preferito calcolato.
_LIST_COLS = (
    "d.id, d.nome_file, d.cartella, d.descrizione, d.data_documento, "
    "d.num_pagine, d.validita, d.anteprima, "
    "CASE WHEN p.id IS NOT NULL THEN 1 ELSE 0 END AS is_preferito"
)
_FAV_JOIN = (
    "LEFT JOIN preferiti_utente p "
    "ON p.documento_id = d.id AND p.utente_nome = :utente"
)


def _build_fts_query(q: str) -> str:
    """Costruisce la query FTS5 con prefix-match, neutralizzando le virgolette."""
    termini = [t.replace('"', "") for t in q.strip().split()]
    return " ".join(f'"{t}"*' for t in termini if t)


def _filter_conditions(
    utente: str,
    solo_preferiti: bool,
    validita: str,
    anno_da: int | None,
    anno_a: int | None,
    cartelle: list[str] | None,
) -> tuple[list[str], dict]:
    """Condizioni WHERE comuni (non testuali), condivise dai vari rami di query."""
    conds = ["d.is_deleted = 0"]
    params: dict = {"utente": utente}
    if solo_preferiti:
        conds.append("p.id IS NOT NULL")
    if validita == VALIDITA_VALIDI:
        conds.append("d.validita = 'si'")
    elif validita == VALIDITA_NON_VALIDI:
        conds.append("d.validita = 'no'")
    if anno_da is not None:
        conds.append(
            "d.data_documento != '' AND CAST(SUBSTR(d.data_documento, 7, 4) AS INTEGER) >= :anno_da"
        )
        params["anno_da"] = anno_da
    if anno_a is not None:
        conds.append(
            "d.data_documento != '' AND CAST(SUBSTR(d.data_documento, 7, 4) AS INTEGER) <= :anno_a"
        )
        params["anno_a"] = anno_a
    if cartelle:
        segnaposto = ", ".join(f":cart{i}" for i in range(len(cartelle)))
        conds.append(f"d.cartella IN ({segnaposto})")
        params.update({f"cart{i}": c for i, c in enumerate(cartelle)})
    return conds, params


def _rrf(ranked_lists: list[list[int]], k: int) -> list[int]:
    """Reciprocal Rank Fusion: fonde più classifiche in un unico ordinamento."""
    punteggi: dict[int, float] = {}
    for lista in ranked_lists:
        for posizione, doc_id in enumerate(lista):
            punteggi[doc_id] = punteggi.get(doc_id, 0.0) + 1.0 / (k + posizione + 1)
    return [doc_id for doc_id, _ in sorted(punteggi.items(), key=lambda x: x[1], reverse=True)]


def _browse(db, conds, params, limit, offset) -> tuple[int, list[dict]]:
    """Nessun testo: sfoglia con i soli filtri, ordine per faldone/nome."""
    where = " AND ".join(conds)
    base = f"FROM documenti d {_FAV_JOIN} WHERE {where}"
    total = db.execute(text(f"SELECT COUNT(*) {base}"), params).scalar() or 0
    rows = (
        db.execute(
            text(f"SELECT {_LIST_COLS}, '' AS snippet {base} ORDER BY d.cartella, d.nome_file "
                 "LIMIT :limit OFFSET :offset"),
            {**params, "limit": limit, "offset": offset},
        )
        .mappings()
        .all()
    )
    return total, [dict(r) for r in rows]


def search_documents(
    db: Session,
    utente: str,
    q: str = "",
    cartelle: list[str] | None = None,
    solo_preferiti: bool = False,
    validita: str = VALIDITA_TUTTI,
    anno_da: int | None = None,
    anno_a: int | None = None,
    limit: int = 500,
    offset: int = 0,
) -> tuple[int, list[dict]]:
    conds, params = _filter_conditions(
        utente, solo_preferiti, validita, anno_da, anno_a, cartelle
    )

    if not (q and q.strip()):
        return _browse(db, conds, params, limit, offset)

    # --- Ramo di ricerca ibrida ---
    where = " AND ".join(conds)

    # 1) Ranking per parola (FTS5) + snippet evidenziato
    keyword_ids: list[int] = []
    snippet_map: dict[int, str] = {}
    fts = _build_fts_query(q)
    if fts:
        krows = db.execute(
            text(
                f"SELECT d.id AS id, "
                f"snippet(documenti_fts, 1, '<mark>', '</mark>', '…', 40) AS snippet "
                f"FROM documenti_fts JOIN documenti d ON d.id = documenti_fts.rowid "
                f"{_FAV_JOIN} WHERE {where} AND documenti_fts MATCH :fts ORDER BY rank"
            ),
            {**params, "fts": fts},
        ).all()
        for r in krows:
            keyword_ids.append(r.id)
            snippet_map[r.id] = r.snippet

    # 2) Ranking per significato (embedding), ristretto ai documenti che passano i filtri
    candidate_ids = {
        r.id
        for r in db.execute(
            text(f"SELECT d.id AS id FROM documenti d {_FAV_JOIN} WHERE {where}"), params
        ).all()
    }
    sem = embeddings.semantic_scores(db, q)  # {doc_id: (score, chunk_id)}
    semantic_ids = [
        doc_id
        for doc_id, (score, _cid) in sorted(sem.items(), key=lambda x: x[1][0], reverse=True)
        if doc_id in candidate_ids and score >= settings.semantic_min_score
    ][: settings.semantic_top_n]

    # 3) Fusione
    fused = _rrf([keyword_ids, semantic_ids], settings.rrf_k)
    total = len(fused)
    page_ids = fused[offset : offset + limit]
    if not page_ids:
        return total, []

    # 4) Recupero righe della pagina, preservando l'ordine fuso
    ph = ", ".join(f":id{i}" for i in range(len(page_ids)))
    id_params = {f"id{i}": v for i, v in enumerate(page_ids)}
    rows = db.execute(
        text(f"SELECT {_LIST_COLS} FROM documenti d {_FAV_JOIN} WHERE d.id IN ({ph})"),
        {"utente": utente, **id_params},
    ).mappings().all()
    per_id = {r["id"]: dict(r) for r in rows}

    # Passaggio rilevante per i risultati SOLO-semantici mostrati (batch per chunk_id)
    keyword_set = set(keyword_ids)
    chunk_da_mostrare = {
        sem[doc_id][1]: doc_id
        for doc_id in page_ids
        if doc_id not in keyword_set and doc_id in sem
    }
    testo_chunk: dict[int, str] = {}
    if chunk_da_mostrare:
        cph = ", ".join(f":c{i}" for i in range(len(chunk_da_mostrare)))
        cparams = {f"c{i}": cid for i, cid in enumerate(chunk_da_mostrare)}
        for r in db.execute(
            text(f"SELECT id, testo FROM chunks WHERE id IN ({cph})"), cparams
        ).all():
            doc_id = chunk_da_mostrare[r.id]
            estratto = " ".join(r.testo.split())[:220]
            testo_chunk[doc_id] = estratto + ("…" if len(r.testo) > 220 else "")

    risultati = []
    for doc_id in page_ids:
        r = per_id.get(doc_id)
        if r is None:
            continue
        if doc_id in keyword_set:
            r["match_semantico"] = False
            r["snippet"] = snippet_map.get(doc_id, "")
        else:
            r["match_semantico"] = True
            r["snippet"] = testo_chunk.get(doc_id, "")  # passaggio del chunk migliore
        risultati.append(r)
    return total, risultati
