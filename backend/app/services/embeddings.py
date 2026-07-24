"""Ricerca semantica: embedding locale dei documenti + punteggi di similarità.

Il modello (fastembed/ONNX) gira su CPU, senza API esterne. Ogni documento è
spezzato in chunk; per ciascuno salviamo il vettore normalizzato come BLOB in
SQLite. La similarità è il prodotto scalare (coseno, dato che i vettori sono
normalizzati), calcolato in memoria con numpy — nessun database vettoriale.
"""

from __future__ import annotations

import re

import numpy as np
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.chunk import Chunk
from ..models.documento import Documento

_model = None  # caricato pigramente al primo uso (evita il costo all'avvio)


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=settings.embedding_model)
    return _model


def _is_e5() -> bool:
    """I modelli E5 richiedono i prefissi 'query:'/'passage:'."""
    return "e5" in settings.embedding_model.lower()


def chunk_text(testo: str) -> list[str]:
    """Divide il testo in spezzoni con sovrapposizione, spezzando su spazi."""
    testo = (testo or "").strip()
    if not testo:
        return []
    size = settings.embedding_chunk_size
    overlap = settings.embedding_chunk_overlap
    chunks: list[str] = []
    start, n = 0, len(testo)
    while start < n:
        end = min(start + size, n)
        if end < n:  # prova a chiudere su uno spazio per non tagliare a metà parola
            sp = testo.rfind(" ", start + size - overlap, end)
            if sp > start:
                end = sp
        frammento = testo[start:end].strip()
        if frammento:
            chunks.append(frammento)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def _embed(testi: list[str], prefix: str) -> np.ndarray:
    if not testi:
        return np.zeros((0, 0), dtype=np.float32)
    inputs = [f"{prefix}{t}" for t in testi] if _is_e5() else testi
    vecs = np.array(list(_get_model().embed(inputs)), dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.clip(norms, 1e-8, None)  # normalizza -> coseno = prodotto scalare


def embed_passages(testi: list[str]) -> np.ndarray:
    return _embed(testi, "passage: ")


def embed_query(query: str) -> np.ndarray:
    return _embed([query], "query: ")


def index_document(db: Session, doc: Documento) -> int:
    """(Ri)calcola i chunk+embedding di un singolo documento. Ritorna il n. di chunk."""
    db.execute(delete(Chunk).where(Chunk.documento_id == doc.id))
    testi = chunk_text(doc.contenuto_md or "")
    if not testi:
        db.commit()
        return 0
    vettori = embed_passages(testi)
    for i, (t, v) in enumerate(zip(testi, vettori)):
        db.add(
            Chunk(documento_id=doc.id, chunk_index=i, testo=t, embedding=v.tobytes())
        )
    db.commit()
    return len(testi)


def reindex_all(db: Session, solo_mancanti: bool = True) -> dict:
    """Indicizza i documenti attivi. Con solo_mancanti salta quelli già indicizzati."""
    docs = list(
        db.execute(select(Documento).where(Documento.is_deleted == 0)).scalars()
    )
    indicizzati = 0
    chunk_totali = 0
    for doc in docs:
        if solo_mancanti:
            esiste = db.scalar(
                select(Chunk.id).where(Chunk.documento_id == doc.id).limit(1)
            )
            if esiste is not None:
                continue
        n = index_document(db, doc)
        if n:
            indicizzati += 1
            chunk_totali += n
    return {"documenti_indicizzati": indicizzati, "chunk_creati": chunk_totali}


def retrieve_chunks(
    db: Session, query: str, k: int = 6, max_per_doc: int = 2
) -> list[dict]:
    """Top-k chunk più vicini alla domanda, per il RAG.

    Cap di `max_per_doc` chunk per documento per non far dominare un solo file.
    Ritorna [{doc_id, nome_file, descrizione, testo, score}] ordinati per score.
    """
    rows = db.execute(
        text(
            """
            SELECT c.id AS chunk_id, c.documento_id AS doc_id, c.embedding AS emb
            FROM chunks c JOIN documenti d ON d.id = c.documento_id
            WHERE d.is_deleted = 0
            """
        )
    ).all()
    if not rows:
        return []
    qvec = embed_query(query)[0]
    matrice = np.frombuffer(b"".join(r.emb for r in rows), dtype=np.float32).reshape(
        len(rows), -1
    )
    sims = matrice @ qvec
    sim_by_chunk = {rows[i].chunk_id: float(sims[i]) for i in range(len(rows))}
    doc_by_chunk = {r.chunk_id: r.doc_id for r in rows}
    n_chunks = len(rows)

    # Recupero IBRIDO: dà priorità ai brani che contengono le parole
    # DISCRIMINANTI della domanda (rare, quindi informative come "mensa"),
    # ignorando quelle comuni ("documenti", "cosa"). Risolve il caso in cui la
    # sola semantica, diluita dalle parole di riempimento, manca i documenti giusti.
    termini = {t for t in re.findall(r"[a-zàèéìòù]{4,}", query.lower())}
    kw_ids: set[int] = set()
    soglia = max(5, int(n_chunks * 0.15))
    for t in termini:
        cnt = db.execute(
            text("SELECT COUNT(*) FROM chunks WHERE lower(testo) LIKE :p"),
            {"p": f"%{t}%"},
        ).scalar() or 0
        if 0 < cnt <= soglia:  # parola poco frequente -> discriminante
            for r in db.execute(
                text(
                    "SELECT c.id FROM chunks c JOIN documenti d ON d.id = c.documento_id "
                    "WHERE d.is_deleted = 0 AND lower(c.testo) LIKE :p"
                ),
                {"p": f"%{t}%"},
            ).all():
                kw_ids.add(r.id)

    # Ordina: prima i brani con parola discriminante (per similarità), poi il resto semantico.
    ordinati = sorted(
        sim_by_chunk.keys(),
        key=lambda cid: (cid in kw_ids, sim_by_chunk[cid]),
        reverse=True,
    )
    scelti: list[tuple[int, float]] = []
    per_doc: dict[int, int] = {}
    for cid in ordinati:
        d = doc_by_chunk[cid]
        if per_doc.get(d, 0) >= max_per_doc:
            continue
        scelti.append((cid, sim_by_chunk[cid]))
        per_doc[d] = per_doc.get(d, 0) + 1
        if len(scelti) >= k:
            break
    if not scelti:
        return []

    # Recupero testo + metadati dei chunk scelti
    ids = [cid for cid, _ in scelti]
    ph = ", ".join(f":c{i}" for i in range(len(ids)))
    meta = {
        r.id: r
        for r in db.execute(
            text(
                f"""
                SELECT c.id AS id, c.testo AS testo, d.nome_file AS nome_file,
                       d.descrizione AS descrizione, d.id AS doc_id
                FROM chunks c JOIN documenti d ON d.id = c.documento_id
                WHERE c.id IN ({ph})
                """
            ),
            {f"c{i}": cid for i, cid in enumerate(ids)},
        ).all()
    }
    risultati = []
    for cid, score in scelti:
        m = meta.get(cid)
        if m:
            risultati.append(
                {
                    "doc_id": m.doc_id,
                    "nome_file": m.nome_file,
                    "descrizione": m.descrizione,
                    "testo": m.testo,
                    "score": score,
                }
            )
    return risultati


def semantic_scores(db: Session, query: str) -> dict[int, tuple[float, int]]:
    """Per ogni documento attivo: (punteggio del chunk migliore, id di quel chunk).

    L'id del chunk serve a mostrare il passaggio rilevante nei match semantici.
    """
    rows = db.execute(
        text(
            """
            SELECT c.id AS chunk_id, c.documento_id AS doc_id, c.embedding AS emb
            FROM chunks c JOIN documenti d ON d.id = c.documento_id
            WHERE d.is_deleted = 0
            """
        )
    ).all()
    if not rows:
        return {}
    qvec = embed_query(query)[0]
    matrice = np.frombuffer(b"".join(r.emb for r in rows), dtype=np.float32).reshape(
        len(rows), -1
    )
    sims = matrice @ qvec
    best: dict[int, tuple[float, int]] = {}
    for r, s in zip(rows, sims):
        val = float(s)
        if val > best.get(r.doc_id, (-1.0, 0))[0]:
            best[r.doc_id] = (val, r.chunk_id)
    return best
