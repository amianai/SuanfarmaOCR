import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ActionIcon,
  AppShell,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Paper,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconArrowLeft, IconTrash, IconUserPlus } from '@tabler/icons-react'
import { api } from '../api/client'
import type { UtenteAdmin } from '../api/types'

export function UsersPage() {
  const navigate = useNavigate()
  const [utenti, setUtenti] = useState<UtenteAdmin[] | null>(null)
  const [nuovoNome, setNuovoNome] = useState('')
  const [adding, setAdding] = useState(false)

  const load = useCallback(() => {
    api.listUtenti().then(setUtenti).catch(() => setUtenti([]))
  }, [])

  useEffect(load, [load])

  async function aggiungi() {
    const nome = nuovoNome.trim()
    if (!nome) return
    setAdding(true)
    try {
      await api.addUtente(nome)
      setNuovoNome('')
      notifications.show({ message: `${nome} aggiunto alla lista`, color: 'green' })
      load()
    } catch (err) {
      notifications.show({
        message: err instanceof Error ? err.message : "Errore nell'aggiunta",
        color: 'red',
      })
    } finally {
      setAdding(false)
    }
  }

  async function toggleAttivo(u: UtenteAdmin) {
    try {
      await api.setUtenteAttivo(u.id, u.attivo === 0)
    } catch (err) {
      notifications.show({
        message: err instanceof Error ? err.message : 'Operazione non consentita',
        color: 'red',
      })
    }
    load()
  }

  async function elimina(u: UtenteAdmin) {
    if (
      !window.confirm(
        `Eliminare definitivamente il profilo "${u.nome}"?\n` +
          'I suoi preferiti verranno rimossi; commenti e storico restano firmati col suo nome.',
      )
    )
      return
    try {
      await api.deleteUtente(u.id)
      notifications.show({ message: `Profilo ${u.nome} eliminato`, color: 'yellow' })
    } catch (err) {
      notifications.show({
        message: err instanceof Error ? err.message : "Errore nell'eliminazione",
        color: 'red',
      })
    }
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
          <Title order={5}>Gestione utenti</Title>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Stack gap="md" maw={560} mx="auto">
          <Text size="sm" c="dimmed">
            I nomi in questa lista sono selezionabili al login. Disattivare un nome
            impedisce nuovi accessi con quel nome; i suoi preferiti e commenti restano.
          </Text>

          <Paper withBorder radius="md" p="md">
            <Group gap="xs" align="flex-end">
              <TextInput
                label="Nuovo nome"
                placeholder="es. Marco"
                style={{ flex: 1 }}
                value={nuovoNome}
                onChange={(e) => setNuovoNome(e.currentTarget.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    aggiungi()
                  }
                }}
              />
              <Button
                leftSection={<IconUserPlus size={16} />}
                loading={adding}
                disabled={!nuovoNome.trim()}
                onClick={aggiungi}
              >
                Aggiungi
              </Button>
            </Group>
          </Paper>

          {utenti === null ? (
            <Center mih={120}>
              <Loader />
            </Center>
          ) : (
            <Stack gap="xs">
              {utenti.map((u) => (
                <Paper key={u.id} withBorder radius="md" p="sm">
                  <Group justify="space-between">
                    <Group gap="xs">
                      <Text fw={600}>{u.nome}</Text>
                      {u.attivo === 0 && (
                        <Badge variant="light" color="gray">
                          Disattivato
                        </Badge>
                      )}
                    </Group>
                    <Group gap="sm">
                      <Switch
                        checked={u.attivo === 1}
                        onChange={() => toggleAttivo(u)}
                        label={u.attivo === 1 ? 'Attivo' : 'Inattivo'}
                        labelPosition="left"
                      />
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        aria-label={`Elimina ${u.nome}`}
                        onClick={() => elimina(u)}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Group>
                </Paper>
              ))}
            </Stack>
          )}
        </Stack>
      </AppShell.Main>
    </AppShell>
  )
}
