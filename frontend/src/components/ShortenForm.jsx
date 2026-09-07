import { useState } from 'react'
import { apiFetch } from '../api.js'

export default function ShortenForm() {
  const [url, setUrl] = useState('')
  const [customAlias, setCustomAlias] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      const response = await apiFetch('/api/links', {
        method: 'POST',
        body: JSON.stringify({ url, custom_alias: customAlias || undefined }),
      })
      if (!response.ok) {
        setError('Something went wrong shortening that URL.')
        return
      }
      setResult(await response.json())
    } catch {
      // The fetch itself failed (no response at all) — most likely the
      // backend's free-tier instance is waking up from a cold start.
      setError('The server is waking up (this can take up to a minute on the free tier) — please try again shortly.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="url-input">URL to shorten</label>
      <input id="url-input" value={url} onChange={(e) => setUrl(e.target.value)} required />

      <label htmlFor="alias-input">Custom alias (optional)</label>
      <input id="alias-input" value={customAlias} onChange={(e) => setCustomAlias(e.target.value)} />

      <button type="submit" disabled={loading}>{loading ? 'Shortening…' : 'Shorten'}</button>

      {error && <p role="alert">{error}</p>}
      {result && <p>{result.short_url}</p>}
    </form>
  )
}
