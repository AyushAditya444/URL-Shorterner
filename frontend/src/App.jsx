import { Routes, Route, Link as RouterLink } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext.jsx'
import Home from './pages/Home.jsx'
import Dashboard from './pages/Dashboard.jsx'
import LoginButton from './components/LoginButton.jsx'
import RequireAuth from './components/RequireAuth.jsx'

function Placeholder({ label }) {
  return <p>{label}</p>
}

export default function App() {
  return (
    <AuthProvider>
      <nav>
        <RouterLink to="/">Home</RouterLink> | <RouterLink to="/dashboard">My Links</RouterLink>
        <LoginButton />
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/links/:id/analytics"
          element={
            <RequireAuth>
              <Placeholder label="Analytics coming in Task 17" />
            </RequireAuth>
          }
        />
      </Routes>
    </AuthProvider>
  )
}
