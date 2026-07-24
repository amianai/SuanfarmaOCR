"""Conversione immagini → PDF lossless (porta la logica di converti_in_pdf.py)."""

import fitz  # PyMuPDF


def tiff_bytes_to_pdf_bytes(tiff_bytes: bytes) -> bytes:
    """Converte un TIFF (anche multipagina) in PDF lossless, ritornando i byte del PDF."""
    img_doc = fitz.open(stream=tiff_bytes, filetype="tif")
    try:
        return img_doc.convert_to_pdf()
    finally:
        img_doc.close()


def pdf_page_count(pdf_bytes: bytes) -> int:
    """Numero di pagine di un PDF. Solleva se i byte non sono un PDF valido."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return doc.page_count
