// Tipi che rispecchiano gli schemi Pydantic del backend.

export interface DocumentoListItem {
  id: number
  nome_file: string
  cartella: string
  descrizione: string
  data_documento: string
  num_pagine: number
  validita: string
  is_preferito: number
  anteprima: string
  snippet: string
  match_semantico: boolean
}

export interface DocumentoDetail {
  id: number
  nome_file: string
  cartella: string
  descrizione: string
  data_documento: string
  num_pagine: number
  validita: string
  is_preferito: number
  percorso_pdf: string
  percorso_md: string
  contenuto_md: string
  scrittura: number
  note: string
  annotazioni_team: string
}

export interface DocumentoListResponse {
  total: number
  items: DocumentoListItem[]
}

export interface LoginResponse {
  access_token: string
  token_type: string
  role: string
  nome: string
  expires_in: number
}

export interface Commento {
  id: number
  autore: string
  testo: string
  creato_il: string
}

export interface UtenteAdmin {
  id: number
  nome: string
  attivo: number
}

export interface EventoAudit {
  id: number
  documento_id: number
  autore: string
  azione: string
  dettaglio: string
  creato_il: string
}

export interface UploadResult {
  documento: DocumentoDetail
  ocr_ok: boolean
  warning: string | null
}

export interface MetadataUpdate {
  descrizione?: string
  data_documento?: string
  num_pagine?: number
  note?: string
  validita?: string
}

export interface ResyncResult {
  righe_excel: number
  documenti_aggiornati: number
  id_non_corrisposti: string[]
}

export interface ListParams {
  q?: string
  cartelle?: string[]
  solo_preferiti?: boolean
  validita?: 'tutti' | 'validi' | 'non_validi'
  anno_da?: number
  anno_a?: number
  limit?: number
  offset?: number
}

export interface CartellaInfo {
  cartella: string
  anno_min: number | null
  anno_max: number | null
  documenti: number
}

export interface FonteRag {
  doc_id: number
  nome_file: string
  descrizione: string
}

export interface ChatResponse {
  risposta: string
  fonti: FonteRag[]
}
