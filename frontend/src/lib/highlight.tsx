import { Mark } from '@mantine/core'
import type { ReactNode } from 'react'

/**
 * Radice della parola cercata: toglie la vocale finale (anche accentata) per
 * catturare le varianti. Es. "valido" -> "valid", così l'evidenziazione copre
 * "valido", "validità", "validazione" — le stesse parole che la ricerca
 * semantica considera vicine. Solo per parole abbastanza lunghe, per non
 * allargare troppo su termini corti.
 */
function radice(term: string): string {
  const t = term.toLowerCase()
  return t.length > 4 && /[aeiouàèéìòù]$/.test(t) ? t.slice(0, -1) : t
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function buildRegex(query: string): RegExp | null {
  const radici = query
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((t) => escapeRegex(radice(t)))
  if (radici.length === 0) return null
  // radice + resto della parola (lettere/numeri unicode, così include gli accenti)
  return new RegExp(`(?:${radici.join('|')})[\\p{L}\\p{N}]*`, 'giu')
}

/** Evidenzia nel testo la radice dei termini cercati e le sue varianti. */
export function highlight(text: string, query: string): ReactNode {
  const re = buildRegex(query)
  if (!re) return text
  const parts: ReactNode[] = []
  let last = 0
  for (const m of text.matchAll(re)) {
    const idx = m.index ?? 0
    if (idx > last) parts.push(<span key={`t${last}`}>{text.slice(last, idx)}</span>)
    parts.push(<Mark key={`m${idx}`}>{m[0]}</Mark>)
    last = idx + m[0].length
  }
  if (last < text.length) parts.push(<span key={`t${last}`}>{text.slice(last)}</span>)
  return parts
}

/** Rimuove i tag <mark> dello snippet FTS: la ri-evidenziazione la fa `highlight`. */
export function stripMarks(s: string): string {
  return s.replace(/<\/?mark>/g, '')
}
