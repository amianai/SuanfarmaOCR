"""Test dell'hashing delle password."""

from app.core import passwords


def test_hash_formato_e_verifica():
    h = passwords.hash_password("segreto123")
    assert h.startswith("sha1$")
    assert len(h.split("$")) == 3
    assert passwords.verify_password("segreto123", h)
    assert not passwords.verify_password("altro", h)


def test_salt_diverso_a_parita_di_password():
    """Due utenti con la stessa password devono avere hash diversi (salt)."""
    a = passwords.hash_password("stessa-password")
    b = passwords.hash_password("stessa-password")
    assert a != b
    assert passwords.verify_password("stessa-password", a)
    assert passwords.verify_password("stessa-password", b)


def test_password_non_impostata_non_verifica():
    """Un utente senza password (hash vuoto) non può accedere."""
    assert not passwords.verify_password("qualsiasi", "")
    assert not passwords.verify_password("", passwords.hash_password("x"))


def test_hash_corrotto_non_verifica():
    assert not passwords.verify_password("x", "non-un-hash-valido")
    assert not passwords.verify_password("x", "md5$abc$def")  # algoritmo non previsto


def test_genera_password():
    p1, p2 = passwords.genera_password(), passwords.genera_password()
    assert len(p1) == 12 and p1 != p2
    # niente caratteri ambigui: evita errori quando la password si detta a voce
    assert not set(p1) & set("O0lI1")
