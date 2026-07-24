import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ActionIcon,
  AppShell,
  Badge,
  Button,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core'
import { IconArrowLeft, IconSend, IconSparkles } from '@tabler/icons-react'
import { api } from '../api/client'
import type { FonteRag } from '../api/types'

interface Messaggio {
  ruolo: 'utente' | 'assistente'
  testo: string
  fonti?: FonteRag[]
}

export function ChatPage() {
  const navigate = useNavigate()
  const [messaggi, setMessaggi] = useState<Messaggio[]>([])
  const [domanda, setDomanda] = useState('')
  const [loading, setLoading] = useState(false)
  const fine = useRef<HTMLDivElement>(null)

  async function invia() {
    const testo = domanda.trim()
    if (!testo || loading) return
    setMessaggi((m) => [...m, { ruolo: 'utente', testo }])
    setDomanda('')
    setLoading(true)
    setTimeout(() => fine.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    try {
      const res = await api.chat(testo)
      setMessaggi((m) => [...m, { ruolo: 'assistente', testo: res.risposta, fonti: res.fonti }])
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Errore'
      setMessaggi((m) => [
        ...m,
        { ruolo: 'assistente', testo: `Non è stato possibile rispondere. ${msg}` },
      ])
    } finally {
      setLoading(false)
      setTimeout(() => fine.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  return (
    <AppShell header={{ height: 60 }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" gap="xs">
          <Button
            variant="default"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate('/')}
          >
            Torna alla lista
          </Button>
          <Group gap={6}>
            <IconSparkles size={18} />
            <Title order={5}>Chiedi all'archivio</Title>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Stack gap="md" maw={760} mx="auto">
          {messaggi.length === 0 && (
            <Paper withBorder radius="md" p="lg">
              <Text fw={600} mb={4}>
                Fai una domanda in linguaggio naturale sui documenti dell'archivio.
              </Text>
              <Text size="sm" c="dimmed">
                Esempi: «In quali documenti si parla di mensa aziendale?» · «Cosa dicono gli
                accordi sul premio di produzione?». Le risposte si basano solo sui documenti e
                citano le fonti; se l'informazione non c'è, te lo dice.
              </Text>
            </Paper>
          )}

          {messaggi.map((m, i) => (
            <Paper
              key={i}
              withBorder
              radius="md"
              p="md"
              style={{ alignSelf: m.ruolo === 'utente' ? 'flex-end' : 'stretch', maxWidth: '92%' }}
            >
              <Text size="xs" c="dimmed" mb={4}>
                {m.ruolo === 'utente' ? 'Tu' : 'Assistente'}
              </Text>
              <Text style={{ whiteSpace: 'pre-wrap' }}>{m.testo}</Text>
              {m.fonti && m.fonti.length > 0 && (
                <Group gap={6} mt="sm">
                  <Text size="xs" c="dimmed">
                    Fonti:
                  </Text>
                  {m.fonti.map((f) => (
                    <Badge
                      key={f.doc_id}
                      variant="light"
                      color="indigo"
                      style={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/doc/${f.doc_id}`)}
                    >
                      {f.nome_file}
                    </Badge>
                  ))}
                </Group>
              )}
            </Paper>
          ))}

          {loading && (
            <Group gap="xs" c="dimmed">
              <Loader size="sm" />
              <Text size="sm">Sto cercando nei documenti… (con un modello locale può volerci qualche minuto)</Text>
            </Group>
          )}
          <div ref={fine} />

          <Paper
            withBorder
            radius="md"
            p="sm"
            style={{ position: 'sticky', bottom: 0 }}
          >
            <Group gap="xs" align="flex-end">
              <Textarea
                placeholder="Scrivi la tua domanda…"
                autosize
                minRows={1}
                maxRows={5}
                style={{ flex: 1 }}
                value={domanda}
                onChange={(e) => setDomanda(e.currentTarget.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    invia()
                  }
                }}
              />
              <ActionIcon
                size="lg"
                aria-label="Invia domanda"
                loading={loading}
                disabled={!domanda.trim()}
                onClick={invia}
              >
                <IconSend size={16} />
              </ActionIcon>
            </Group>
          </Paper>
        </Stack>
      </AppShell.Main>
    </AppShell>
  )
}
