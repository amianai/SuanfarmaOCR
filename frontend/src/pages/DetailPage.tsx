import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  ActionIcon,
  AppShell,
  Badge,
  Button,
  Center,
  Grid,
  Group,
  Loader,
  Modal,
  Paper,
  ScrollArea,
  Select,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
  useMantineColorScheme,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
  IconArrowLeft,
  IconChevronLeft,
  IconChevronRight,
  IconDownload,
  IconHistory,
  IconMoon,
  IconPencil,
  IconSend,
  IconStar,
  IconStarFilled,
  IconSun,
  IconTrash,
  IconX,
} from '@tabler/icons-react'
import { api } from '../api/client'
import type { Commento, DocumentoDetail, EventoAudit } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { highlight } from '../lib/highlight'

const AZIONI_AUDIT: Record<string, string> = {
  upload: 'Caricamento',
  validita: 'Cambio validità',
  metadati: 'Modifica metadati',
  delete: 'Spostato nel cestino',
  restore: 'Ripristinato',
}

function formatDataOra(iso: string): string {
  const d = new Date(iso)
  return isNaN(d.getTime())
    ? iso
    : d.toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' })
}

function downloadText(filename: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function DetailPage() {
  const { id } = useParams()
  const docId = Number(id)
  const [searchParams] = useSearchParams()
  const query = searchParams.get('q') ?? ''
  // Contesto di ricerca ereditato dalla URL: serve a tornare alla ricerca intatta
  // e a scorrere i risultati con le frecce.
  const searchString = searchParams.toString()
  const backTo = searchString ? `/?${searchString}` : '/'
  const navigate = useNavigate()
  const { colorScheme, setColorScheme } = useMantineColorScheme()
  const { auth, isAdmin } = useAuth()

  const [doc, setDoc] = useState<DocumentoDetail | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)

  // Commenti firmati
  const [commenti, setCommenti] = useState<Commento[]>([])
  const [nuovoCommento, setNuovoCommento] = useState('')
  const [savingCommento, setSavingCommento] = useState(false)

  // Storico modifiche (solo admin)
  const [auditOpen, { open: openAudit, close: closeAudit }] = useDisclosure(false)
  const [eventi, setEventi] = useState<EventoAudit[] | null>(null)

  // Elenco ordinato degli ID della ricerca corrente (per le frecce prev/next)
  const [risultatiIds, setRisultatiIds] = useState<number[] | null>(null)

  // Modifica metadati (solo admin)
  const [editOpen, { open: openEdit, close: closeEdit }] = useDisclosure(false)
  const [editDescrizione, setEditDescrizione] = useState('')
  const [editData, setEditData] = useState('')
  const [editValidita, setEditValidita] = useState('si')
  const [editNote, setEditNote] = useState('')
  const [savingEdit, setSavingEdit] = useState(false)

  useEffect(() => {
    let objectUrl: string | null = null
    api
      .getDocument(docId)
      .then((d) => {
        setDoc(d)
        return api.getPdfBlob(docId)
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        setPdfUrl(objectUrl)
      })
      .catch(() => {})
    api.listCommenti(docId).then(setCommenti).catch(() => {})
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [docId])

  // Riesegue la ricerca corrente per ottenere l'ordine dei risultati (frecce prev/next).
  // Solo se c'è un contesto di ricerca/filtri nella URL.
  useEffect(() => {
    if (!searchString) {
      setRisultatiIds(null)
      return
    }
    let cancelled = false
    api
      .listDocuments({
        q: searchParams.get('q') || undefined,
        cartelle: searchParams.getAll('cartella'),
        validita: (searchParams.get('validita') as 'tutti' | 'validi' | 'non_validi') || 'tutti',
        anno_da: searchParams.get('anno_da') ? Number(searchParams.get('anno_da')) : undefined,
        anno_a: searchParams.get('anno_a') ? Number(searchParams.get('anno_a')) : undefined,
        solo_preferiti: searchParams.get('preferiti') === '1' || undefined,
        limit: 500,
      })
      .then((res) => !cancelled && setRisultatiIds(res.items.map((i) => i.id)))
      .catch(() => !cancelled && setRisultatiIds(null))
    return () => {
      cancelled = true
    }
  }, [searchString, searchParams])

  async function togglePreferito() {
    if (!doc) return
    const res = await api.setPreferito(doc.id, doc.is_preferito !== 1)
    setDoc({ ...doc, is_preferito: res.preferito ? 1 : 0 })
  }

  async function inviaCommento() {
    if (!doc || !nuovoCommento.trim()) return
    setSavingCommento(true)
    try {
      const c = await api.addCommento(doc.id, nuovoCommento.trim())
      setCommenti((prev) => [...prev, c])
      setNuovoCommento('')
    } catch {
      notifications.show({ message: "Errore nell'invio del commento", color: 'red' })
    } finally {
      setSavingCommento(false)
    }
  }

  async function eliminaCommento(c: Commento) {
    if (!doc) return
    try {
      await api.deleteCommento(doc.id, c.id)
      setCommenti((prev) => prev.filter((x) => x.id !== c.id))
    } catch {
      notifications.show({ message: 'Non puoi eliminare questo commento', color: 'red' })
    }
  }

  function apriStorico() {
    if (!doc) return
    setEventi(null)
    openAudit()
    api.listAudit(doc.id).then(setEventi).catch(() => setEventi([]))
  }

  function startEdit() {
    if (!doc) return
    setEditDescrizione(doc.descrizione)
    setEditData(doc.data_documento)
    setEditValidita(doc.validita === 'no' ? 'no' : 'si')
    setEditNote(doc.note)
    openEdit()
  }

  async function salvaMetadati() {
    if (!doc) return
    setSavingEdit(true)
    try {
      const updated = await api.updateMetadata(doc.id, {
        descrizione: editDescrizione,
        data_documento: editData,
        validita: editValidita,
        note: editNote,
      })
      setDoc(updated)
      closeEdit()
      notifications.show({ message: 'Metadati aggiornati', color: 'green' })
    } catch (err) {
      notifications.show({
        message: err instanceof Error ? err.message : 'Errore nel salvataggio',
        color: 'red',
      })
    } finally {
      setSavingEdit(false)
    }
  }

  async function eliminaDocumento() {
    if (!doc) return
    if (!window.confirm(`Spostare ${doc.nome_file} nel cestino? Potrà essere ripristinato.`)) return
    await api.deleteDocument(doc.id)
    notifications.show({ message: `${doc.nome_file} spostato nel cestino`, color: 'yellow' })
    navigate(backTo)
  }

  // Posizione nella ricerca e ID adiacenti per le frecce prev/next.
  const idxCorrente = risultatiIds ? risultatiIds.indexOf(docId) : -1
  const mostraNav = idxCorrente >= 0 && risultatiIds !== null
  const prevId = idxCorrente > 0 ? risultatiIds![idxCorrente - 1] : null
  const nextId =
    risultatiIds && idxCorrente >= 0 && idxCorrente < risultatiIds.length - 1
      ? risultatiIds[idxCorrente + 1]
      : null

  if (!doc) {
    return (
      <Center mih="100vh">
        <Loader />
      </Center>
    )
  }

  return (
    <AppShell header={{ height: 60 }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="xs">
            <Button
              variant="default"
              leftSection={<IconArrowLeft size={16} />}
              onClick={() => navigate(backTo)}
            >
              {searchString ? 'Torna alla ricerca' : 'Torna alla lista'}
            </Button>
            {mostraNav && (
              <Group gap={4}>
                <ActionIcon
                  variant="default"
                  size="lg"
                  aria-label="Documento precedente"
                  disabled={prevId === null}
                  onClick={() => prevId !== null && navigate(`/doc/${prevId}?${searchString}`)}
                >
                  <IconChevronLeft size={18} />
                </ActionIcon>
                <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                  {idxCorrente + 1} / {risultatiIds!.length}
                </Text>
                <ActionIcon
                  variant="default"
                  size="lg"
                  aria-label="Documento successivo"
                  disabled={nextId === null}
                  onClick={() => nextId !== null && navigate(`/doc/${nextId}?${searchString}`)}
                >
                  <IconChevronRight size={18} />
                </ActionIcon>
              </Group>
            )}
            <Title order={5}>{doc.nome_file}</Title>
          </Group>
          <Group gap="xs">
            {isAdmin && (
              <>
                <Button
                  variant="default"
                  leftSection={<IconPencil size={16} />}
                  onClick={startEdit}
                >
                  Modifica
                </Button>
                <ActionIcon
                  variant="default"
                  size="lg"
                  aria-label="Storico modifiche"
                  onClick={apriStorico}
                >
                  <IconHistory size={18} />
                </ActionIcon>
                <ActionIcon
                  variant="default"
                  color="red"
                  size="lg"
                  aria-label="Elimina"
                  onClick={eliminaDocumento}
                >
                  <IconTrash size={18} />
                </ActionIcon>
              </>
            )}
            <ActionIcon
              variant={doc.is_preferito === 1 ? 'filled' : 'default'}
              color="yellow"
              size="lg"
              aria-label="Preferito"
              onClick={togglePreferito}
            >
              {doc.is_preferito === 1 ? <IconStarFilled size={18} /> : <IconStar size={18} />}
            </ActionIcon>
            <ActionIcon
              variant="default"
              size="lg"
              aria-label="Cambia tema"
              onClick={() => setColorScheme(colorScheme === 'dark' ? 'light' : 'dark')}
            >
              {colorScheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
            </ActionIcon>
          </Group>
        </Group>
      </AppShell.Header>

      <Modal opened={editOpen} onClose={closeEdit} title="Modifica metadati" centered>
        <Stack gap="sm">
          <TextInput
            label="Descrizione"
            value={editDescrizione}
            onChange={(e) => setEditDescrizione(e.currentTarget.value)}
          />
          <TextInput
            label="Data documento"
            placeholder="gg/mm/aaaa"
            value={editData}
            onChange={(e) => setEditData(e.currentTarget.value)}
          />
          <Select
            label="Validità"
            data={[
              { value: 'si', label: 'Valido' },
              { value: 'no', label: 'Non valido' },
            ]}
            value={editValidita}
            onChange={(v) => setEditValidita(v ?? 'si')}
            allowDeselect={false}
          />
          <Textarea
            label="Note archivio"
            value={editNote}
            onChange={(e) => setEditNote(e.currentTarget.value)}
            autosize
            minRows={2}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={closeEdit}>
              Annulla
            </Button>
            <Button loading={savingEdit} onClick={salvaMetadati}>
              Salva
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal opened={auditOpen} onClose={closeAudit} title="Storico modifiche" centered size="lg">
        {eventi === null ? (
          <Center mih={120}>
            <Loader size="sm" />
          </Center>
        ) : eventi.length === 0 ? (
          <Text size="sm" c="dimmed">
            Nessun evento registrato per questo documento (la tracciabilità parte
            dall'introduzione dello storico).
          </Text>
        ) : (
          <Stack gap="xs">
            {eventi.map((e) => (
              <Paper key={e.id} withBorder radius="sm" p="xs">
                <Group justify="space-between" gap="xs">
                  <Text size="sm" fw={600}>
                    {AZIONI_AUDIT[e.azione] ?? e.azione}
                    {e.dettaglio && (
                      <Text span size="sm" c="dimmed" fw={400}>
                        {' '}
                        — {e.dettaglio}
                      </Text>
                    )}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {e.autore} · {formatDataOra(e.creato_il)}
                  </Text>
                </Group>
              </Paper>
            ))}
          </Stack>
        )}
      </Modal>

      <AppShell.Main>
        <Stack gap="md">
          <Paper withBorder radius="md" p="md">
            <Group gap="xs" mb={6}>
              <Badge variant="light" color="indigo">
                {doc.cartella}
              </Badge>
              {doc.data_documento && <Badge variant="default">{doc.data_documento}</Badge>}
              {doc.num_pagine > 0 && <Badge variant="default">{doc.num_pagine} pag.</Badge>}
              {doc.validita === 'si' && (
                <Badge variant="light" color="green">
                  Valido
                </Badge>
              )}
              {doc.validita === 'no' && (
                <Badge variant="light" color="red">
                  Non valido
                </Badge>
              )}
            </Group>
            <Title order={4}>{doc.descrizione || doc.nome_file}</Title>
            {doc.note && (
              <Text size="sm" c="dimmed" mt={4}>
                Note archivio: {doc.note}
              </Text>
            )}
          </Paper>

          <Grid>
            <Grid.Col span={{ base: 12, md: 7 }}>
              {pdfUrl ? (
                <iframe
                  title={`PDF ${doc.nome_file}`}
                  src={pdfUrl}
                  style={{
                    width: '100%',
                    height: '75vh',
                    border: '1px solid var(--mantine-color-default-border)',
                    borderRadius: 8,
                  }}
                />
              ) : (
                <Center mih={300}>
                  <Loader />
                </Center>
              )}
            </Grid.Col>

            <Grid.Col span={{ base: 12, md: 5 }}>
              <Stack gap="md">
                <Paper withBorder radius="md" p="md">
                  <Text fw={600} mb={6}>
                    Commenti del team
                  </Text>
                  <Stack gap="xs" mb="sm">
                    {commenti.length === 0 && (
                      <Text size="sm" c="dimmed">
                        Nessun commento su questo documento.
                      </Text>
                    )}
                    {commenti.map((c) => (
                      <Paper key={c.id} withBorder radius="sm" p="xs">
                        <Group justify="space-between" gap="xs" mb={2}>
                          <Text size="xs" fw={600}>
                            {c.autore}
                            <Text span size="xs" c="dimmed" fw={400}>
                              {' '}
                              · {formatDataOra(c.creato_il)}
                            </Text>
                          </Text>
                          {(isAdmin || c.autore === auth?.nome) && (
                            <ActionIcon
                              variant="subtle"
                              color="red"
                              size="xs"
                              aria-label="Elimina commento"
                              onClick={() => eliminaCommento(c)}
                            >
                              <IconX size={12} />
                            </ActionIcon>
                          )}
                        </Group>
                        <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                          {c.testo}
                        </Text>
                      </Paper>
                    ))}
                  </Stack>
                  <Group gap="xs" align="flex-end">
                    <Textarea
                      placeholder="Scrivi un commento…"
                      autosize
                      minRows={1}
                      maxRows={4}
                      style={{ flex: 1 }}
                      value={nuovoCommento}
                      onChange={(e) => setNuovoCommento(e.currentTarget.value)}
                    />
                    <ActionIcon
                      size="lg"
                      aria-label="Invia commento"
                      loading={savingCommento}
                      disabled={!nuovoCommento.trim()}
                      onClick={inviaCommento}
                    >
                      <IconSend size={16} />
                    </ActionIcon>
                  </Group>
                </Paper>

                <Paper withBorder radius="md" p="md">
                  <Group justify="space-between" mb={6}>
                    <Text fw={600}>Testo estratto (OCR)</Text>
                    <Group gap={4}>
                      <Button
                        size="compact-xs"
                        variant="default"
                        leftSection={<IconDownload size={14} />}
                        onClick={() => downloadText(`${doc.nome_file}.md`, doc.contenuto_md)}
                      >
                        .md
                      </Button>
                      <Button
                        size="compact-xs"
                        variant="default"
                        leftSection={<IconDownload size={14} />}
                        onClick={() => downloadText(`${doc.nome_file}.txt`, doc.contenuto_md)}
                      >
                        .txt
                      </Button>
                    </Group>
                  </Group>
                  {doc.contenuto_md ? (
                    <ScrollArea h="55vh">
                      <Text style={{ whiteSpace: 'pre-wrap' }}>
                        {highlight(doc.contenuto_md, query)}
                      </Text>
                    </ScrollArea>
                  ) : (
                    <Text c="dimmed" size="sm">
                      Nessun testo estratto per questo documento.
                    </Text>
                  )}
                </Paper>
              </Stack>
            </Grid.Col>
          </Grid>
        </Stack>
      </AppShell.Main>
    </AppShell>
  )
}
