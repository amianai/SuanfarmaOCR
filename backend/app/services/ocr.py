"""OCR locale via Tesseract (motore predefinito per i documenti caricati).

Scelta concordata col committente: Tesseract è maturo, gira su CPU, non fa
uscire i dati e non richiede API esterne. Le scansioni caricate d'ora in poi
sono recenti e di buona qualità, quindi non serve preprocessing spinto.

Flusso: ogni pagina del PDF viene renderizzata in immagine (PyMuPDF) a una
risoluzione adeguata all'OCR, poi passata a Tesseract. Il testo delle pagine
viene concatenato. Lingua e DPI sono configurabili da .env (settings.ocr_*).

Requisiti di sistema: binario `tesseract` + pacchetto lingua (es. `ita`).
- macOS:  brew install tesseract tesseract-lang
- Docker: apt-get install -y tesseract-ocr tesseract-ocr-ita
"""

import io
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from ..core.config import settings

# Percorso esplicito al binario, se non è nel PATH (utile in alcuni container).
if settings.ocr_tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.ocr_tesseract_cmd


def _ocr_image(img: "Image.Image") -> str:
    return pytesseract.image_to_string(img, lang=settings.ocr_lang)


def ocr_pdf_file(pdf_path: Path) -> str:
    """Esegue l'OCR locale su tutte le pagine del PDF e ritorna il testo unito.

    Solleva se il PDF non è leggibile; l'eventuale mancanza del binario Tesseract
    emerge come pytesseract.TesseractNotFoundError, gestita a monte dall'upload
    (il PDF resta comunque salvato).
    """
    testo_pagine: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=settings.ocr_dpi)
            with Image.open(io.BytesIO(pix.tobytes("png"))) as img:
                testo_pagine.append(_ocr_image(img).strip())
    return "\n\n".join(t for t in testo_pagine if t).strip()
