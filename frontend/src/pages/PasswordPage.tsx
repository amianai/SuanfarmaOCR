import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AppShell,
  Button,
  Group,
  Paper,
  PasswordInput,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconArrowLeft, IconKey } from '@tabler/icons-react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function PasswordPage() {
  const navigate = useNavigate()
  const { auth } = useAuth()
  const [attuale, setAttuale] = useState('')
  const [nuova, setNuova] = useState('')
  const [conferma, setConferma] = useState('')
  const [salvando, setSalvando] = useState(false)

  const nonCombaciano = conferma.length > 0 && nuova !== conferma
  const valido = attuale.length > 0 && nuova.length >= 8 && nuova === conferma

  async function salva() {
    setSalvando(true)
    try {
      await api.cambiaPassword(attuale, nuova)
      notifications.show({ message: 'Password aggiornata', color: 'green' })
      navigate('/')
    } catch (err) {
      notifications.show({
        message: err instanceof Error ? err.message : 'Errore nel cambio password',
        color: 'red',
      })
    } finally {
      setSalvando(false)
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
          <Title order={5}>Cambia password</Title>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Paper withBorder radius="md" p="xl" maw={460} mx="auto">
          <Stack gap="md">
            <Text size="sm" c="dimmed">
              Stai cambiando la password dell'utente <strong>{auth?.nome}</strong>.
            </Text>
            <PasswordInput
              label="Password attuale"
              value={attuale}
              onChange={(e) => setAttuale(e.currentTarget.value)}
              required
            />
            <PasswordInput
              label="Nuova password"
              description="Almeno 8 caratteri"
              value={nuova}
              onChange={(e) => setNuova(e.currentTarget.value)}
              required
            />
            <PasswordInput
              label="Conferma nuova password"
              value={conferma}
              onChange={(e) => setConferma(e.currentTarget.value)}
              error={nonCombaciano ? 'Le due password non combaciano' : undefined}
              required
            />
            <Button
              leftSection={<IconKey size={16} />}
              loading={salvando}
              disabled={!valido}
              onClick={salva}
            >
              Aggiorna password
            </Button>
          </Stack>
        </Paper>
      </AppShell.Main>
    </AppShell>
  )
}
