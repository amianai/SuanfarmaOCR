"""Test identità leggera: login con nome, preferiti per-utente, commenti, utenti, audit."""

import shutil

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.services import ocr

client = TestClient(app)

UTENTI_TEST = ["ZzTestA", "ZzTestB"]
CARTELLA_TEST = "ZZTEST"


def _login(password: str, nome: str = "Admin") -> dict:
    r = client.post("/auth/login", json={"password": password, "nome": nome})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin_headers() -> dict:
    return _login(settings.admin_password)


@pytest.fixture(autouse=True)
def _cleanup():
    """Rimuove utenti, preferiti, commenti e documenti di test dopo ogni test."""
    yield
    with SessionLocal() as db:
        db.execute(
            text("DELETE FROM preferiti_utente WHERE utente_nome IN ('ZzTestA', 'ZzTestB')")
        )
        db.execute(text("DELETE FROM commenti WHERE autore IN ('ZzTestA', 'ZzTestB', 'Admin')"))
        db.execute(text("DELETE FROM utenti WHERE nome IN ('ZzTestA', 'ZzTestB')"))
        db.execute(
            text(
                "DELETE FROM eventi_audit WHERE documento_id IN "
                "(SELECT id FROM documenti WHERE cartella = :c)"
            ),
            {"c": CARTELLA_TEST},
        )
        db.execute(text("DELETE FROM documenti WHERE cartella = :c"), {"c": CARTELLA_TEST})
        db.commit()
    shutil.rmtree(settings.documenti_pdf_dir / CARTELLA_TEST, ignore_errors=True)
    shutil.rmtree(settings.testo_estratto_dir / CARTELLA_TEST, ignore_errors=True)


@pytest.fixture()
def due_utenti(admin_headers) -> tuple[dict, dict]:
    """Crea due utenti di test e ritorna i loro header viewer."""
    for nome in UTENTI_TEST:
        r = client.post("/admin/utenti", json={"nome": nome}, headers=admin_headers)
        assert r.status_code == 201, r.text
    return (
        _login(settings.viewer_password, "ZzTestA"),
        _login(settings.viewer_password, "ZzTestB"),
    )


def test_login_nome_sconosciuto():
    r = client.post(
        "/auth/login", json={"password": settings.viewer_password, "nome": "Inventato"}
    )
    assert r.status_code == 422


def test_lista_nomi_pubblica():
    r = client.get("/auth/utenti")
    assert r.status_code == 200
    assert "Admin" in r.json()


