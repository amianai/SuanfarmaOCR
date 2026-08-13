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


from conftest import PASSWORD_TEST, UTENTE_ADMIN, login  # noqa: E402

# admin_headers arriva dalle fixture condivise in conftest.py


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
        db.execute(
            text(
                "DELETE FROM chunks WHERE documento_id IN "
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
    """Crea due utenti di test con password nota e ritorna i loro header."""
    for nome in UTENTI_TEST:
        r = client.post(
            "/admin/utenti",
            json={"nome": nome, "password": PASSWORD_TEST},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
    return (login("ZzTestA"), login("ZzTestB"))


def test_login_nome_sconosciuto():
    """401 generico: non si rivela se sia il nome o la password a non combaciare."""
    r = client.post(
        "/auth/login", json={"password": PASSWORD_TEST, "nome": "Inventato"}
    )
    assert r.status_code == 401


def test_lista_nomi_pubblica():
    r = client.get("/auth/utenti")
    assert r.status_code == 200
    assert "Admin" in r.json()


def test_utenti_crud_solo_admin(admin_headers, viewer_headers):
    nuovo = {"nome": "ZzTestA", "password": PASSWORD_TEST}
    assert client.post("/admin/utenti", json=nuovo, headers=viewer_headers).status_code == 403

    # crea: la risposta contiene l'utente e la password in chiaro (una sola volta)
    r = client.post("/admin/utenti", json=nuovo, headers=admin_headers)
    assert r.status_code == 201
    body = r.json()
    uid = body["utente"]["id"]
    assert body["password"] == PASSWORD_TEST
    assert body["utente"]["ha_password"] is True
    assert body["utente"]["amministratore"] == 0

    # duplicato
    assert client.post("/admin/utenti", json=nuovo, headers=admin_headers).status_code == 409

    # il nome appare nella lista pubblica e le credenziali funzionano
    assert "ZzTestA" in client.get("/auth/utenti").json()
    login("ZzTestA")

    # disattiva -> sparisce dalla lista e il login viene rifiutato
    r = client.patch(f"/admin/utenti/{uid}", json={"attivo": False}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["attivo"] == 0
    assert "ZzTestA" not in client.get("/auth/utenti").json()
    assert (
        client.post(
            "/auth/login", json={"password": PASSWORD_TEST, "nome": "ZzTestA"}
        ).status_code
        == 401
    )


def test_promozione_e_reset_password(admin_headers):
    """L'admin può promuovere un utente e reimpostargli la password."""
    r = client.post(
        "/admin/utenti",
        json={"nome": "ZzTestA", "password": PASSWORD_TEST},
        headers=admin_headers,
    )
    uid = r.json()["utente"]["id"]

    # promozione ad amministratore -> al login ottiene il ruolo admin
    r = client.patch(
        f"/admin/utenti/{uid}", json={"amministratore": True}, headers=admin_headers
    )
    assert r.status_code == 200 and r.json()["amministratore"] == 1
    tok = client.post("/auth/login", json={"nome": "ZzTestA", "password": PASSWORD_TEST})
    assert tok.json()["role"] == "admin"

    # reset password: la vecchia non vale più, la nuova sì
    nuova = "password-nuova-456"
    assert (
        client.patch(
            f"/admin/utenti/{uid}", json={"password": nuova}, headers=admin_headers
        ).status_code
        == 200
    )
    assert client.post(
        "/auth/login", json={"nome": "ZzTestA", "password": PASSWORD_TEST}
    ).status_code == 401
    assert client.post(
        "/auth/login", json={"nome": "ZzTestA", "password": nuova}
    ).status_code == 200


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
    uid = client.post(
        "/admin/utenti",
        json={"nome": "ZzTestA", "password": PASSWORD_TEST},
        headers=admin_headers,
    ).json()["utente"]["id"]
    headers_a = login("ZzTestA")

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


def test_account_admin_protetto(admin_headers):
    """L'account `Admin` è immutabile: è la garanzia di non restare chiusi fuori.

    Non può essere eliminato, disattivato, degradato a utente normale, né gli si
    può cambiare la password dall'interfaccia (solo `python -m app.reset_admin`).
    """
    utenti = client.get("/admin/utenti", headers=admin_headers).json()
    admin = next(u for u in utenti if u["nome"] == "Admin")
    assert admin["protetto"] is True and admin["amministratore"] == 1

    aid = admin["id"]
    assert client.delete(f"/admin/utenti/{aid}", headers=admin_headers).status_code == 403
    assert (
        client.patch(f"/admin/utenti/{aid}", json={"attivo": False}, headers=admin_headers).status_code
        == 403
    )
    assert (
        client.patch(
            f"/admin/utenti/{aid}", json={"amministratore": False}, headers=admin_headers
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/admin/utenti/{aid}", json={"password": "qualsiasi-cosa"}, headers=admin_headers
        ).status_code
        == 403
    )
    # ...e resta attivo e amministratore
    utenti = client.get("/admin/utenti", headers=admin_headers).json()
    admin = next(u for u in utenti if u["nome"] == "Admin")
    assert admin["attivo"] == 1 and admin["amministratore"] == 1


def test_cambio_password_proprio(admin_headers):
    """Ogni utente cambia la propria password; serve quella attuale."""
    client.post(
        "/admin/utenti",
        json={"nome": "ZzTestA", "password": PASSWORD_TEST},
        headers=admin_headers,
    )
    headers_a = login("ZzTestA")

    # password attuale sbagliata -> rifiutato
    assert (
        client.patch(
            "/auth/password",
            json={"password_attuale": "sbagliata", "password_nuova": "nuova-password-1"},
            headers=headers_a,
        ).status_code
        == 400
    )
    # con quella giusta -> cambiata, e vale solo la nuova
    assert (
        client.patch(
            "/auth/password",
            json={"password_attuale": PASSWORD_TEST, "password_nuova": "nuova-password-1"},
            headers=headers_a,
        ).status_code
        == 204
    )
    assert client.post(
        "/auth/login", json={"nome": "ZzTestA", "password": PASSWORD_TEST}
    ).status_code == 401
    assert client.post(
        "/auth/login", json={"nome": "ZzTestA", "password": "nuova-password-1"}
    ).status_code == 200


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
    assert all(e["autore"] == UTENTE_ADMIN for e in eventi)
    validita_ev = next(e for e in eventi if e["azione"] == "validita")
    assert validita_ev["dettaglio"] == "si→no"
