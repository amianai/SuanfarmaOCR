import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import { ChatPage } from './pages/ChatPage'
import { DetailPage } from './pages/DetailPage'
import { ListPage } from './pages/ListPage'
import { LoginPage } from './pages/LoginPage'
import { TrashPage } from './pages/TrashPage'
import { UploadPage } from './pages/UploadPage'
import { UsersPage } from './pages/UsersPage'

function RequireAuth() {
  const { auth } = useAuth()
  return auth ? <Outlet /> : <Navigate to="/login" replace />
}

function RequireAdmin() {
  const { auth, isAdmin } = useAuth()
  if (!auth) return <Navigate to="/login" replace />
  return isAdmin ? <Outlet /> : <Navigate to="/" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/" element={<ListPage />} />
          <Route path="/doc/:id" element={<DetailPage />} />
          <Route path="/chat" element={<ChatPage />} />
        </Route>
        <Route element={<RequireAdmin />}>
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/trash" element={<TrashPage />} />
          <Route path="/utenti" element={<UsersPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
