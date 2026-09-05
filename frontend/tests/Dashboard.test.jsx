import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Dashboard from '../src/pages/Dashboard.jsx'

const links = [
  { id: 1, code: 'abc1234', short_url: 'http://x/abc1234', target_url: 'https://example.com/1' },
  { id: 2, code: 'def5678', short_url: 'http://x/def5678', target_url: 'https://example.com/2' },
]

describe('Dashboard', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockImplementation((url, options) => {
      if (options?.method === 'DELETE') {
        return Promise.resolve({ ok: true })
      }
      return Promise.resolve({ ok: true, json: async () => links })
    })
  })

  it('lists the user\'s links', async () => {
    render(<Dashboard />, { wrapper: MemoryRouter })
    await waitFor(() => expect(screen.getByText('https://example.com/1')).toBeInTheDocument())
    expect(screen.getByText('https://example.com/2')).toBeInTheDocument()
  })

  it('removes a link from the list after deleting it', async () => {
    render(<Dashboard />, { wrapper: MemoryRouter })
    await waitFor(() => expect(screen.getByText('https://example.com/1')).toBeInTheDocument())

    fireEvent.click(screen.getAllByRole('button', { name: /delete/i })[0])

    await waitFor(() => expect(screen.queryByText('https://example.com/1')).not.toBeInTheDocument())
    expect(screen.getByText('https://example.com/2')).toBeInTheDocument()
  })
})
