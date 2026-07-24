# Archivio OCR — Suanfarma (Rovereto)

Applicazione web per la consultazione e gestione dell'archivio storico documentale
(verbali, accordi sindacali, documenti aziendali 1970–2020) digitalizzato via OCR.

- **Backend**: FastAPI + SQLAlchemy su SQLite (con FTS5 per la ricerca full-text).
- **Frontend**: React + Vite + TypeScript + Mantine.
- **Ricerca ibrida**: full-text + semantica (embedding locali, fastembed/ONNX).
- **Chatbot RAG**: domande in linguaggio naturale sull'archivio con citazioni,
  tramite un LLM locale (Ollama) o qualunque endpoint OpenAI-compatibile.
- **OCR** dei nuovi documenti: locale via Tesseract (nessuna API esterna).

> **Codice e dati sono separati.** Questo repository contiene **solo il codice**.
> I dati (PDF, database `archivio.db`, Excel dei metadati) si scaricano a parte
> e la loro posizione si indica con la variabile d'ambiente `DATA_DIR`.

## Struttura

```
backend/     API FastAPI, servizi (OCR, embedding, RAG), migrazioni Alembic, test
frontend/    SPA React (Vite + Mantine)
```

## Prerequisiti

- **Python 3.11+** e **Node.js 18+**
- **Tesseract** con lingua italiana (per l'OCR dei nuovi upload):
  - macOS: `brew install tesseract tesseract-lang`
  - Debian/Ubuntu: `apt-get install tesseract-ocr tesseract-ocr-ita`
- **Ollama** (opzionale, per il chatbot RAG in locale): https://ollama.com

## Configurazione

```bash
cp .env.example .env
```
Poi apri `.env` e imposta almeno: `DATA_DIR` (cartella dei dati scaricati),
`JWT_SECRET`, `VIEWER_PASSWORD`, `ADMIN_PASSWORD`. Vedi i commenti nel file.

## Dati

I dati non sono nel repository. Scaricali dalla cartella Drive del progetto e
mettili in una cartella qualsiasi, poi indica quella cartella in `DATA_DIR`.
La cartella deve contenere: `archivio.db`, `documenti_pdf/`, `testo_estratto/`,
`OCR database.xlsx`.

## Avvio in sviluppo

Backend (porta 8000):
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head          # allinea lo schema del database
uvicorn app.main:app --port 8000
```

Frontend (porta 5173), in un secondo terminale:
```bash
cd frontend
npm install
npm run dev
```
Apri http://localhost:5173. Il frontend inoltra le chiamate `/api` al backend.

## Chatbot RAG (opzionale)

```bash
ollama pull qwen2.5:3b            # o un altro modello
```
Imposta nel `.env`: `LLM_BASE_URL`, `LLM_MODEL`, e `LLM_API_STYLE`
(`ollama` per i modelli "thinking", altrimenti `openai`).
Alla prima ricerca semantica il modello di embedding (~220MB) viene scaricato in cache.

## Test

```bash
cd backend && source .venv/bin/activate && pytest
```

## Deploy

Containerizzazione con Docker in preparazione (vedi `backend/DEPLOY_NOTES.md`).
