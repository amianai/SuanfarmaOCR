"""Test dell'OCR locale Tesseract (motore reale, non mockato).

Si salta automaticamente se il binario tesseract non è installato, così la
suite resta verde anche in ambienti che non lo hanno.
"""

import fitz
import pytesseract
import pytest

from app.services import ocr

tesseract_mancante = False
try:
    pytesseract.get_tesseract_version()
except Exception:
    tesseract_mancante = True

pytestmark = pytest.mark.skipif(
    tesseract_mancante, reason="binario tesseract non installato"
)


def _pdf_con_testo(testo: str) -> bytes:
    """PDF di una pagina con del testo grande e nitido, adatto all'OCR."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 200), testo, fontsize=48)
    data = doc.tobytes()
    doc.close()
    return data


def test_ocr_legge_testo_semplice(tmp_path):
    pdf_path = tmp_path / "prova.pdf"
    pdf_path.write_bytes(_pdf_con_testo("VERBALE ACCORDO"))
    risultato = ocr.ocr_pdf_file(pdf_path).upper()
    # Tesseract può introdurre spazi/refusi: verifichiamo le parole chiave.
    assert "VERBALE" in risultato
    assert "ACCORDO" in risultato


def test_ocr_pdf_multipagina(tmp_path):
    doc = fitz.open()
    doc.new_page().insert_text((72, 200), "PRIMA", fontsize=48)
    doc.new_page().insert_text((72, 200), "SECONDA", fontsize=48)
    pdf_path = tmp_path / "multi.pdf"
    pdf_path.write_bytes(doc.tobytes())
    doc.close()
    risultato = ocr.ocr_pdf_file(pdf_path).upper()
    assert "PRIMA" in risultato and "SECONDA" in risultato
