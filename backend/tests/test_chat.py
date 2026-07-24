"""Test Fase 5: chatbot RAG (LLM mockato — nessuna chiamata reale a Ollama)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.services import llm, rag

client = TestClient(app)


def _login(password: str, nome: str = "Admin") -> dict:
    r = client.post("/auth/login", json={"password": password, "nome": nome})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _indice_pronto() -> bool:
    with SessionLocal() as db:
        return (db.execute(text("SELECT COUNT(*) FROM chunks")).scalar() or 0) > 0


skip_no_index = pytest.mark.skipif(
    not _indice_pronto(), reason="indice semantico non costruito"
)


def test_chat_richiede_auth():
    assert client.post("/chat", json={"domanda": "test"}).status_code == 401


def test_chat_domanda_vuota_422():
    assert client.post("/chat", json={"domanda": ""}, headers=_login(settings.viewer_password)).status_code == 422


@skip_no_index
def test_retrieve_chunks_rispetta_cap_per_documento():
    from app.services import embeddings

    with SessionLocal() as db:
        chunks = embeddings.retrieve_chunks(db, "premio di produzione", k=6, max_per_doc=2)
        assert 1 <= len(chunks) <= 6
        conteggio: dict[int, int] = {}
        for c in chunks:
            conteggio[c["doc_id"]] = conteggio.get(c["doc_id"], 0) + 1
        assert all(v <= 2 for v in conteggio.values())
        assert all(c["testo"] and c["nome_file"] for c in chunks)


@skip_no_index
def test_prompt_contiene_contesto_e_regole(monkeypatch):
    """Il prompt inviato al modello deve contenere i brani recuperati e le regole di scope."""
    catturato = {}

    def fake_chat(messages, **kwargs):
        catturato["messages"] = messages
        return "Risposta di prova [B01-D001]."

    monkeypatch.setattr(llm, "chat", fake_chat)
    with SessionLocal() as db:
        res = rag.answer(db, "Cosa dicono i documenti sulla mensa?")

    sys_msg = catturato["messages"][0]["content"]
    user_msg = catturato["messages"][1]["content"]
    assert "SOLO le informazioni" in sys_msg and "parentesi quadre" in sys_msg
    assert "DOCUMENTI:" in user_msg and "DOMANDA:" in user_msg
    assert res["risposta"] == "Risposta di prova [B01-D001]."
    assert res["fonti"] and "nome_file" in res["fonti"][0]


@skip_no_index
def test_chat_api_con_llm_mockato(monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda messages, **kw: "Risposta simulata.")
    r = client.post(
        "/chat", json={"domanda": "Quali documenti parlano di sciopero?"},
        headers=_login(settings.viewer_password),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["risposta"] == "Risposta simulata."
    assert isinstance(body["fonti"], list) and body["fonti"]


def test_chat_llm_non_raggiungibile_503(monkeypatch):
    if not _indice_pronto():
        pytest.skip("indice non pronto")

    def boom(messages, **kwargs):
        raise llm.LLMError("connessione rifiutata")

    monkeypatch.setattr(llm, "chat", boom)
    r = client.post(
        "/chat", json={"domanda": "test"}, headers=_login(settings.viewer_password)
    )
    assert r.status_code == 503
