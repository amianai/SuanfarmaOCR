"""OCR via API REST Mistral — LEGACY.

Non più usato dall'upload dell'interfaccia (ora l'OCR è locale via Tesseract,
vedi services/ocr.py). Conservato solo come riferimento della pipeline con cui
furono processati i 257 documenti storici. Non richiede più la chiave in
esecuzione normale del backend.
"""

from pathlib import Path

import requests

from ..core.config import settings

FILES_URL = "https://api.mistral.ai/v1/files"
OCR_URL = "https://api.mistral.ai/v1/ocr"


def _headers_auth() -> dict:
    if not settings.mistral_api_key:
        raise RuntimeError("MISTRAL_API_KEY non configurata nel .env")
    return {"Authorization": f"Bearer {settings.mistral_api_key}"}


def upload_file_to_mistral(pdf_path: Path) -> str:
    """Carica il PDF sulle API Files di Mistral e ritorna il file_id."""
    with open(pdf_path, "rb") as f:
        files = {
            "purpose": (None, "ocr"),
            "file": (pdf_path.name, f, "application/pdf"),
        }
        response = requests.post(FILES_URL, headers=_headers_auth(), files=files, timeout=60)
        response.raise_for_status()
        return response.json()["id"]


def run_ocr(file_id: str) -> str:
    """Esegue l'OCR (mistral-ocr-latest) sul file_id e ritorna il markdown aggregato."""
    headers = {**_headers_auth(), "Content-Type": "application/json"}
    payload = {
        "model": "mistral-ocr-latest",
        "document": {"type": "document_url", "document_url": f"mistral://{file_id}"},
    }
    response = requests.post(OCR_URL, headers=headers, json=payload, timeout=180)
    # Fallback per la formattazione deprecata document -> file_id
    if response.status_code == 422:
        payload["document"] = {"file_id": file_id}
        response = requests.post(OCR_URL, headers=headers, json=payload, timeout=180)
    response.raise_for_status()
    data = response.json()
    return "\n\n".join(page.get("markdown", "") for page in data.get("pages", []))


def ocr_pdf_file(pdf_path: Path) -> str:
    """Upload + OCR in un solo passo."""
    return run_ocr(upload_file_to_mistral(pdf_path))
