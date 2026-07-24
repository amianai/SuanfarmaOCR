import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
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
import { IconArrowLeft, IconRestore } from '@tabler/icons-react'
import { api } from '../api/client'
import type { DocumentoDetail } from '../api/types'

export function TrashPage() {
  const navigate = useNavigate()
  const [docs, setDocs] = useState<DocumentoDetail[] | null>(null)

  const load = useCallback(() => {
    api.listDeleted().then(setDocs).catch(() => setDocs([]))
  }, [])

  useEffect(load, [load])

  async function restore(doc: DocumentoDetail) {
    await api.restoreDocument(doc.id)
    notifications.show({ message: `${doc.nome_file} ripristinato`, color: 'green' })
    load()
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
            <Text size="sm" c="dimmed">
              I documenti eliminati restano archiviati (file inclusi) e possono essere
              ripristinati in qualsiasi momento.
            </Text>
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
