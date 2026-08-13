import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ActionIcon,
  Alert,
  AppShell,
  Badge,
  Button,
  Center,
  CopyButton,
  Group,
  Loader,
  Paper,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconArrowLeft,
  IconCheck,
  IconCopy,
  IconDice5,
  IconKey,
  IconLock,
  IconTrash,
  IconUserPlus,
} from '@tabler/icons-react'
import { api } from '../api/client'
import type { UtenteAdmin } from '../api/types'

export function UsersPage() {
  const navigate = useNavigate()
  const [utenti, setUtenti] = useState<UtenteAdmin[] | null>(null)
  const [nuovoNome, setNuovoNome] = useState('')
  const [nuovaPassword, setNuovaPassword] = useState('')
  const [adding, setAdding] = useState(false)
  // Password appena creata/reimpostata: visibile una sola volta, da comunicare.
  const [credenziali, setCredenziali] = useState<{ nome: string; password: string } | null>(null)

  const load = useCallback(() => {
    api.listUtenti().then(setUtenti).catch(() => setUtenti([]))
  }, [])

  useEffect(load, [load])

  async function generaPassword() {
    try {
      setNuovaPassword(await api.generaPassword())
    } catch {
      notifications.show({ message: 'Impossibile generare la password', color: 'red' })
    }
  }

  async function aggiungi() {
    const nome = nuovoNome.trim()
    if (!nome || nuovaPassword.length < 8) return
    setAdding(true)
    try {
      const res = await api.addUtente(nome, nuovaPassword)
      setCredenziali({ nome: res.utente.nome, password: res.password })
      setNuovoNome('')
      setNuovaPassword('')
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

  async function aggiorna(u: UtenteAdmin, campi: Parameters<typeof api.updateUtente>[1]) {
    try {
      await api.updateUtente(u.id, campi)
    } catch (err) {
      notifications.show({
        message: err instanceof Error ? err.message : 'Operazione non consentita',
        color: 'red',
      })
    }
    load()
  }

  async function reimpostaPassword(u: UtenteAdmin) {
    try {
      const password = await api.generaPassword()
      await api.updateUtente(u.id, { password })
      setCredenziali({ nome: u.nome, password })
      load()
    } catch (err) {
      notifications.show({
        message: err instanceof Error ? err.message : 'Reset non consentito',
        color: 'red',
      })
    }
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
        <Stack gap="md" maw={620} mx="auto">
          <Text size="sm" c="dimmed">
            Ogni utente accede con la propria password. Gli amministratori possono
            caricare e modificare documenti; gli altri solo consultare.
          </Text>

          {credenziali && (
            <Alert
              color="green"
              title={`Password di ${credenziali.nome}`}
              withCloseButton
              onClose={() => setCredenziali(null)}
            >
              <Group gap="xs">
                <Text ff="monospace" fw={600}>
                  {credenziali.password}
                </Text>
                <CopyButton value={credenziali.password}>
                  {({ copied, copy }) => (
                    <Tooltip label={copied ? 'Copiata' : 'Copia'}>
                      <ActionIcon variant="subtle" onClick={copy}>
                        {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                      </ActionIcon>
                    </Tooltip>
                  )}
                </CopyButton>
              </Group>
              <Text size="xs" mt={4}>
                Comunicala all'utente adesso: non sarà più visibile. Potrà cambiarla
                dopo il primo accesso.
              </Text>
            </Alert>
          )}

          <Paper withBorder radius="md" p="md">
            <Stack gap="sm">
              <TextInput
                label="Nuovo utente"
                placeholder="es. Marco"
                value={nuovoNome}
                onChange={(e) => setNuovoNome(e.currentTarget.value)}
              />
              <TextInput
                label="Password iniziale"
                description="Almeno 8 caratteri, oppure generane una col dado"
                placeholder="password"
                value={nuovaPassword}
                onChange={(e) => setNuovaPassword(e.currentTarget.value)}
                rightSection={
                  <Tooltip label="Genera password casuale">
                    <ActionIcon variant="subtle" aria-label="Genera password" onClick={generaPassword}>
                      <IconDice5 size={18} />
                    </ActionIcon>
                  </Tooltip>
                }
              />
              <Group justify="flex-end">
                <Button
                  leftSection={<IconUserPlus size={16} />}
                  loading={adding}
                  disabled={!nuovoNome.trim() || nuovaPassword.length < 8}
                  onClick={aggiungi}
                >
                  Aggiungi utente
                </Button>
              </Group>
            </Stack>
          </Paper>

          {utenti === null ? (
            <Center mih={120}>
              <Loader />
            </Center>
          ) : (
            <Stack gap="xs">
              {utenti.map((u) => (
                <Paper key={u.id} withBorder radius="md" p="sm">
                  <Group justify="space-between" wrap="nowrap">
                    <Group gap="xs">
                      <Text fw={600}>{u.nome}</Text>
                      {u.amministratore === 1 && (
                        <Badge variant="light" color="red">
                          Amministratore
                        </Badge>
                      )}
                      {u.protetto && (
                        <Tooltip label="Account di servizio: non modificabile, garantisce l'accesso">
                          <Badge variant="light" color="gray" leftSection={<IconLock size={10} />}>
                            Protetto
                          </Badge>
                        </Tooltip>
                      )}
                      {u.attivo === 0 && (
                        <Badge variant="light" color="gray">
                          Disattivato
                        </Badge>
                      )}
                      {!u.ha_password && (
                        <Badge variant="light" color="orange">
                          Senza password
                        </Badge>
                      )}
                    </Group>

                    <Group gap="sm" wrap="nowrap">
                      <Switch
                        checked={u.amministratore === 1}
                        disabled={u.protetto}
                        onChange={(e) =>
                          aggiorna(u, { amministratore: e.currentTarget.checked })
                        }
                        label="Admin"
                        labelPosition="left"
                      />
                      <Switch
                        checked={u.attivo === 1}
                        disabled={u.protetto}
                        onChange={(e) => aggiorna(u, { attivo: e.currentTarget.checked })}
                        label="Attivo"
                        labelPosition="left"
                      />
                      <Tooltip
                        label={
                          u.protetto
                            ? 'Usa `python -m app.reset_admin` sul server'
                            : 'Genera una nuova password'
                        }
                      >
                        <ActionIcon
                          variant="subtle"
                          aria-label={`Reimposta password di ${u.nome}`}
                          disabled={u.protetto}
                          onClick={() => reimpostaPassword(u)}
                        >
                          <IconKey size={16} />
                        </ActionIcon>
                      </Tooltip>
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        aria-label={`Elimina ${u.nome}`}
                        disabled={u.protetto}
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
