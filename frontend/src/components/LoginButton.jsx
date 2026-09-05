import { useAuth } from '../context/AuthContext.jsx'
import { googleLoginUrl } from '../api.js'

export default function LoginButton() {
  const { user, loading, logout } = useAuth()

  if (loading) return null

  if (user) {
    return (
      <span>
        {user.name} · <button onClick={logout}>Log out</button>
      </span>
    )
  }

  return <a href={googleLoginUrl()}>Sign in with Google</a>
}
