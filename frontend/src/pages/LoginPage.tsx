import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Center,
  Paper,
  PasswordInput,
  Select,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { IconLock } from '@tabler/icons-react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [nomi, setNomi] = useState<string[]>([])
  const [nome, setNome] = useState<string | null>(null)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.listNomi().then(setNomi)
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!nome) {
      setError('Scegli il tuo nome dalla lista')
      return
    }
    setError(null)
    setLoading(true)
    try {
      await login(password, nome)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore di autenticazione')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Center mih="100vh">
      <Paper withBorder radius="lg" p="xl" w={380}>
        <form onSubmit={handleSubmit}>
          <Stack gap="md">
            <Stack gap={4} align="center">
              <IconLock size={28} />
              <Title order={2}>Archivio OCR</Title>
              <Text size="sm" c="dimmed">
                Suanfarma — Rovereto
              </Text>
            </Stack>
            <Select
              placeholder="Chi sei?"
              data={nomi}
              value={nome}
              onChange={setNome}
              searchable
              nothingFoundMessage="Nome non in lista: chiedi all'amministratore"
            />
            <PasswordInput
              placeholder="Password di accesso"
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              required
            />
            {error && (
              <Text size="sm" c="red">
                {error}
              </Text>
            )}
            <Button type="submit" loading={loading} fullWidth>
              Accedi
            </Button>
          </Stack>
        </form>
      </Paper>
    </Center>
  )
}
