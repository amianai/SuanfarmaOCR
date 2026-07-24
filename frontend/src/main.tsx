import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'
import './index.css'
import App from './App.tsx'
import { AuthProvider } from './auth/AuthContext'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider defaultColorScheme="dark" theme={{ primaryColor: 'indigo' }}>
      <Notifications position="top-right" />
      <AuthProvider>
        <App />
      </AuthProvider>
    </MantineProvider>
  </StrictMode>,
)
