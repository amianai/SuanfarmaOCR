import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ActionIcon,
  AppShell,
  Badge,
  Button,
  Card,
  Center,
  CloseButton,
  Group,
  Loader,
  MultiSelect,
  NumberInput,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
  useMantineColorScheme,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import {
  IconLogout,
  IconMessageChatbot,
  IconMoon,
  IconSearch,
  IconSparkles,
  IconStarFilled,
  IconSun,
  IconTrash,
  IconUpload,
  IconUsers,
} from '@tabler/icons-react'
import { api } from '../api/client'
import type { CartellaInfo, DocumentoListItem } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { highlight, stripMarks } from '../lib/highlight'

/** Etichetta faldone con range anni, es. "B01 (1970–1979)". */
function labelCartella(c: CartellaInfo): string {
  if (c.anno_min == null) return `${c.cartella} (date n.d.)`
  const range = c.anno_min === c.anno_max ? `${c.anno_min}` : `${c.anno_min}–${c.anno_max}`
  return `${c.cartella} (${range})`
}

function DocumentCard({
  doc,
  query,
  searchString,
}: {
  doc: DocumentoListItem
  query: string
  searchString: string
}) {
  const navigate = useNavigate()
  // Estratto FTS (senza i suoi <mark>) o anteprima; l'evidenziazione la ricalcola `highlight`.
  const preview =
    (doc.snippet ? stripMarks(doc.snippet) : doc.anteprima) || 'Nessuna anteprima disponibile.'
  return (
    <Card
      withBorder
      radius="md"
      padding="md"
      style={{ cursor: 'pointer' }}
      onClick={() => navigate(`/doc/${doc.id}?${searchString}`)}
    >
      <Group gap="xs" mb={6}>
        <Badge variant="light" color="indigo">
          {doc.nome_file}
        </Badge>
        {doc.num_pagine > 0 && <Badge variant="default">{doc.num_pagine} pag.</Badge>}
        {doc.data_documento && <Badge variant="default">{doc.data_documento}</Badge>}
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
        {doc.is_preferito === 1 && (
          <Badge variant="light" color="yellow" leftSection={<IconStarFilled size={10} />}>
            Preferito
          </Badge>
        )}
        {doc.match_semantico && (
          <Badge variant="light" color="violet" leftSection={<IconSparkles size={11} />}>
            Trovato per significato
          </Badge>
        )}
      </Group>
      <Text fw={600} mb={4}>
        {doc.descrizione || doc.nome_file}
      </Text>
      <Text size="sm" c="dimmed" lineClamp={3}>
        {highlight(preview, query)}
      </Text>
    </Card>
  )
}

type Validita = 'tutti' | 'validi' | 'non_validi'

