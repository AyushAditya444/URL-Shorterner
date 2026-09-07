import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ShortenForm from '../src/components/ShortenForm.jsx'

describe('ShortenForm', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ code: 'abc1234', short_url: 'http://localhost:8000/abc1234', target_url: 'https://example.com' }),
    })
  })

  it('submits the url and shows the short link', async () => {
    render(<ShortenForm />)
    fireEvent.change(screen.getByLabelText(/url to shorten/i), { target: { value: 'https://example.com' } })
    fireEvent.click(screen.getByRole('button', { name: /shorten/i }))

    await waitFor(() => {
      expect(screen.getByText('http://localhost:8000/abc1234')).toBeInTheDocument()
    })
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/links'),
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('shows an error message when the API call fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, json: async () => ({ error: 'Invalid URL' }) })
    render(<ShortenForm />)
    fireEvent.change(screen.getByLabelText(/url to shorten/i), { target: { value: 'https://example.com' } })
    fireEvent.click(screen.getByRole('button', { name: /shorten/i }))

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    })
  })

  it('shows a waking-up message when the request fails at the network level', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    render(<ShortenForm />)
    fireEvent.change(screen.getByLabelText(/url to shorten/i), { target: { value: 'https://example.com' } })
    fireEvent.click(screen.getByRole('button', { name: /shorten/i }))

    await waitFor(() => {
      expect(screen.getByText(/waking up/i)).toBeInTheDocument()
    })
  })

  it('disables the submit button and shows a loading state while the request is in flight', async () => {
    let resolveFetch
    global.fetch = vi.fn().mockReturnValue(new Promise((resolve) => { resolveFetch = resolve }))
    render(<ShortenForm />)
    fireEvent.change(screen.getByLabelText(/url to shorten/i), { target: { value: 'https://example.com' } })
    fireEvent.click(screen.getByRole('button', { name: /shorten/i }))

    expect(screen.getByRole('button', { name: /shortening/i })).toBeDisabled()

    resolveFetch({ ok: true, json: async () => ({ short_url: 'http://x/abc1234' }) })
    await waitFor(() => {
      expect(screen.getByText('http://x/abc1234')).toBeInTheDocument()
    })
  })
})
