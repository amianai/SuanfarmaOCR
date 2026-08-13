"""Test dello svuota cestino: eliminazione definitiva con rimozione dei file."""

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

CARTELLA_TEST = "ZZTRASH"


@pytest.fixture(autouse=True)
def _pulizia():
    yield
    with SessionLocal() as db:
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
def pdf_bytes() -> bytes:
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def test_svuota_cestino_elimina_righe_e_file(admin_headers, pdf_bytes, monkeypatch):
    monkeypatch.setattr(ocr, "ocr_pdf_file", lambda _p: "testo di prova")

    # carica un documento, poi mettilo nel cestino
    doc = client.post(
        "/admin/documents",
        files={"file": ("t.pdf", pdf_bytes, "application/pdf")},
        data={"cartella": CARTELLA_TEST},
        headers=admin_headers,
    ).json()["documento"]
    doc_id, nome = doc["id"], doc["nome_file"]
    pdf_path = settings.documenti_pdf_dir / CARTELLA_TEST / f"{nome}.pdf"
    md_path = settings.testo_estratto_dir / CARTELLA_TEST / f"{nome}.md"
    assert pdf_path.exists() and md_path.exists()

    client.delete(f"/admin/documents/{doc_id}", headers=admin_headers)
    assert any(
        d["id"] == doc_id
        for d in client.get("/admin/documents/deleted", headers=admin_headers).json()
    )

    r = client.post("/admin/trash/empty", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["documenti_eliminati"] >= 1
    assert body["file_eliminati"] >= 2  # PDF + testo estratto

    # i file sono rimossi dal disco e la riga dal database
    assert not pdf_path.exists() and not md_path.exists()
    assert client.get(f"/documents/{doc_id}", headers=admin_headers).status_code == 404
    assert client.get("/admin/documents/deleted", headers=admin_headers).json() == []


def test_svuota_cestino_richiede_admin(viewer_headers):
    assert client.post("/admin/trash/empty", headers=viewer_headers).status_code == 403


def test_svuota_cestino_vuoto_non_errore(admin_headers):
    r = client.post("/admin/trash/empty", headers=admin_headers)
    assert r.status_code == 200 and r.json()["documenti_eliminati"] == 0


def test_percorsi_fuori_da_data_dir_non_vengono_eliminati(tmp_path):
    """Guardia contro path traversal: un percorso fuori da DATA_DIR è ignorato."""
    from app.api.admin import _elimina_file_dati

    esterno = tmp_path / "non-toccare.txt"
    esterno.write_text("dati importanti")
    assert _elimina_file_dati(f"../../../../{esterno}") is False
    assert esterno.exists()  # il file è ancora lì