export function ListPage() {
  const { auth, isAdmin, logout } = useAuth()
  const navigate = useNavigate()
  const { colorScheme, setColorScheme } = useMantineColorScheme()

  // La URL è la fonte di verità dei filtri: tornando da un documento, la ricerca
  // si ricostruisce da qui (e diventa condivisibile via link).
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const cartelleSel = params.getAll('cartella')
  const validita = (params.get('validita') as Validita) || 'tutti'
  const annoDa = params.get('anno_da') ? Number(params.get('anno_da')) : ''
  const annoA = params.get('anno_a') ? Number(params.get('anno_a')) : ''
  const soloPreferiti = params.get('preferiti') === '1'

  function updateParams(mut: (p: URLSearchParams) => void, replace = false) {
    const next = new URLSearchParams(params)
    mut(next)
    setParams(next, { replace })
  }

  // Input di testo: stato locale per reattività, scritto in URL con debounce.
  const [search, setSearch] = useState(q)
  const [debouncedSearch] = useDebouncedValue(search, 300)
  useEffect(() => {
    if (debouncedSearch === (params.get('q') ?? '')) return
    updateParams((p) => {
      if (debouncedSearch) p.set('q', debouncedSearch)
      else p.delete('q')
    }, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch])

  const [cartelle, setCartelle] = useState<CartellaInfo[]>([])
  const [docs, setDocs] = useState<DocumentoListItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.listCartelle().then(setCartelle).catch(() => {})
  }, [])

  // I risultati seguono la URL: ogni cambio di filtro (che aggiorna la URL) rifà la fetch.
  const paramsKey = params.toString()
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .listDocuments({
        q: q || undefined,
        cartelle: cartelleSel,
        validita,
        anno_da: annoDa === '' ? undefined : annoDa,
        anno_a: annoA === '' ? undefined : annoA,
        solo_preferiti: soloPreferiti || undefined,
      })
      .then((res) => {
        if (cancelled) return
        setDocs(res.items)
        setTotal(res.total)
      })
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey])

  function clearQuery() {
    setSearch('')
    updateParams((p) => p.delete('q'))
  }

  return (
    <AppShell header={{ height: 60 }} navbar={{ width: 320, breakpoint: 'sm' }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="xs">
            <Title order={4}>Archivio OCR</Title>
            <Text size="sm" c="dimmed">
              Suanfarma — Rovereto
            </Text>
          </Group>
          <Group gap="xs">
            <Button
              variant="light"
              color="violet"
              leftSection={<IconMessageChatbot size={16} />}
              onClick={() => navigate('/chat')}
            >
              Chiedi all'archivio
            </Button>
            {isAdmin && (
              <>
                <Button leftSection={<IconUpload size={16} />} onClick={() => navigate('/upload')}>
                  Carica documento
                </Button>
                <ActionIcon
                  variant="default"
                  size="lg"
                  aria-label="Gestione utenti"
                  onClick={() => navigate('/utenti')}
                >
                  <IconUsers size={18} />
                </ActionIcon>
                <ActionIcon
                  variant="default"
                  size="lg"
                  aria-label="Cestino"
                  onClick={() => navigate('/trash')}
                >
                  <IconTrash size={18} />
                </ActionIcon>
              </>
            )}
            <Badge variant="light" color={auth?.role === 'admin' ? 'red' : 'indigo'}>
              {auth?.nome} · {auth?.role === 'admin' ? 'Amministratore' : 'Consultazione'}
            </Badge>
            <ActionIcon
              variant="default"
              size="lg"
              aria-label="Cambia tema"
              onClick={() => setColorScheme(colorScheme === 'dark' ? 'light' : 'dark')}
            >
              {colorScheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
            </ActionIcon>
            <Button variant="default" leftSection={<IconLogout size={16} />} onClick={logout}>
              Esci
            </Button>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <Stack gap="md">
          <TextInput
            label="Ricerca"
            placeholder="Parole chiave…"
            leftSection={<IconSearch size={16} />}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
          />
          <MultiSelect
            label="Faldoni"
            placeholder={cartelleSel.length === 0 ? 'Tutti' : undefined}
            data={cartelle.map((c) => ({ value: c.cartella, label: labelCartella(c) }))}
            value={cartelleSel}
            onChange={(vals) =>
              updateParams((p) => {
                p.delete('cartella')
                vals.forEach((v) => p.append('cartella', v))
              })
            }
            clearable
            searchable
            hidePickedOptions
          />
          <div>
            <Text size="sm" fw={500} mb={4}>
              Validità
            </Text>
            <SegmentedControl
              fullWidth
              value={validita}
              onChange={(v) =>
                updateParams((p) => {
                  if (v === 'tutti') p.delete('validita')
                  else p.set('validita', v)
                })
              }
              data={[
                { label: 'Tutti', value: 'tutti' },
                { label: 'Validi', value: 'validi' },
                { label: 'Non validi', value: 'non_validi' },
              ]}
            />
          </div>
          <Group grow>
            <NumberInput
              label="Anno da"
              placeholder="1970"
              min={1900}
              max={2100}
              value={annoDa}
              onChange={(v) =>
                updateParams((p) => {
                  if (typeof v === 'number') p.set('anno_da', String(v))
                  else p.delete('anno_da')
                })
              }
            />
            <NumberInput
              label="Anno a"
              placeholder="2008"
              min={1900}
              max={2100}
              value={annoA}
              onChange={(v) =>
                updateParams((p) => {
                  if (typeof v === 'number') p.set('anno_a', String(v))
                  else p.delete('anno_a')
                })
              }
            />
          </Group>
          <Switch
            label="Solo preferiti"
            checked={soloPreferiti}
            onChange={(e) =>
              updateParams((p) => {
                if (e.currentTarget.checked) p.set('preferiti', '1')
                else p.delete('preferiti')
              })
            }
          />
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main>
        <Group justify="space-between" mb="sm">
          <Group gap="xs">
            <Text size="sm" c="dimmed">
              {total} {q ? 'risultati' : 'documenti'}
            </Text>
            {q && (
              <Badge
                size="lg"
                variant="light"
                color="indigo"
                rightSection={
                  <CloseButton size="xs" aria-label="Rimuovi ricerca" onClick={clearQuery} />
                }
              >
                {q}
              </Badge>
            )}
          </Group>
        </Group>

        {loading ? (
          <Center mih={200}>
            <Loader />
          </Center>
        ) : docs.length === 0 ? (
          <Center mih={200}>
            <Text c="dimmed">Nessun documento trovato con questi filtri.</Text>
          </Center>
        ) : (
          <Stack gap="sm">
            {docs.map((doc) => (
              <DocumentCard key={doc.id} doc={doc} query={q} searchString={paramsKey} />
            ))}
          </Stack>
        )}
      </AppShell.Main>
    </AppShell>
  )
}
