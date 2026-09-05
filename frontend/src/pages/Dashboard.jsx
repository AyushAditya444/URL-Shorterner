import { useEffect, useState } from 'react'
import { apiFetch } from '../api.js'
import LinkList from '../components/LinkList.jsx'

export default function Dashboard() {
  const [links, setLinks] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch('/api/links')
      .then((r) => r.json())
      .then((data) => {
        setLinks(data)
        setLoading(false)
      })
  }, [])

  async function handleDelete(id) {
    await apiFetch(`/api/links/${id}`, { method: 'DELETE' })
    setLinks((current) => current.filter((link) => link.id !== id))
  }

  if (loading) return <p>Loading...</p>

  return (
    <div>
      <h1>My Links</h1>
      <LinkList links={links} onDelete={handleDelete} />
    </div>
  )
}
