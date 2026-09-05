import { Routes, Route, Link as RouterLink } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext.jsx'
import Home from './pages/Home.jsx'

function Placeholder({ label }) {
  return <p>{label}</p>
}

export default function App() {
  return (
    <AuthProvider>
      <nav>
        <RouterLink to="/">Home</RouterLink>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/dashboard" element={<Placeholder label="Dashboard coming in Task 16" />} />
        <Route path="/links/:id/analytics" element={<Placeholder label="Analytics coming in Task 17" />} />
      </Routes>
    </AuthProvider>
  )
}
