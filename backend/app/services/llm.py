"""Client LLM. Due stili selezionabili da .env (LLM_API_STYLE):

- "openai" (default): protocollo OpenAI-compatibile (chat/completions). Generico,
  funziona con vLLM, API a consumo e l'endpoint /v1 di Ollama. È lo stile da
  usare in produzione, come richiesto dal committente.
- "ollama": endpoint nativo di Ollama (/api/chat) con `think=false`, per
  disattivare il ragionamento dei modelli "thinking" in sviluppo locale
  (l'endpoint OpenAI di Ollama ignora lo switch).

Nessun SDK aggiuntivo: solo httpx.
"""

import httpx

from ..core.config import settings


class LLMError(RuntimeError):
    """L'endpoint LLM non è raggiungibile o ha risposto con errore/vuoto."""


def _post(url: str, payload: dict, timeout: float) -> dict:
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        raise LLMError(f"Modello non raggiungibile: {e}") from e


def _chat_openai(messages: list[dict], temperature: float, timeout: float) -> str:
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    data = _post(
        url,
        {"model": settings.llm_model, "messages": messages, "temperature": temperature, "stream": False},
        timeout,
    )
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError) as e:
        raise LLMError(f"Risposta non valida dall'endpoint OpenAI: {e}") from e


def _chat_ollama(messages: list[dict], temperature: float, timeout: float) -> str:
    # L'endpoint nativo sta alla radice, non sotto /v1.
    base = settings.llm_base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3].rstrip("/")
    data = _post(
        base + "/api/chat",
        {
            "model": settings.llm_model,
            "messages": messages,
            "think": False,  # disattiva il ragionamento dei modelli "thinking"
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout,
    )
    try:
        return (data["message"]["content"] or "").strip()
    except KeyError as e:
        raise LLMError(f"Risposta non valida dall'endpoint Ollama: {e}") from e


def chat(messages: list[dict], temperature: float = 0.2, timeout: float | None = None) -> str:
    """Invia i messaggi al modello e ritorna il testo della risposta."""
    if timeout is None:
        timeout = settings.llm_timeout
    contenuto = (
        _chat_ollama(messages, temperature, timeout)
        if settings.llm_api_style == "ollama"
        else _chat_openai(messages, temperature, timeout)
    )
    if not contenuto:
        raise LLMError(
            "Il modello ha restituito una risposta vuota (tipico dei modelli 'thinking' "
            "senza think=false). Usa LLM_API_STYLE=ollama, oppure un modello non-thinking."
        )
    return contenuto
