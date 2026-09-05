import { useAuth } from '../context/AuthContext.jsx'
import LoginButton from './LoginButton.jsx'

export default function RequireAuth({ children }) {
  const { user, loading } = useAuth()

  if (loading) return null
  if (!user) {
    return (
      <div>
        <p>Sign in to view this page.</p>
        <LoginButton />
      </div>
    )
  }
  return children
}
