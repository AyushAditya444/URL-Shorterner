import { Link as RouterLink } from 'react-router-dom'

export default function LinkList({ links, onDelete }) {
  return (
    <ul>
      {links.map((link) => (
        <li key={link.id}>
          <a href={link.short_url}>{link.short_url}</a> → <span>{link.target_url}</span>{' '}
          <RouterLink to={`/links/${link.id}/analytics`}>Analytics</RouterLink>{' '}
          <button onClick={() => onDelete(link.id)}>Delete</button>
        </li>
      ))}
    </ul>
  )
}
