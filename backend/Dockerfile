# Immagine del backend FastAPI (vedi DEPLOY_NOTES.md).
# Il codice sta in /srv/backend: config.py ricava PROJECT_ROOT=/srv e le
# migrazioni Alembic vengono cercate in PROJECT_ROOT/backend/alembic.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/opt/models

# Tesseract + lingua italiana per l'OCR dei nuovi upload
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-ita \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/backend

COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt

# Modello di embedding pre-scaricato nell'immagine (niente download a runtime).
# Deve combaciare con settings.embedding_model.
RUN python -c "from fastembed import TextEmbedding; \
TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')" \
    && chmod -R a+rwX /opt/models

COPY . .

EXPOSE 8090
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
