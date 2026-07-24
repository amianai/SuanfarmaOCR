// Client API: percorsi relativi sotto /api (proxy Vite in dev, nginx in prod).
// Gestisce Bearer token, refresh scorrevole (header X-Refreshed-Token) e 401.

import type {
  CartellaInfo,
  ChatResponse,
  Commento,
  DocumentoDetail,
  DocumentoListResponse,
  EventoAudit,
  ListParams,
  LoginResponse,
  MetadataUpdate,
  ResyncResult,
  UploadResult,
  UtenteAdmin,
} from './types'

const TOKEN_KEY = 'archivio_token'
const ROLE_KEY = 'archivio_role'
const NOME_KEY = 'archivio_nome'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getRole(): string | null {
  return localStorage.getItem(ROLE_KEY)
}

export function getNome(): string | null {
  return localStorage.getItem(NOME_KEY)
}

export function saveAuth(token: string, role: string, nome: string): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(ROLE_KEY, role)
  localStorage.setItem(NOME_KEY, nome)
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(ROLE_KEY)
  localStorage.removeItem(NOME_KEY)
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function fetchApi(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(`/api${path}`, { ...options, headers })

  // Refresh scorrevole: il backend allega un token nuovo quando quello
  // corrente è oltre metà vita. Lo sostituiamo in modo trasparente.
  const refreshed = res.headers.get('X-Refreshed-Token')
  if (refreshed) localStorage.setItem(TOKEN_KEY, refreshed)

  if (res.status === 401) {
    clearAuth()
    window.dispatchEvent(new Event('auth-expired'))
    throw new ApiError('Sessione scaduta', 401)
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* corpo non-JSON: teniamo statusText */
    }
    throw new ApiError(detail, res.status)
  }
  return res
}

async function fetchJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetchApi(path, options)
  return res.json() as Promise<T>
}

function jsonBody(body: unknown): RequestInit {
  return {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export const api = {
  // Nomi selezionabili al login (endpoint pubblico).
  async listNomi(): Promise<string[]> {
    const res = await fetch('/api/auth/utenti')
    return res.ok ? res.json() : []
  },

  // Login: fetch diretto, un 401 qui significa "password errata", non sessione scaduta.
  async login(password: string, nome: string): Promise<LoginResponse> {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      ...jsonBody({ password, nome }),
    })
    if (!res.ok) {
      const detail = (await res.json().catch(() => null))?.detail ?? 'Errore di autenticazione'
      throw new ApiError(detail, res.status)
    }
    return res.json()
  },

  me(): Promise<{ role: string; nome: string }> {
    return fetchJson('/auth/me')
  },

  listDocuments(params: ListParams = {}): Promise<DocumentoListResponse> {
    const qs = new URLSearchParams()
    const { cartelle, ...rest } = params
    for (const [key, value] of Object.entries(rest)) {
      if (value !== undefined && value !== null && value !== '') qs.set(key, String(value))
    }
    // Multi-selezione faldoni: parametro ripetuto (?cartella=B01&cartella=B02)
    for (const c of cartelle ?? []) qs.append('cartella', c)
    const suffix = qs.toString() ? `?${qs}` : ''
    return fetchJson(`/documents${suffix}`)
  },

  listCartelle(): Promise<CartellaInfo[]> {
    return fetchJson('/documents/cartelle')
  },

  getDocument(id: number): Promise<DocumentoDetail> {
    return fetchJson(`/documents/${id}`)
  },

  async getPdfBlob(id: number): Promise<Blob> {
    const res = await fetchApi(`/documents/${id}/pdf`)
    return res.blob()
  },

  setPreferito(id: number, preferito: boolean): Promise<{ preferito: boolean }> {
    return fetchJson(`/documents/${id}/preferito`, {
      method: 'PUT',
      ...jsonBody({ preferito }),
    })
  },

  listCommenti(docId: number): Promise<Commento[]> {
    return fetchJson(`/documents/${docId}/commenti`)
  },

  addCommento(docId: number, testo: string): Promise<Commento> {
    return fetchJson(`/documents/${docId}/commenti`, { method: 'POST', ...jsonBody({ testo }) })
  },

  async deleteCommento(docId: number, commentoId: number): Promise<void> {
    await fetchApi(`/documents/${docId}/commenti/${commentoId}`, { method: 'DELETE' })
  },

  // --- Admin ---

  uploadDocument(file: File, fields: Record<string, string>): Promise<UploadResult> {
    const form = new FormData()
    form.set('file', file)
    for (const [k, v] of Object.entries(fields)) form.set(k, v)
    // Niente Content-Type esplicito: il browser imposta il boundary multipart.
    return fetchJson('/admin/documents', { method: 'POST', body: form })
  },

  updateMetadata(id: number, update: MetadataUpdate): Promise<DocumentoDetail> {
    return fetchJson(`/admin/documents/${id}`, { method: 'PATCH', ...jsonBody(update) })
  },

  deleteDocument(id: number): Promise<DocumentoDetail> {
    return fetchJson(`/admin/documents/${id}`, { method: 'DELETE' })
  },

  restoreDocument(id: number): Promise<DocumentoDetail> {
    return fetchJson(`/admin/documents/${id}/restore`, { method: 'POST' })
  },

  listDeleted(): Promise<DocumentoDetail[]> {
    return fetchJson('/admin/documents/deleted')
  },

  resyncExcel(): Promise<ResyncResult> {
    return fetchJson('/admin/resync-excel', { method: 'POST' })
  },

  listUtenti(): Promise<UtenteAdmin[]> {
    return fetchJson('/admin/utenti')
  },

  addUtente(nome: string): Promise<UtenteAdmin> {
    return fetchJson('/admin/utenti', { method: 'POST', ...jsonBody({ nome }) })
  },

  setUtenteAttivo(id: number, attivo: boolean): Promise<UtenteAdmin> {
    return fetchJson(`/admin/utenti/${id}`, { method: 'PATCH', ...jsonBody({ attivo }) })
  },

  async deleteUtente(id: number): Promise<void> {
    await fetchApi(`/admin/utenti/${id}`, { method: 'DELETE' })
  },

  listAudit(documentoId?: number): Promise<EventoAudit[]> {
    const qs = documentoId != null ? `?documento_id=${documentoId}` : ''
    return fetchJson(`/admin/audit${qs}`)
  },

  chat(domanda: string): Promise<ChatResponse> {
    return fetchJson('/chat', { method: 'POST', ...jsonBody({ domanda }) })
  },
}
