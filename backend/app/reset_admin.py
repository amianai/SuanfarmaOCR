"""Rigenera la password dell'utente Admin e la stampa a video.

Rete di sicurezza: la password di Admin non è modificabile dall'interfaccia
(l'account è volutamente immutabile), quindi se quella iniziale va perduta non
si potrebbe più entrare. Questo comando si lancia dal server:

    python -m app.reset_admin
"""

from .core import passwords
from .core.bootstrap import NOME_ADMIN, _stampa_credenziali
from .core.db import SessionLocal
from .models.collab import Utente


def main() -> None:
    with SessionLocal() as db:
        admin = db.query(Utente).filter(Utente.nome == NOME_ADMIN).first()
        if admin is None:
            admin = Utente(nome=NOME_ADMIN, attivo=1, amministratore=1, password_hash="")
            db.add(admin)
            print(f"Utente {NOME_ADMIN} non presente: viene creato.")
        password = passwords.genera_password()
        admin.password_hash = passwords.hash_password(password)
        admin.attivo = 1
        admin.amministratore = 1  # l'account admin resta sempre amministratore attivo
        db.commit()
    _stampa_credenziali(NOME_ADMIN, password)


if __name__ == "__main__":
    main()
