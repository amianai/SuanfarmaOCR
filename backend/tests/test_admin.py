"""Test API Fase 3: CRUD admin (upload, modifica, soft-delete, resync Excel)."""

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

CARTELLA_TEST = "ZZTEST"


def _login(password: str, nome: str = "Admin") -> dict:
    r = client.post("/auth/login", json={"password": password, "nome": nome})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def viewer_headers() -> dict:
    return _login(settings.viewer_password)


@pytest.fixture()
def admin_headers() -> dict:
    return _login(settings.admin_password)


@pytest.fixture()
def pdf_bytes() -> bytes:
    """PDF minimale generato in memoria (1 pagina con testo)."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Documento di test")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(autouse=True)
def _cleanup_test_folder():
    """Rimuove righe, file ed eventi audit del faldone di test dopo ogni test."""
    yield
    with SessionLocal() as db:
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


def test_admin_endpoints_richiedono_admin(viewer_headers):
    r = client.patch("/admin/documents/1", json={"note": "x"}, headers=viewer_headers)
    assert r.status_code == 403
    r = client.delete("/admin/documents/1", headers=viewer_headers)
    assert r.status_code == 403
    r = client.post("/admin/resync-excel", headers=viewer_headers)
    assert r.status_code == 403


def test_upload_ciclo_completo(admin_headers, pdf_bytes, monkeypatch):
    # OCR mockato: nessuna chiamata reale alle API Mistral.
    monkeypatch.setattr(ocr, "ocr_pdf_file", lambda _p: "testo OCR simulato per il test")

    r = client.post(
        "/admin/documents",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={
            "cartella": CARTELLA_TEST,
            "descrizione": "Documento di prova",
            "data_documento": "15/03/1985",
            "validita": "si",
            "note": "nota di prova",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ocr_ok"] is True
    doc = body["documento"]
    assert doc["nome_file"] == f"{CARTELLA_TEST}-D001"
    assert doc["num_pagine"] == 1
    assert doc["contenuto_md"] == "testo OCR simulato per il test"

    # I file sono stati scritti su disco
    assert (settings.documenti_pdf_dir / CARTELLA_TEST / f"{doc['nome_file']}.pdf").exists()
    assert (settings.testo_estratto_dir / CARTELLA_TEST / f"{doc['nome_file']}.md").exists()

    # Il secondo upload nello stesso faldone prende l'ID successivo
    r2 = client.post(
        "/admin/documents",
        files={"file": ("test2.pdf", pdf_bytes, "application/pdf")},
        data={"cartella": CARTELLA_TEST},
        headers=admin_headers,
    )
    assert r2.json()["documento"]["nome_file"] == f"{CARTELLA_TEST}-D002"

    # FTS5: il nuovo documento è ricercabile subito (trigger)
    r3 = client.get("/documents", params={"q": "simulato"}, headers=admin_headers)
    assert any(i["cartella"] == CARTELLA_TEST for i in r3.json()["items"])

    # Modifica metadati
    doc_id = doc["id"]
    r4 = client.patch(
        f"/admin/documents/{doc_id}",
        json={"descrizione": "Descrizione aggiornata", "validita": "no"},
        headers=admin_headers,
    )
    assert r4.status_code == 200
    assert r4.json()["descrizione"] == "Descrizione aggiornata"
    assert r4.json()["validita"] == "no"

    # Soft-delete: sparisce dalla lettura, i file restano
    r5 = client.delete(f"/admin/documents/{doc_id}", headers=admin_headers)
    assert r5.status_code == 200
    assert client.get(f"/documents/{doc_id}", headers=admin_headers).status_code == 404
    assert (settings.documenti_pdf_dir / CARTELLA_TEST / f"{doc['nome_file']}.pdf").exists()

    # Compare nel cestino e si può ripristinare
    cestino = client.get("/admin/documents/deleted", headers=admin_headers).json()
    assert any(d["id"] == doc_id for d in cestino)
    r6 = client.post(f"/admin/documents/{doc_id}/restore", headers=admin_headers)
    assert r6.status_code == 200
    assert client.get(f"/documents/{doc_id}", headers=admin_headers).status_code == 200


def test_upload_cartella_invalida(admin_headers, pdf_bytes):
    r = client.post(
        "/admin/documents",
        files={"file": ("x.pdf", pdf_bytes, "application/pdf")},
        data={"cartella": "../../etc"},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_upload_file_corrotto(admin_headers):
    r = client.post(
        "/admin/documents",
        files={"file": ("x.pdf", b"non sono un pdf", "application/pdf")},
        data={"cartella": CARTELLA_TEST},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_upload_ocr_fallito_salva_comunque(admin_headers, pdf_bytes, monkeypatch):
    def _boom(_p):
        raise RuntimeError("API non raggiungibile")

    monkeypatch.setattr(ocr, "ocr_pdf_file", _boom)
    r = client.post(
        "/admin/documents",
        files={"file": ("x.pdf", pdf_bytes, "application/pdf")},
        data={"cartella": CARTELLA_TEST},
        headers=admin_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["ocr_ok"] is False and "OCR non riuscito" in body["warning"]
    # Il PDF esiste comunque, il testo è vuoto
    assert (settings.documenti_pdf_dir / CARTELLA_TEST / "ZZTEST-D001.pdf").exists()
    assert body["documento"]["contenuto_md"] == ""


def test_resync_excel(admin_headers):
    r = client.post("/admin/resync-excel", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["righe_excel"] >= 250
    assert body["documenti_aggiornati"] >= 250
    # Dopo la correzione del refuso D07/B07 nell'Excel, ogni ID deve corrispondere
    assert body["id_non_corrisposti"] == []
