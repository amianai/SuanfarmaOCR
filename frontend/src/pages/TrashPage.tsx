import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  AppShell,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertTriangle, IconArrowLeft, IconRestore, IconTrashX } from '@tabler/icons-react'
import { api } from '../api/client'
import type { DocumentoDetail } from '../api/types'

export function TrashPage() {
  const navigate = useNavigate()
  const [docs, setDocs] = useState<DocumentoDetail[] | null>(null)
  const [svuotando, setSvuotando] = useState(false)

  const load = useCallback(() => {
    api.listDeleted().then(setDocs).catch(() => setDocs([]))
  }, [])

  useEffect(load, [load])

  async function restore(doc: DocumentoDetail) {
    await api.restoreDocument(doc.id)
    notifications.show({ message: `${doc.nome_file} ripristinato`, color: 'green' })
    load()
  }

  async function svuota() {
    const quanti = docs?.length ?? 0
    if (
      !window.confirm(
        `Eliminare DEFINITIVAMENTE ${quanti} document${quanti === 1 ? 'o' : 'i'}?\n\n` +
          'Verranno cancellati dal disco i PDF e i testi estratti, insieme a commenti, ' +
          'preferiti e indice di ricerca.\n\nL\'operazione NON è reversibile.',
      )
    )
      return
    setSvuotando(true)
    try {
      const res = await api.svuotaCestino()
      notifications.show({
        message: `Eliminati ${res.documenti_eliminati} documenti e ${res.file_eliminati} file dal disco`,
        color: 'yellow',
      })
      load()
    } catch (err) {
      notifications.show({
        message: err instanceof Error ? err.message : "Errore nello svuotamento",
        color: 'red',
      })
    } finally {
      setSvuotando(false)
    }
  }

  return (
    <AppShell header={{ height: 60 }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md">
          <Button
            variant="default"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate('/')}
          >
            Torna alla lista
          </Button>
          <Title order={5}>Cestino</Title>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        {docs === null ? (
          <Center mih={200}>
            <Loader />
          </Center>
        ) : docs.length === 0 ? (
          <Center mih={200}>
            <Text c="dimmed">Il cestino è vuoto.</Text>
          </Center>
        ) : (
          <Stack gap="sm" maw={800} mx="auto">
            <Group justify="space-between" align="flex-start">
              <Text size="sm" c="dimmed" style={{ flex: 1 }}>
                I documenti eliminati restano archiviati (file inclusi) e possono essere
                ripristinati in qualsiasi momento.
              </Text>
              <Button
                color="red"
                variant="light"
                leftSection={<IconTrashX size={16} />}
                loading={svuotando}
                onClick={svuota}
              >
                Svuota cestino
              </Button>
            </Group>
            <Alert color="red" icon={<IconAlertTriangle size={16} />}>
              Svuotando il cestino i file vengono <strong>cancellati dal disco</strong>:
              l'operazione non è reversibile.
            </Alert>
            {docs.map((doc) => (
              <Card key={doc.id} withBorder radius="md" padding="md">
                <Group justify="space-between">
                  <div>
                    <Group gap="xs" mb={4}>
                      <Badge variant="light" color="indigo">
                        {doc.nome_file}
                      </Badge>
                      {doc.data_documento && (
                        <Badge variant="default">{doc.data_documento}</Badge>
                      )}
                    </Group>
                    <Text fw={600}>{doc.descrizione || doc.nome_file}</Text>
                  </div>
                  <Button
                    variant="default"
                    leftSection={<IconRestore size={16} />}
                    onClick={() => restore(doc)}
                  >
                    Ripristina
                  </Button>
                </Group>
              </Card>
            ))}
          </Stack>
        )}
      </AppShell.Main>
    </AppShell>
  )
}
