# Note per il deploy (Fase 6) — requisiti runtime del backend

Raccolta di tutto ciò che il `Dockerfile` del backend dovrà includere. Aggiornato
mano a mano che le fasi introducono nuove dipendenze.

## 1. Dipendenze di sistema (apt)

L'OCR locale (Tesseract) non è una libreria Python: serve il binario di sistema
+ i dati di lingua. Nel Dockerfile (base `python:3.11-slim` o simile):

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ita \
    && rm -rf /var/lib/apt/lists/*
```

- `tesseract-ocr` = motore. `tesseract-ocr-ita` = lingua italiana (la usa `settings.ocr_lang="ita"`).
- Se il binario non finisse nel PATH, impostare `OCR_TESSERACT_CMD` col percorso.

## 2. Dipendenze Python

Installare **dal lockfile** per riproducibilità (versioni esatte, non le loose):

```dockerfile
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
```

Pacchetti "pesanti" introdotti e perché:
- `fastembed` (== 0.8.0) + `onnxruntime`: embedding per la ricerca semantica, su CPU, **senza PyTorch**.
- `pytesseract` + `Pillow`: ponte verso Tesseract e rendering immagini.
- `PyMuPDF`: rende le pagine PDF in immagine per l'OCR e conta le pagine.

> **Importante (riproducibilità embedding):** fastembed 0.8 usa mean-pooling per il
> modello MiniLM (avviso all'avvio). Tenendo la versione pinnata nel lock, gli
> embedding restano identici nel tempo. Se si cambia versione di fastembed, va
> rifatto il reindex completo (`POST /admin/reindex?tutti=true`) perché i vettori
> potrebbero non essere più confrontabili con quelli vecchi.

## 3. Modello di embedding — pre-scaricarlo nell'immagine

Di default fastembed scarica il modello (~220MB) al primo uso. Per evitare il
download a runtime (e per far girare l'app anche offline), pre-scaricarlo durante
la build così finisce dentro l'immagine:

```dockerfile
ENV FASTEMBED_CACHE_PATH=/opt/models
RUN python -c "from fastembed import TextEmbedding; \
    TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"
```

(Il nome modello deve combaciare con `settings.embedding_model`. Se lo si cambia
via env, aggiornare anche questa riga.)

## 4. Variabili d'ambiente (tutte configurabili, come richiesto dal prof)

Da passare al container (compose `environment:` o `env_file`):

| Variabile | Default | A cosa serve |
|---|---|---|
| `JWT_SECRET` | (dev) | **Da impostare in produzione** a un valore casuale robusto. |
| `VIEWER_PASSWORD` / `ADMIN_PASSWORD` | (dev) | Le due password di team. Da cambiare. |
| `OCR_LANG` | `ita` | Lingua Tesseract (es. `ita+eng`). |
| `OCR_DPI` | `300` | Risoluzione rendering pagine per l'OCR. |
| `EMBEDDING_MODEL` | MiniLM multilingue | Modello embedding (deve combaciare col pre-download). |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Endpoint OpenAI-compatibile del chatbot (Fase 5): Ollama/vLLM/API. |
| `LLM_MODEL` | `qwen2.5:3b` | Modello del chatbot (Fase 5). |
| `LLM_API_KEY` | (vuota) | Chiave se l'endpoint LLM la richiede (Fase 5). |
| `CORS_ORIGINS` | localhost:5173 | Origine/i del frontend in produzione. |

Nota: `MISTRAL_API_KEY` **non serve più** (l'OCR è locale). Si può omettere.

## 5. Volumi persistenti (dati che non stanno nell'immagine)

Montare come volumi, non copiare nell'immagine:
- `archivio.db` (contiene documenti, utenti, preferiti, commenti, **e i chunk/embedding**).
- `documenti_pdf/` e `testo_estratto/`.
- `OCR database.xlsx` (per il resync metadati).

## 6. Passo una-tantum dopo il primo deploy

Se il volume `archivio.db` è **nuovo/vuoto di chunk**, costruire l'indice semantico:
```
POST /admin/reindex          # indicizza solo i documenti senza chunk
```
Se invece si monta un `archivio.db` che ha già i chunk (es. copiato da qui), non
serve: è già pronto. I nuovi upload si indicizzano da soli.

## 7. Riepilogo servizi (docker-compose, Fase 6)

- **backend**: questa immagine (FastAPI + Tesseract + fastembed).
- **frontend**: build React servita da nginx, proxy `/api` → backend.
- **ollama** (o vLLM), opzionale: solo se il chatbot RAG gira in locale nel loro cloud.
  In alternativa `LLM_BASE_URL` punta a un'API esterna e questo servizio non serve.
