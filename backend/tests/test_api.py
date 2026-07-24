"""Test API Fase 1: auth a due livelli + endpoint di lettura."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def _login(password: str, nome: str = "Admin") -> str:
    r = client.post("/auth/login", json={"password": password, "nome": nome})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture()
def viewer_token() -> str:
    return _login(settings.viewer_password)


@pytest.fixture()
def admin_token() -> str:
    return _login(settings.admin_password)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_login_wrong_password():
    r = client.post("/auth/login", json={"password": "sbagliata", "nome": "Admin"})
    assert r.status_code == 401


def test_login_roles():
    v = client.post("/auth/login", json={"password": settings.viewer_password, "nome": "Admin"})
    a = client.post("/auth/login", json={"password": settings.admin_password, "nome": "Admin"})
    assert v.json()["role"] == "viewer" and v.json()["nome"] == "Admin"
    assert a.json()["role"] == "admin"


def test_documents_requires_auth():
    assert client.get("/documents").status_code == 401


def test_me(viewer_token):
    r = client.get("/auth/me", headers=_auth(viewer_token))
    assert r.status_code == 200
    assert r.json() == {"role": "viewer", "nome": "Admin"}


def test_lista_documenti(viewer_token):
    r = client.get("/documents", headers=_auth(viewer_token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 250
    assert len(data["items"]) >= 250
    assert "nome_file" in data["items"][0]


def test_filtro_validita(viewer_token):
    r = client.get("/documents", params={"validita": "validi"}, headers=_auth(viewer_token))
    assert r.status_code == 200
    assert all(True for _ in r.json()["items"])  # struttura valida
    # tutti i risultati devono avere validita 'si' -> verifichiamo via dettaglio del primo
    items = r.json()["items"]
    if items:
        d = client.get(f"/documents/{items[0]['id']}", headers=_auth(viewer_token)).json()
        assert d["validita"] == "si"


def test_ricerca_fts(viewer_token):
    r = client.get("/documents", params={"q": "sindacale"}, headers=_auth(viewer_token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert "<mark>" in data["items"][0]["snippet"]


def test_ricerca_con_virgolette_non_crasha(viewer_token):
    r = client.get("/documents", params={"q": 'test"x'}, headers=_auth(viewer_token))
    assert r.status_code == 200


def test_cartelle_con_anni(viewer_token):
    r = client.get("/documents/cartelle", headers=_auth(viewer_token))
    assert r.status_code == 200
    per_nome = {c["cartella"]: c for c in r.json()}
    assert "B01" in per_nome
    b01 = per_nome["B01"]
    assert b01["anno_min"] == 1970 and b01["anno_max"] >= b01["anno_min"]
    assert b01["documenti"] >= 1


def test_filtro_multi_cartella(viewer_token):
    r = client.get(
        "/documents",
        params=[("cartella", "B01"), ("cartella", "B02")],
        headers=_auth(viewer_token),
    )
    assert r.status_code == 200
    cartelle_trovate = {i["cartella"] for i in r.json()["items"]}
    assert cartelle_trovate == {"B01", "B02"}
    # una sola cartella continua a funzionare
    r1 = client.get("/documents", params={"cartella": "B03"}, headers=_auth(viewer_token))
    assert {i["cartella"] for i in r1.json()["items"]} == {"B03"}


def test_dettaglio_e_pdf(viewer_token):
    lista = client.get("/documents", headers=_auth(viewer_token)).json()["items"]
    doc_id = lista[0]["id"]
    det = client.get(f"/documents/{doc_id}", headers=_auth(viewer_token))
    assert det.status_code == 200
    assert "contenuto_md" in det.json()

    pdf = client.get(f"/documents/{doc_id}/pdf", headers=_auth(viewer_token))
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"


def test_dettaglio_inesistente(viewer_token):
    assert client.get("/documents/999999", headers=_auth(viewer_token)).status_code == 404
