import { useState } from 'react'
import { apiFetch } from '../api.js'

export default function ShortenForm() {
  const [url, setUrl] = useState('')
  const [customAlias, setCustomAlias] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setResult(null)
    const response = await apiFetch('/api/links', {
      method: 'POST',
      body: JSON.stringify({ url, custom_alias: customAlias || undefined }),
    })
    if (!response.ok) {
      setError('Something went wrong shortening that URL.')
      return
    }
    setResult(await response.json())
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="url-input">URL to shorten</label>
      <input id="url-input" value={url} onChange={(e) => setUrl(e.target.value)} required />

      <label htmlFor="alias-input">Custom alias (optional)</label>
      <input id="alias-input" value={customAlias} onChange={(e) => setCustomAlias(e.target.value)} />

      <button type="submit">Shorten</button>

      {error && <p role="alert">{error}</p>}
      {result && <p>{result.short_url}</p>}
    </form>
  )
}