def test_utenti_crud_solo_admin(admin_headers):
    viewer = _login(settings.viewer_password)
    assert client.post("/admin/utenti", json={"nome": "X"}, headers=viewer).status_code == 403

    # crea
    r = client.post("/admin/utenti", json={"nome": "ZzTestA"}, headers=admin_headers)
    assert r.status_code == 201
    uid = r.json()["id"]
    # duplicato
    assert (
        client.post("/admin/utenti", json={"nome": "ZzTestA"}, headers=admin_headers).status_code
        == 409
    )
    # il nome appare nella lista pubblica e permette il login
    assert "ZzTestA" in client.get("/auth/utenti").json()
    _login(settings.viewer_password, "ZzTestA")
    # disattiva -> sparisce dalla lista e il login viene rifiutato
    r = client.patch(f"/admin/utenti/{uid}", json={"attivo": False}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["attivo"] == 0
    assert "ZzTestA" not in client.get("/auth/utenti").json()
    assert (
        client.post(
            "/auth/login", json={"password": settings.viewer_password, "nome": "ZzTestA"}
        ).status_code
        == 422
    )


def test_preferiti_isolati_tra_utenti(due_utenti):
    headers_a, headers_b = due_utenti
    doc_id = client.get("/documents", headers=headers_a).json()["items"][0]["id"]

    r = client.put(
        f"/documents/{doc_id}/preferito", json={"preferito": True}, headers=headers_a
    )
    assert r.status_code == 200

    # A lo vede nei preferiti, B no
    ids_a = [
        i["id"]
        for i in client.get(
            "/documents", params={"solo_preferiti": True}, headers=headers_a
        ).json()["items"]
    ]
    ids_b = [
        i["id"]
        for i in client.get(
            "/documents", params={"solo_preferiti": True}, headers=headers_b
        ).json()["items"]
    ]
    assert doc_id in ids_a and doc_id not in ids_b

    # Anche il dettaglio riflette l'utente
    assert client.get(f"/documents/{doc_id}", headers=headers_a).json()["is_preferito"] == 1
    assert client.get(f"/documents/{doc_id}", headers=headers_b).json()["is_preferito"] == 0

    # Rimozione
    client.put(f"/documents/{doc_id}/preferito", json={"preferito": False}, headers=headers_a)
    assert client.get(f"/documents/{doc_id}", headers=headers_a).json()["is_preferito"] == 0


def test_commenti_permessi(due_utenti, admin_headers):
    headers_a, headers_b = due_utenti
    doc_id = client.get("/documents", headers=headers_a).json()["items"][0]["id"]

    r = client.post(
        f"/documents/{doc_id}/commenti", json={"testo": "commento di A"}, headers=headers_a
    )
    assert r.status_code == 201
    cid = r.json()["id"]
    assert r.json()["autore"] == "ZzTestA"

    # Visibile a tutti
    commenti = client.get(f"/documents/{doc_id}/commenti", headers=headers_b).json()
    assert any(c["id"] == cid for c in commenti)

    # B non può eliminare il commento di A
    assert (
        client.delete(f"/documents/{doc_id}/commenti/{cid}", headers=headers_b).status_code
        == 403
    )
    # A sì
    assert (
        client.delete(f"/documents/{doc_id}/commenti/{cid}", headers=headers_a).status_code
        == 204
    )

    # L'admin può eliminare il commento di chiunque
    r = client.post(
        f"/documents/{doc_id}/commenti", json={"testo": "altro di B"}, headers=headers_b
    )
    assert (
        client.delete(
            f"/documents/{doc_id}/commenti/{r.json()['id']}", headers=admin_headers
        ).status_code
        == 204
    )


def test_modifica_admin_non_crea_preferito_fantasma(admin_headers, monkeypatch):
    """Regressione: il PATCH admin non deve esporre il flag legacy condiviso.

    Bug originale: modificando un documento con is_preferito legacy = 1
    (i 4 preferiti storici pre-migrazione), la risposta accendeva la stella
    anche se l'utente non lo aveva mai messo nei preferiti.
    """
    monkeypatch.setattr(ocr, "ocr_pdf_file", lambda _p: "testo")
    pdf = fitz.open()
    pdf.new_page()
    pdf_bytes = pdf.tobytes()
    pdf.close()
    doc_id = client.post(
        "/admin/documents",
        files={"file": ("t.pdf", pdf_bytes, "application/pdf")},
        data={"cartella": CARTELLA_TEST},
        headers=admin_headers,
    ).json()["documento"]["id"]

    # Simula il flag legacy condiviso attivo (com'era per i 4 storici)
    with SessionLocal() as db:
        db.execute(
            text("UPDATE documenti SET is_preferito = 1 WHERE id = :i"), {"i": doc_id}
        )
        db.commit()

    r = client.patch(
        f"/admin/documents/{doc_id}", json={"note": "modifica"}, headers=admin_headers
    )
    assert r.status_code == 200
    assert r.json()["is_preferito"] == 0  # Admin non l'ha mai preferito


def test_elimina_utente(admin_headers):
    uid = client.post("/admin/utenti", json={"nome": "ZzTestA"}, headers=admin_headers).json()["id"]
    headers_a = _login(settings.viewer_password, "ZzTestA")

    # ZzTestA mette un preferito, poi il profilo viene eliminato
    doc_id = client.get("/documents", headers=headers_a).json()["items"][0]["id"]
    client.put(f"/documents/{doc_id}/preferito", json={"preferito": True}, headers=headers_a)

    assert client.delete(f"/admin/utenti/{uid}", headers=admin_headers).status_code == 204
    # sparito dalla lista pubblica e i suoi preferiti sono stati puliti
    assert "ZzTestA" not in client.get("/auth/utenti").json()
    with SessionLocal() as db:
        rimasti = db.execute(
            text("SELECT COUNT(*) FROM preferiti_utente WHERE utente_nome='ZzTestA'")
        ).scalar()
    assert rimasti == 0


def test_guardia_ultimo_utente_attivo(admin_headers):
    """Non si può eliminare/disattivare l'ultimo utente attivo (lockout totale)."""
    utenti = client.get("/admin/utenti", headers=admin_headers).json()
    attivi = [u for u in utenti if u["attivo"] == 1]
    if len(attivi) > 1:
        # disattiva temporaneamente tutti gli altri per arrivare al caso limite
        for u in attivi[1:]:
            client.patch(f"/admin/utenti/{u['id']}", json={"attivo": False}, headers=admin_headers)
    ultimo = attivi[0]
    try:
        assert (
            client.delete(f"/admin/utenti/{ultimo['id']}", headers=admin_headers).status_code
            == 409
        )
        assert (
            client.patch(
                f"/admin/utenti/{ultimo['id']}", json={"attivo": False}, headers=admin_headers
            ).status_code
            == 409
        )
    finally:
        # riattiva gli altri
        for u in attivi[1:]:
            client.patch(f"/admin/utenti/{u['id']}", json={"attivo": True}, headers=admin_headers)


def test_audit_su_operazioni_admin(admin_headers, monkeypatch):
    monkeypatch.setattr(ocr, "ocr_pdf_file", lambda _p: "testo di prova")
    pdf = fitz.open()
    pdf.new_page().insert_text((72, 72), "x")
    pdf_bytes = pdf.tobytes()
    pdf.close()

    doc_id = client.post(
        "/admin/documents",
        files={"file": ("t.pdf", pdf_bytes, "application/pdf")},
        data={"cartella": CARTELLA_TEST},
        headers=admin_headers,
    ).json()["documento"]["id"]

    client.patch(
        f"/admin/documents/{doc_id}", json={"validita": "no"}, headers=admin_headers
    )
    client.delete(f"/admin/documents/{doc_id}", headers=admin_headers)
    client.post(f"/admin/documents/{doc_id}/restore", headers=admin_headers)

    eventi = client.get(
        "/admin/audit", params={"documento_id": doc_id}, headers=admin_headers
    ).json()
    azioni = [e["azione"] for e in eventi]
    assert set(azioni) == {"upload", "validita", "delete", "restore"}
    assert all(e["autore"] == "Admin" for e in eventi)
    validita_ev = next(e for e in eventi if e["azione"] == "validita")
    assert validita_ev["dettaglio"] == "si→no"
