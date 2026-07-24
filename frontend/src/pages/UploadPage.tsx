import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  AppShell,
  Button,
  FileInput,
  Group,
  Paper,
  Select,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconArrowLeft,
  IconFileUpload,
  IconRefresh,
  IconUpload,
} from '@tabler/icons-react'
import { api } from '../api/client'

const NUOVO_FALDONE = '__nuovo__'

export function UploadPage() {
  const navigate = useNavigate()

  const [cartelle, setCartelle] = useState<string[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [cartella, setCartella] = useState<string | null>(null)
  const [nuovoFaldone, setNuovoFaldone] = useState('')
  const [descrizione, setDescrizione] = useState('')
  const [dataDocumento, setDataDocumento] = useState('')
  const [validita, setValidita] = useState<string>('si')
  const [note, setNote] = useState('')
  const [uploading, setUploading] = useState(false)
  const [resyncing, setResyncing] = useState(false)
  const [esito, setEsito] = useState<string | null>(null)

  useEffect(() => {
    api
      .listCartelle()
      .then((cs) => setCartelle(cs.map((c) => c.cartella)))
      .catch(() => {})
  }, [])

  const cartellaEffettiva =
    cartella === NUOVO_FALDONE ? nuovoFaldone.trim().toUpperCase() : cartella

  async function handleUpload() {
    if (!file || !cartellaEffettiva) return
    setUploading(true)
    setEsito(null)
    try {
      const res = await api.uploadDocument(file, {
        cartella: cartellaEffettiva,
        descrizione,
        data_documento: dataDocumento,
        validita,
        note,
      })
      const nome = res.documento.nome_file
      if (res.ocr_ok) {
        setEsito(`Documento ${nome} caricato, OCR completato e indicizzato.`)
      } else {
        setEsito(`Documento ${nome} salvato ma OCR non riuscito: ${res.warning}`)
      }
      notifications.show({ message: `Documento ${nome} salvato`, color: 'green' })
      // reset form (mantiene il faldone per upload multipli)
      setFile(null)
      setDescrizione('')
      setDataDocumento('')
      setNote('')
    } catch (err) {
      notifications.show({
        message: err instanceof Error ? err.message : 'Errore durante il caricamento',
        color: 'red',
      })
    } finally {
      setUploading(false)
    }
  }

  async function handleResync() {
    setResyncing(true)
    try {
      const res = await api.resyncExcel()
      const extra =
        res.id_non_corrisposti.length > 0
          ? ` — ATTENZIONE, ID senza corrispondenza: ${res.id_non_corrisposti.join(', ')}`
          : ''
      notifications.show({
        message: `Excel riletto: ${res.documenti_aggiornati} documenti aggiornati${extra}`,
        color: res.id_non_corrisposti.length > 0 ? 'yellow' : 'green',
        autoClose: 8000,
      })
    } catch (err) {
      notifications.show({
        message: err instanceof Error ? err.message : 'Errore nel resync',
        color: 'red',
      })
    } finally {
      setResyncing(false)
    }
  }

  return (
    <AppShell header={{ height: 60 }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="xs">
            <Button
              variant="default"
              leftSection={<IconArrowLeft size={16} />}
              onClick={() => navigate('/')}
            >
              Torna alla lista
            </Button>
            <Title order={5}>Carica nuovo documento</Title>
          </Group>
          <Button
            variant="default"
            leftSection={<IconRefresh size={16} />}
            loading={resyncing}
            onClick={handleResync}
          >
            Risincronizza da Excel
          </Button>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Paper withBorder radius="md" p="xl" maw={640} mx="auto">
          <Stack gap="md">
            <Text size="sm" c="dimmed">
              PDF o TIFF — conversione e OCR automatici via Mistral AI. L'ID documento
              viene assegnato in automatico in base al faldone scelto.
            </Text>

            <FileInput
              label="File (PDF o TIFF)"
              placeholder="Seleziona il file…"
              accept=".pdf,.tif,.tiff"
              leftSection={<IconFileUpload size={16} />}
              value={file}
              onChange={setFile}
              clearable
            />

            <Select
              label="Faldone di appartenenza"
              placeholder="Scegli il faldone"
              data={[
                ...cartelle,
                { value: NUOVO_FALDONE, label: '+ Nuovo faldone' },
              ]}
              value={cartella}
              onChange={setCartella}
            />
            {cartella === NUOVO_FALDONE && (
              <TextInput
                label="Codice nuovo faldone"
                placeholder="es. B08"
                description="Solo lettere, numeri, trattini e underscore (max 20 caratteri)"
                value={nuovoFaldone}
                onChange={(e) => setNuovoFaldone(e.currentTarget.value)}
              />
            )}

            <TextInput
              label="Descrizione"
              placeholder="Contenuto del documento…"
              value={descrizione}
              onChange={(e) => setDescrizione(e.currentTarget.value)}
            />
            <TextInput
              label="Data documento"
              placeholder="gg/mm/aaaa"
              value={dataDocumento}
              onChange={(e) => setDataDocumento(e.currentTarget.value)}
            />
            <Select
              label="Validità"
              data={[
                { value: 'si', label: 'Valido' },
                { value: 'no', label: 'Non valido' },
              ]}
              value={validita}
              onChange={(v) => setValidita(v ?? 'si')}
              allowDeselect={false}
            />
            <Textarea
              label="Note"
              placeholder="Note di archivio…"
              value={note}
              onChange={(e) => setNote(e.currentTarget.value)}
              autosize
              minRows={2}
            />

            <Button
              leftSection={<IconUpload size={16} />}
              loading={uploading}
              disabled={!file || !cartellaEffettiva}
              onClick={handleUpload}
            >
              {uploading ? 'OCR in corso (può richiedere fino a un minuto)…' : 'Carica, esegui OCR e salva'}
            </Button>

            {esito && <Alert color={esito.includes('non riuscito') ? 'yellow' : 'green'}>{esito}</Alert>}
          </Stack>
        </Paper>
      </AppShell.Main>
    </AppShell>
  )
}
