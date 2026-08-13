/**
 * Valori di validità di un documento, come nell'Excel dell'archivio.
 * "parzialmente" = ancora valido solo in parte.
 */
export const VALORI_VALIDITA: readonly string[] = ['si', 'no', 'parzialmente']

export const ETICHETTE_VALIDITA: Record<string, string> = {
  si: 'Valido',
  no: 'Non valido',
  parzialmente: 'Parzialmente valido',
}

export const COLORI_VALIDITA: Record<string, string> = {
  si: 'green',
  no: 'red',
  parzialmente: 'orange',
}

/** Opzioni per i menu di scelta (creazione/modifica documento). */
export const OPZIONI_VALIDITA = VALORI_VALIDITA.map((v) => ({
  value: v,
  label: ETICHETTE_VALIDITA[v],
}))
