# URL Shortener with Rate Limiting & Caching — Design

Date: 2026-09-05
Status: Approved for planning

## 1. Purpose

Build the "URL Shortener with Rate Limiting & Caching" project listed on Ayush Aditya's resume as a real, deployed web application — not just a script. This is the second of three resume projects being built out (after the Phishing E-Mail Detector).

Resume bullets this project must substantiate:
- "Developed a URL shortening service with REST APIs for URL creation and redirection."
- "Implemented rate limiting and Redis caching to improve API performance and prevent abuse."

## 2. Scope

In scope:
- Shorten a long URL to a short code and redirect on visit.
- Custom short codes (user-chosen alias, optional).
- Link expiration (optional expiry date/time).
- Click analytics per link (count, timestamp, referrer, user agent).
- Google OAuth login; logged-in users see a dashboard of the links they created. Anonymous users can still shorten URLs (frictionless, bit.ly-style), but those links aren't attached to an account.
- Per-IP rate limiting on link creation and redirection, backed by Redis.
- Cache-aside caching of code → target-URL lookups in Redis, to keep redirects fast and reduce Postgres load.
- Fully Dockerized locally (docker-compose: Postgres, Redis, backend, frontend) and deployed live (Render) with a public demo link.

Out of scope (YAGNI for a resume-demo project):
- Refresh tokens / token revocation lists — a single reasonably-lived JWT is enough.
- A background job queue (Celery/RQ) — click logging uses FastAPI `BackgroundTasks` instead of a separate worker.
- Multi-region / horizontal scaling concerns, load testing, or SLAs.
- Editing an existing link's target URL after creation (delete + recreate instead).

## 3. Architecture

Monorepo layout:

```
/
├── backend/           # FastAPI app
├── frontend/          # React (Vite) app
├── docker-compose.yml # postgres, redis, backend, frontend — local dev
└── docs/superpowers/  # this spec + implementation plan
```

Local dev: `docker-compose up` runs all four services — Dockerized Postgres and Dockerized Redis (per the resume's tech stack) plus the backend and frontend containers.

Production (Render): the backend and frontend deploy as two separate Render web services (each from its own Dockerfile). Postgres and Redis use Render's managed add-ons rather than self-hosted containers, since Render doesn't persist container disk well and managed instances are one click — the app talks to them through the same `DATABASE_URL` / `REDIS_URL` env vars either way, so no code differs between local and prod.

## 4. Backend components (FastAPI)

**Auth** — Google OAuth via Authlib. `/api/auth/google/login` redirects to Google; `/api/auth/google/callback` exchanges the code, upserts a `users` row (email, name, google_sub), and issues a JWT (7-day expiry) set as an httpOnly cookie. httpOnly avoids exposing the token to frontend JS (XSS-safer than localStorage) and needs no manual header wiring on the frontend.

**Links** —
- `POST /api/links` — body: `{ url, custom_alias?, expires_at? }`. Validates the URL, generates or validates the code, inserts into Postgres, primes the Redis cache, returns the short URL. Attaches `owner_id` if the request has a valid auth cookie, else leaves it null.
- `GET /api/links` — the current user's links (requires auth).
- `DELETE /api/links/{id}` — requires auth + ownership; also evicts the Redis cache entry.
- `GET /api/links/{id}/analytics` — requires auth + ownership; aggregate click counts (totals, per-day counts, top referrers) via SQL.
- `GET /{code}` — public redirect endpoint (mounted outside `/api` since it's meant to be the short link itself). Cache-aside lookup, 302 redirect, logs a click via `BackgroundTasks`, 404 if unknown/expired.

**Short code generation** — random 7-character base62 string; insert with a unique constraint on `links.code` and retry (small bounded number of attempts) on the rare collision. A custom alias goes through the same uniqueness check, just skipping the random-generation step; a taken alias returns 400.

**Rate limiting** — Redis-backed fixed-window counter: key `ratelimit:{ip}:{bucket}`, `INCR` + `EXPIRE` on first increment in the window. Two buckets: link creation (e.g. 10/min) and redirects (e.g. 60/min) — tighter on the write path since that's the one meant to prevent abuse. Exceeding the limit returns 429 with a `Retry-After` header.

**Caching** — cache-aside on the redirect path: check `short:{code}` in Redis first; on miss, query Postgres, then populate the cache with a TTL (e.g. 1 hour). Deleting or expiring a link evicts its cache entry so stale redirects can't happen.

**Click analytics** — on every successful redirect, a `BackgroundTask` inserts a row into `clicks` (link_id, clicked_at, referrer, user_agent) after the redirect response has already been sent, so logging never adds latency to the redirect itself.

## 5. Data model (Postgres)

- `users(id, email UNIQUE, name, google_sub UNIQUE, created_at)`
- `links(id, code UNIQUE, target_url, owner_id NULLABLE FK→users, is_custom_alias BOOL, expires_at NULLABLE, created_at)`
- `clicks(id, link_id FK→links, clicked_at, referrer NULLABLE, user_agent NULLABLE)`

## 6. Frontend (React + Vite)

- **Home** (`/`) — a form to paste a URL with optional custom alias and expiry date, returns the shortened link. Works whether or not the visitor is logged in.
- **Login** — a "Sign in with Google" button that hits the backend's OAuth redirect flow.
- **Dashboard** (`/dashboard`, protected) — lists the logged-in user's links: code, target, click count, created/expiry dates, and a delete action.
- **Analytics** (`/links/:id/analytics`, protected) — per-link click count over time and top referrers, pulled from the analytics endpoint.

The actual `/{code}` redirect is served by FastAPI directly, not by React routing — visiting a short link never touches the SPA.

## 7. Data flow

**Create**: client → `POST /api/links` → rate-limit check (Redis) → validate URL → generate/validate code → insert row (Postgres) → prime cache (Redis) → return short URL.

**Redirect**: client → `GET /{code}` → rate-limit check (Redis) → `GET short:{code}` from Redis → hit: 302 + background click log; miss: query Postgres → 404 if missing/expired, else 302 + populate cache + background click log.

## 8. Error handling

- 404 — unknown or expired short code.
- 429 — rate limit exceeded, with `Retry-After`.
- 400 — invalid URL, or alias already taken.
- 401/403 — dashboard/analytics/delete routes without a valid session.
- A global exception handler returns a consistent `{ "error": "..." }` JSON shape for uncaught errors.

## 9. Testing

- Backend: pytest + httpx. Unit tests for short-code generation/collision handling and the rate limiter (using `fakeredis`); integration tests for the create → redirect → analytics flow against a test Postgres instance (via the docker-compose test profile).
- Frontend: React Testing Library for the shorten form and the dashboard list/delete flow. No full e2e suite — out of scope for a demo project.

## 10. Deployment

- Local: `docker-compose up` — Dockerized Postgres, Dockerized Redis, backend, frontend, matching the resume's stated stack.
- Production: Render web services for backend and frontend (each with its own Dockerfile), Render managed Postgres and managed Redis-compatible store. Google OAuth's redirect URI is configured to the deployed backend URL; CORS on the backend allows the deployed frontend's origin.
