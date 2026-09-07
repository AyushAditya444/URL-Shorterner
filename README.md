# URL Shortener

A full-stack URL shortener with rate limiting, Redis caching, Google OAuth login, custom aliases, link expiry, and click analytics.

**Live app:** https://urlshortener-neon-six.vercel.app
**API:** https://url-shorterner-ui9m.onrender.com

## Features

- Shorten any URL into a 7-character code, or pick a custom alias
- Anonymous shortening allowed; sign in with Google to manage your links
- Per-link click analytics: total clicks, clicks by day, top referrers
- Optional link expiry
- Redis cache-aside layer in front of Postgres for redirect lookups
- Fixed-window rate limiting (Redis `INCR`/`EXPIRE`): 10 req/min for link creation, 60 req/min for redirects, per IP

## Tech stack

**Backend:** Python, FastAPI, SQLAlchemy 2.0 + Alembic, PyJWT, Authlib (Google OAuth), redis-py, pytest + httpx + fakeredis
**Frontend:** React 18 + Vite, React Router, Vitest + React Testing Library
**Data:** Postgres (Supabase), Redis (Upstash)
**Hosting:** Render (backend, free web service), Vercel (frontend, free static hosting)

## Running locally

Requires Docker Desktop.

```bash
cp .env.example .env
docker-compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Backend tests: `cd backend && pip install -r requirements.txt && pytest`
- Frontend tests: `cd frontend && npm install && npm test`

## Design & implementation notes

Full design spec and task-by-task implementation plan: [`docs/superpowers/`](docs/superpowers/).
