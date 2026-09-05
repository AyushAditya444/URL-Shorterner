import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiFetch } from '../api.js'

export default function LinkAnalytics() {
  const { id } = useParams()
  const [data, setData] = useState(null)

  useEffect(() => {
    apiFetch(`/api/links/${id}/analytics`)
      .then((r) => r.json())
      .then(setData)
  }, [id])

  if (!data) return <p>Loading...</p>

  return (
    <div>
      <h1>Analytics</h1>
      <p>Total clicks: {data.total_clicks}</p>

      <h2>Clicks by day</h2>
      <table>
        <tbody>
          {data.clicks_by_day.map((row) => (
            <tr key={row.date}>
              <td>{row.date}</td>
              <td>{row.count}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Top referrers</h2>
      <table>
        <tbody>
          {data.top_referrers.map((row) => (
            <tr key={row.referrer ?? 'direct'}>
              <td>{row.referrer ?? 'Direct'}</td>
              <td>{row.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
