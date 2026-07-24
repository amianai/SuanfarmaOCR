"""Test Fase 4: ricerca semantica ibrida.

- test unitari veloci su chunking e fusione RRF (nessun modello);
- test d'accettazione con embedding reale (ricerca 'valido' -> 'validità'),
  saltato se l'indice semantico non è ancora stato costruito.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.services import embeddings, search

client = TestClient(app)


def _login(password: str, nome: str = "Admin") -> dict:
    r = client.post("/auth/login", json={"password": password, "nome": nome})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- Unit: chunking ---


def test_chunk_text_vuoto():
    assert embeddings.chunk_text("") == []
    assert embeddings.chunk_text("   ") == []


def test_chunk_text_overlap_e_copertura():
    testo = " ".join(f"parola{i}" for i in range(600))  # testo lungo
    chunks = embeddings.chunk_text(testo)
    assert len(chunks) >= 2
    # ogni chunk rispetta grossomodo la dimensione massima configurata
    assert all(len(c) <= settings.embedding_chunk_size + 50 for c in chunks)
    # la prima e l'ultima parola del testo compaiono nei chunk
    assert "parola0" in chunks[0]
    assert "parola599" in chunks[-1]


# --- Unit: fusione RRF ---


def test_rrf_fonde_e_premia_presenza_in_entrambe():
    keyword = [10, 20, 30]
    semantic = [30, 40, 10]
    fused = search._rrf([keyword, semantic], k=60)
    # 10 e 30 stanno in entrambe le liste in alto -> davanti a 20 e 40
    assert set(fused[:2]) == {10, 30}
    assert set(fused) == {10, 20, 30, 40}


def test_rrf_lista_vuota():
    assert search._rrf([[], []], k=60) == []
    assert search._rrf([[5, 6]], k=60) == [5, 6]


# --- Accettazione con modello reale ---

def _indice_pronto() -> bool:
    with SessionLocal() as db:
        return (db.execute(text("SELECT COUNT(*) FROM chunks")).scalar() or 0) > 0


indice_assente = not _indice_pronto()
motivo = "indice semantico non costruito (esegui il reindex prima)"


@pytest.mark.skipif(indice_assente, reason=motivo)
def test_ricerca_semantica_trova_varianti_morfologiche():
    """Cercando 'valido' devono comparire documenti che contengono solo
    'validità'/'validazione' — il cuore della Fase 4."""
    with SessionLocal() as db:
        target = db.execute(
            text(
                "SELECT id FROM documenti WHERE is_deleted=0 "
                "AND (lower(contenuto_md) LIKE '%validità%' OR lower(contenuto_md) LIKE '%validazione%') "
                "AND lower(contenuto_md) NOT LIKE '%valido%' LIMIT 1"
            )
        ).scalar()
        if target is None:
            pytest.skip("nessun documento adatto al test nel corpus")
        _, rows = search.search_documents(db, "Admin", q="valido", limit=200)
        assert target in {r["id"] for r in rows}


@pytest.mark.skipif(indice_assente, reason=motivo)
def test_ricerca_ibrida_via_api():
    headers = _login(settings.viewer_password)
    r = client.get("/documents", params={"q": "valido"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["total"] >= 1


@pytest.mark.skipif(indice_assente, reason=motivo)
def test_reindex_solo_mancanti_idempotente():
    """Un reindex 'solo mancanti' a indice completo non ricrea nulla."""
    with SessionLocal() as db:
        res = embeddings.reindex_all(db, solo_mancanti=True)
        assert res["documenti_indicizzati"] == 0


@pytest.mark.skipif(indice_assente, reason=motivo)
def test_semantic_scores_ritorna_chunk_id():
    with SessionLocal() as db:
        sem = embeddings.semantic_scores(db, "valido")
        assert sem
        score, chunk_id = next(iter(sem.values()))
        assert isinstance(score, float) and isinstance(chunk_id, int) and chunk_id > 0


@pytest.mark.skipif(indice_assente, reason=motivo)
def test_flag_match_semantico_e_passaggio():
    """I match per parola hanno match_semantico=False; i solo-semantici True + passaggio."""
    with SessionLocal() as db:
        _, rows = search.search_documents(db, "Admin", q="valido", limit=100)
        per_parola = [r for r in rows if not r["match_semantico"]]
        semantici = [r for r in rows if r["match_semantico"]]
        # cercando 'valido' ci sono match per parola (documenti che la contengono)
        assert per_parola
        # se ci sono risultati semantici, hanno un passaggio (snippet) non vuoto
        for r in semantici:
            assert r["snippet"]
