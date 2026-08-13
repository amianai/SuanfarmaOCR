// Stato di autenticazione condiviso: token + ruolo (viewer/admin) + nome utente.

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api, clearAuth, getNome, getRole, getToken, saveAuth } from '../api/client'

interface AuthState {
  token: string
  role: string
  nome: string
}

interface AuthContextValue {
  auth: AuthState | null
  isAdmin: boolean
  /** Il chatbot è attivo lato server? (funzione opzionale, spenta per default) */
  chatEnabled: boolean
  /** L'account Admin non può cambiare la propria password dall'interfaccia. */
  puoCambiarePassword: boolean
  login: (password: string, nome: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState | null>(() => {
    const token = getToken()
    const role = getRole()
    const nome = getNome()
    return token && role && nome ? { token, role, nome } : null
  })

  const [chatEnabled, setChatEnabled] = useState(false)
  const [puoCambiarePassword, setPuoCambiarePassword] = useState(false)

  // Il client API notifica la scadenza sessione (401): sincronizza lo stato.
  useEffect(() => {
    const onExpired = () => setAuth(null)
    window.addEventListener('auth-expired', onExpired)
    return () => window.removeEventListener('auth-expired', onExpired)
  }, [])

  // Flag di funzionalità dal server (dipendono dalla configurazione e dall'utente).
  useEffect(() => {
    if (!auth) {
      setChatEnabled(false)
      setPuoCambiarePassword(false)
      return
    }
    api
      .me()
      .then((m) => {
        setChatEnabled(m.chat_enabled)
        setPuoCambiarePassword(m.puo_cambiare_password)
      })
      .catch(() => {})
  }, [auth])

  const login = useCallback(async (password: string, nome: string) => {
    const res = await api.login(password, nome)
    saveAuth(res.access_token, res.role, res.nome)
    setAuth({ token: res.access_token, role: res.role, nome: res.nome })
  }, [])

  const logout = useCallback(() => {
    clearAuth()
    setAuth(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        auth,
        isAdmin: auth?.role === 'admin',
        chatEnabled,
        puoCambiarePassword,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve essere usato dentro AuthProvider')
  return ctx
}
