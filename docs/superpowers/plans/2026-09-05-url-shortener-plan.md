# URL Shortener with Rate Limiting & Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a working URL shortener web app (React + FastAPI + Postgres + Redis) that substantiates the resume bullets on rate limiting and Redis caching, with Google login, custom aliases, expiry, and click analytics.

**Architecture:** FastAPI backend exposes REST endpoints for link CRUD, a public redirect endpoint, and Google OAuth; Postgres holds users/links/clicks, Redis backs both a cache-aside layer for redirect lookups and a fixed-window rate limiter. React (Vite) frontend consumes the API. Docker Compose runs all four services locally; Render hosts the deployed version.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 + Alembic, PyJWT, Authlib (Google OAuth), redis-py, pytest + httpx + fakeredis; React 18 + Vite, React Router, Vitest + React Testing Library; Postgres 15, Redis 7; Docker Compose; Render (deployment).

**Spec:** `docs/superpowers/specs/2026-09-05-url-shortener-design.md`

## Global Constraints

- Short codes: 7-character base62 strings (`[0-9A-Za-z]`), unique in `links.code`.
- Rate limits: 10 requests/min per IP on link creation, 60 requests/min per IP on redirects (fixed window, Redis `INCR` + `EXPIRE`).
- Cache TTL: 1 hour on `short:{code}` entries; evicted on delete/expiry.
- JWT: HS256, 7-day expiry, stored as an httpOnly cookie named `access_token`.
- Anonymous link creation is allowed; `owner_id` is null for links created without a valid session.
- All backend routes except the public redirect live under `/api`.
- Backend tests use fakeredis for anything touching Redis, and a real Postgres test database (`url_shortener_test`, same Postgres container) for anything touching the DB — no SQLite substitution, no mocked DB layer.

---

## File Structure

```
backend/
  app/
    main.py            # FastAPI app, CORS, router includes, exception handlers
    config.py          # Settings (env vars)
    db.py              # engine, SessionLocal, Base, get_db
    redis_client.py    # redis.Redis singleton, get_redis
    models.py          # User, Link, Click ORM models
    schemas.py         # Pydantic request/response schemas
    security.py        # JWT encode/decode, get_current_user(_optional)
    shortcode.py        # generate_code()
    rate_limit.py       # rate_limit() dependency factory
    cache.py             # cache_get_link/cache_set_link/cache_delete_link
    routers/
      auth.py            # Google OAuth login/callback/me/logout
      links.py            # create/list/delete/analytics
      redirect.py          # GET /{code}
  alembic/                  # migrations
  tests/
    conftest.py
    test_shortcode.py
    test_rate_limit.py
    test_cache.py
    test_links_create.py
    test_redirect.py
    test_links_manage.py
    test_auth.py
  requirements.txt
  Dockerfile
frontend/
  src/
    main.jsx
    App.jsx
    api.js
    context/AuthContext.jsx
    pages/Home.jsx
    pages/Dashboard.jsx
    pages/LinkAnalytics.jsx
    components/ShortenForm.jsx
    components/LinkList.jsx
    components/LoginButton.jsx
  tests/
    ShortenForm.test.jsx
    Dashboard.test.jsx
  package.json
  vite.config.js
  Dockerfile
  nginx.conf
docker-compose.yml
render.yaml
```

---

### Task 1: Repo scaffolding & Docker Compose

**Files:**
- Create: `backend/requirements.txt`, `backend/Dockerfile`, `backend/app/__init__.py`
- Create: `frontend/package.json`, `frontend/vite.config.js`, `frontend/Dockerfile`, `frontend/index.html`, `frontend/src/main.jsx`, `frontend/src/App.jsx`
- Create: `docker-compose.yml`, `.gitignore`, `.env.example`

**Interfaces:**
- Produces: a `docker-compose up` that starts `postgres`, `redis`, `backend` (empty FastAPI app on :8000), `frontend` (Vite dev server on :5173) — later tasks fill in behavior.

- [ ] **Step 1: Create `.gitignore` and `.env.example`**

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
node_modules/
dist/
.env
*.db
```

`.env.example`:
```
DATABASE_URL=postgresql+psycopg2://postgres:postgres@postgres:5432/url_shortener
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@postgres:5432/url_shortener_test
REDIS_URL=redis://redis:6379/0
JWT_SECRET=dev-secret-change-me
GOOGLE_CLIENT_ID=changeme
GOOGLE_CLIENT_SECRET=changeme
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
FRONTEND_URL=http://localhost:5173
SESSION_SECRET=dev-session-secret-change-me
```

- [ ] **Step 2: Backend requirements and Dockerfile**

`backend/requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
alembic==1.13.2
pydantic-settings==2.5.2
redis==5.0.8
pyjwt==2.9.0
authlib==1.3.2
itsdangerous==2.2.0
httpx==0.27.2
pytest==8.3.3
fakeredis==2.24.1
```

`backend/Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

`backend/app/__init__.py`: empty file.

`backend/app/main.py` (minimal placeholder app, replaced/extended in Task 12 — must be a real working app, not a stub comment):
```python
from fastapi import FastAPI

app = FastAPI(title="URL Shortener")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 3: Frontend scaffold**

`frontend/package.json`:
```json
{
  "name": "url-shortener-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^25.0.1",
    "vite": "^5.4.8",
    "vitest": "^2.1.1"
  }
}
```

`frontend/vite.config.js`:
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173 },
  test: { environment: 'jsdom', globals: true, setupFiles: './tests/setup.js' }
})
```

`frontend/tests/setup.js`:
```javascript
import '@testing-library/jest-dom'
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="en">
  <head><meta charset="UTF-8" /><title>URL Shortener</title></head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

`frontend/src/main.jsx`:
```javascript
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
```

`frontend/src/App.jsx` (placeholder, extended in Task 15):
```javascript
export default function App() {
  return <h1>URL Shortener</h1>
}
```

`frontend/Dockerfile` (dev target used by docker-compose; Task 18 adds a production build stage):
```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
CMD ["npm", "run", "dev"]
```

- [ ] **Step 4: `docker-compose.yml`**

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: url_shortener
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
  redis:
    image: redis:7
    ports: ["6379:6379"]
  backend:
    build: ./backend
    env_file: .env
    ports: ["8000:8000"]
    volumes: ["./backend:/app"]
    depends_on: [postgres, redis]
  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    volumes: ["./frontend:/app", "/app/node_modules"]
    depends_on: [backend]
volumes:
  pgdata:
```

- [ ] **Step 5: Verify the stack boots**

Run: `cp .env.example .env && docker-compose up -d postgres redis backend && sleep 5 && curl -s http://localhost:8000/health`
Expected: `{"status":"ok"}`

- [ ] **Step 6: Commit**

```bash
git add .gitignore .env.example docker-compose.yml backend frontend
git commit -m "chore: scaffold backend/frontend and docker-compose"
```

### Task 2: Backend config, DB, and Redis connections

**Files:**
- Create: `backend/app/config.py`, `backend/app/db.py`, `backend/app/redis_client.py`
- Test: `backend/tests/conftest.py`, `backend/tests/test_db.py`

**Interfaces:**
- Consumes: `DATABASE_URL`, `REDIS_URL`, `TEST_DATABASE_URL`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `FRONTEND_URL`, `SESSION_SECRET` env vars.
- Produces: `Settings` (importable as `from app.config import settings`), `Base`, `SessionLocal`, `get_db()` generator dependency, `get_redis()` dependency returning a `redis.Redis` client.

- [ ] **Step 1: `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    test_database_url: str = ""
    redis_url: str
    jwt_secret: str
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    frontend_url: str = "http://localhost:5173"
    session_secret: str = "dev-session-secret"

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 2: `backend/app/db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: `backend/app/redis_client.py`**

```python
import redis

from app.config import settings

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def get_redis():
    return redis_client
```

- [ ] **Step 4: `backend/tests/conftest.py`** (shared fixtures every later test task relies on)

```python
import os
import fakeredis
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/url_shortener")
os.environ.setdefault("TEST_DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/url_shortener_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.config import settings  # noqa: E402
from app.db import Base  # noqa: E402
import app.models  # noqa: E402,F401  (ensure models are registered on Base)


@pytest.fixture(scope="session")
def test_engine():
    admin_engine = create_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS url_shortener_test"))
        conn.execute(text("CREATE DATABASE url_shortener_test"))
    engine = create_engine(settings.test_database_url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def fake_redis():
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture()
def client(db_session, fake_redis):
    from app.main import app
    from app.db import get_db
    from app.redis_client import get_redis
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: fake_redis
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

Note: this fixture set assumes `backend/app/main.py`, `get_db`, and `get_redis` already exist (Task 1/2) and that `app/models.py` exists (Task 3) — run `pytest` again after Task 3 if `test_db.py` fails on import before then.

- [ ] **Step 5: `backend/tests/test_db.py`**

```python
from sqlalchemy import text


def test_db_session_executes_query(db_session):
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_redis_roundtrip(fake_redis):
    fake_redis.set("k", "v")
    assert fake_redis.get("k") == "v"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker-compose up -d postgres redis && cd backend && pip install -r requirements.txt && pytest tests/test_db.py -v`
Expected: both tests PASS (requires local Python + Postgres/Redis reachable on localhost, matching the compose port mappings).

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/app/db.py backend/app/redis_client.py backend/tests/conftest.py backend/tests/test_db.py
git commit -m "feat: backend settings, DB session, and Redis client with test fixtures"
```

### Task 3: Database models and Alembic migration

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: ORM classes `User(id, email, name, google_sub, created_at)`, `Link(id, code, target_url, owner_id, is_custom_alias, expires_at, created_at)`, `Click(id, link_id, clicked_at, referrer, user_agent)`. Later tasks import these as `from app.models import User, Link, Click`.

- [ ] **Step 1: `backend/app/models.py`**

```python
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    links: Mapped[list["Link"]] = relationship(back_populates="owner")


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_custom_alias: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped["User | None"] = relationship(back_populates="links")
    clicks: Mapped[list["Click"]] = relationship(back_populates="link", cascade="all, delete-orphan")


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id"), nullable=False)
    clicked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    referrer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    link: Mapped["Link"] = relationship(back_populates="clicks")
```

- [ ] **Step 2: `backend/tests/test_models.py`**

```python
from app.models import User, Link, Click


def test_create_user_link_click(db_session):
    user = User(email="a@example.com", name="A", google_sub="sub-1")
    db_session.add(user)
    db_session.flush()

    link = Link(code="abc1234", target_url="https://example.com", owner_id=user.id)
    db_session.add(link)
    db_session.flush()

    click = Click(link_id=link.id, referrer="https://ref.com", user_agent="pytest")
    db_session.add(click)
    db_session.flush()

    assert link.owner.email == "a@example.com"
    assert link.clicks[0].referrer == "https://ref.com"


def test_link_owner_is_optional(db_session):
    link = Link(code="anon001", target_url="https://example.com", owner_id=None)
    db_session.add(link)
    db_session.flush()
    assert link.owner_id is None
```

- [ ] **Step 3: Run tests to verify they fail (tables don't exist yet via migration, but conftest creates them via `Base.metadata.create_all` — verify they pass instead once models are added)**

Run: `cd backend && pytest tests/test_models.py -v`
Expected: PASS (the `test_engine` fixture calls `Base.metadata.create_all`, which now has these tables registered).

- [ ] **Step 4: Alembic setup and initial migration** (for production deploys, where `create_all` isn't used — Task 19 runs `alembic upgrade head` against the Render Postgres)

`backend/alembic.ini`:
```ini
[alembic]
script_location = alembic
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handlers]
keys = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatters]
keys = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

`backend/alembic/env.py`:
```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db import Base
import app.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

`backend/alembic/versions/0001_initial.py`:
```python
"""initial tables

Revision ID: 0001
Revises:
Create Date: 2026-09-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("google_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "links",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("target_url", sa.Text, nullable=False),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_custom_alias", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_links_code", "links", ["code"])
    op.create_table(
        "clicks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("link_id", sa.Integer, sa.ForeignKey("links.id"), nullable=False),
        sa.Column("clicked_at", sa.DateTime, nullable=False),
        sa.Column("referrer", sa.String(512), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
    )


def downgrade():
    op.drop_table("clicks")
    op.drop_index("ix_links_code", table_name="links")
    op.drop_table("links")
    op.drop_table("users")
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/alembic.ini backend/alembic backend/tests/test_models.py
git commit -m "feat: add User/Link/Click models with Alembic migration"
```

### Task 4: Short code generation

**Files:**
- Create: `backend/app/shortcode.py`
- Test: `backend/tests/test_shortcode.py`

**Interfaces:**
- Produces: `generate_code(length: int = 7) -> str`, `CODE_ALPHABET: str`. Task 7 imports `generate_code`.

- [ ] **Step 1: Write the failing tests**

```python
from app.shortcode import generate_code, CODE_ALPHABET


def test_generate_code_default_length():
    code = generate_code()
    assert len(code) == 7


def test_generate_code_custom_length():
    code = generate_code(length=10)
    assert len(code) == 10


def test_generate_code_uses_only_base62_alphabet():
    code = generate_code()
    assert all(ch in CODE_ALPHABET for ch in code)


def test_generate_code_is_randomized():
    codes = {generate_code() for _ in range(50)}
    assert len(codes) == 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_shortcode.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.shortcode'`

- [ ] **Step 3: Implement `backend/app/shortcode.py`**

```python
import secrets
import string

CODE_ALPHABET = string.ascii_letters + string.digits


def generate_code(length: int = 7) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_shortcode.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/shortcode.py backend/tests/test_shortcode.py
git commit -m "feat: base62 short code generator"
```

### Task 5: Rate limiter

**Files:**
- Create: `backend/app/rate_limit.py`
- Test: `backend/tests/test_rate_limit.py`

**Interfaces:**
- Consumes: a `redis.Redis`-compatible client (fakeredis in tests, real client via `get_redis` in the app).
- Produces: `check_rate_limit(redis_client, key: str, limit: int, window_seconds: int) -> bool` (True if allowed, False if over limit) and `rate_limit_dependency(bucket: str, limit: int, window_seconds: int)` — a FastAPI dependency factory used by Task 7/8 as `Depends(rate_limit_dependency("create", 10, 60))`. Raises `fastapi.HTTPException(429, headers={"Retry-After": str(window_seconds)})` when exceeded.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from fastapi import HTTPException

from app.rate_limit import check_rate_limit


def test_allows_requests_under_the_limit(fake_redis):
    for _ in range(5):
        assert check_rate_limit(fake_redis, "ip:1.2.3.4:test", limit=5, window_seconds=60) is True


def test_blocks_requests_over_the_limit(fake_redis):
    for _ in range(5):
        check_rate_limit(fake_redis, "ip:1.2.3.4:test", limit=5, window_seconds=60)
    assert check_rate_limit(fake_redis, "ip:1.2.3.4:test", limit=5, window_seconds=60) is False


def test_different_keys_have_independent_limits(fake_redis):
    for _ in range(5):
        check_rate_limit(fake_redis, "ip:1.2.3.4:test", limit=5, window_seconds=60)
    assert check_rate_limit(fake_redis, "ip:9.9.9.9:test", limit=5, window_seconds=60) is True


def test_sets_expiry_on_first_increment(fake_redis):
    check_rate_limit(fake_redis, "ip:1.2.3.4:test", limit=5, window_seconds=60)
    ttl = fake_redis.ttl("ratelimit:ip:1.2.3.4:test")
    assert 0 < ttl <= 60
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_rate_limit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.rate_limit'`

- [ ] **Step 3: Implement `backend/app/rate_limit.py`**

```python
from fastapi import Depends, HTTPException, Request

from app.redis_client import get_redis


def check_rate_limit(redis_client, key: str, limit: int, window_seconds: int) -> bool:
    full_key = f"ratelimit:{key}"
    count = redis_client.incr(full_key)
    if count == 1:
        redis_client.expire(full_key, window_seconds)
    return count <= limit


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_dependency(bucket: str, limit: int, window_seconds: int):
    def dependency(request: Request, redis_client=Depends(get_redis)):
        key = f"ip:{_client_ip(request)}:{bucket}"
        if not check_rate_limit(redis_client, key, limit, window_seconds):
            raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": str(window_seconds)})

    return dependency
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_rate_limit.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/rate_limit.py backend/tests/test_rate_limit.py
git commit -m "feat: Redis fixed-window rate limiter"
```

### Task 6: Cache helpers

**Files:**
- Create: `backend/app/cache.py`
- Test: `backend/tests/test_cache.py`

**Interfaces:**
- Produces: `cache_set_link(redis_client, code: str, target_url: str, link_id: int, ttl_seconds: int = 3600)`, `cache_get_link(redis_client, code: str) -> dict | None` (returns `{"target_url": str, "link_id": int}`), `cache_delete_link(redis_client, code: str)`, `ttl_for_expiry(expires_at: datetime | None, default_ttl: int = 3600) -> int`. Task 8/9/10 import all four.

The cache stores `link_id` alongside `target_url` (not just the URL string) so the redirect endpoint (Task 9) can serve a cache hit — redirect *and* click logging — without any Postgres query. `ttl_for_expiry` clamps the cache TTL to the link's remaining lifetime so a cached entry never outlives the link's actual `expires_at`, which is what lets Task 9 trust a cache hit as still valid without re-checking the database.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timedelta

from app.cache import cache_set_link, cache_get_link, cache_delete_link, ttl_for_expiry


def test_set_then_get_returns_target_url_and_link_id(fake_redis):
    cache_set_link(fake_redis, "abc1234", "https://example.com", link_id=7)
    assert cache_get_link(fake_redis, "abc1234") == {"target_url": "https://example.com", "link_id": 7}


def test_get_missing_code_returns_none(fake_redis):
    assert cache_get_link(fake_redis, "nope000") is None


def test_delete_removes_entry(fake_redis):
    cache_set_link(fake_redis, "abc1234", "https://example.com", link_id=7)
    cache_delete_link(fake_redis, "abc1234")
    assert cache_get_link(fake_redis, "abc1234") is None


def test_set_applies_ttl(fake_redis):
    cache_set_link(fake_redis, "abc1234", "https://example.com", link_id=7, ttl_seconds=100)
    ttl = fake_redis.ttl("short:abc1234")
    assert 0 < ttl <= 100


def test_ttl_for_expiry_returns_default_when_no_expiry():
    assert ttl_for_expiry(None, default_ttl=3600) == 3600


def test_ttl_for_expiry_clamps_to_remaining_lifetime():
    expires_at = datetime.utcnow() + timedelta(seconds=30)
    assert ttl_for_expiry(expires_at, default_ttl=3600) <= 30


def test_ttl_for_expiry_returns_zero_when_already_expired():
    expires_at = datetime.utcnow() - timedelta(seconds=1)
    assert ttl_for_expiry(expires_at, default_ttl=3600) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.cache'`

- [ ] **Step 3: Implement `backend/app/cache.py`**

```python
import json
from datetime import datetime

DEFAULT_TTL_SECONDS = 3600


def _key(code: str) -> str:
    return f"short:{code}"


def cache_set_link(redis_client, code: str, target_url: str, link_id: int, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    payload = json.dumps({"target_url": target_url, "link_id": link_id})
    redis_client.set(_key(code), payload, ex=ttl_seconds)


def cache_get_link(redis_client, code: str) -> dict | None:
    raw = redis_client.get(_key(code))
    if raw is None:
        return None
    return json.loads(raw)


def cache_delete_link(redis_client, code: str) -> None:
    redis_client.delete(_key(code))


def ttl_for_expiry(expires_at: datetime | None, default_ttl: int = DEFAULT_TTL_SECONDS) -> int:
    if expires_at is None:
        return default_ttl
    seconds_left = int((expires_at - datetime.utcnow()).total_seconds())
    return max(min(default_ttl, seconds_left), 0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_cache.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/cache.py backend/tests/test_cache.py
git commit -m "feat: Redis cache-aside helpers for link lookups"
```

### Task 7: JWT security helpers and Google OAuth

**Files:**
- Create: `backend/app/security.py`, `backend/app/routers/__init__.py`, `backend/app/routers/auth.py`
- Modify: `backend/app/main.py` (add `SessionMiddleware`, include `auth` router)
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `Settings.jwt_secret`, `Settings.google_client_id/secret/redirect_uri`, `Settings.frontend_url`, `Settings.session_secret`; `User` model (Task 3).
- Produces: `create_access_token(user_id: int) -> str`, `decode_access_token(token: str) -> dict | None`, `get_current_user(request, db=Depends(get_db)) -> User` (raises 401), `get_current_user_optional(request, db=Depends(get_db)) -> User | None`, `upsert_user_and_issue_token(db, profile: dict) -> tuple[User, str]`. Tasks 8/10/11 depend on `get_current_user` and `get_current_user_optional`.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timedelta

import jwt

from app.security import create_access_token, decode_access_token, upsert_user_and_issue_token
from app.config import settings
from app.models import User


def test_create_and_decode_access_token_roundtrip():
    token = create_access_token(user_id=42)
    payload = decode_access_token(token)
    assert payload["sub"] == "42"


def test_decode_rejects_invalid_token():
    assert decode_access_token("not-a-real-token") is None


def test_decode_rejects_expired_token():
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.utcnow() - timedelta(days=1)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    assert decode_access_token(expired) is None


def test_upsert_creates_new_user_and_token(db_session):
    profile = {"email": "new@example.com", "name": "New User", "sub": "google-sub-1"}
    user, token = upsert_user_and_issue_token(db_session, profile)
    assert user.email == "new@example.com"
    assert decode_access_token(token)["sub"] == str(user.id)


def test_upsert_reuses_existing_user_by_google_sub(db_session):
    existing = User(email="old@example.com", name="Old Name", google_sub="google-sub-2")
    db_session.add(existing)
    db_session.flush()

    profile = {"email": "old@example.com", "name": "Updated Name", "sub": "google-sub-2"}
    user, _ = upsert_user_and_issue_token(db_session, profile)
    assert user.id == existing.id
    assert user.name == "Updated Name"


def test_login_redirects_to_google(client):
    response = client.get("/api/auth/google/login", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]


def test_me_requires_auth(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_returns_user_when_cookie_present(client, db_session):
    user = User(email="a@example.com", name="A", google_sub="sub-a")
    db_session.add(user)
    db_session.flush()
    token = create_access_token(user_id=user.id)
    client.cookies.set("access_token", token)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "a@example.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.security'`

- [ ] **Step 3: Implement `backend/app/security.py`**

```python
from datetime import datetime, timedelta

import jwt
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

ALGORITHM = "HS256"
TOKEN_EXPIRY_DAYS = 7


def create_access_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(days=TOKEN_EXPIRY_DAYS)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def upsert_user_and_issue_token(db: Session, profile: dict) -> tuple[User, str]:
    user = db.query(User).filter(User.google_sub == profile["sub"]).first()
    if user is None:
        user = User(email=profile["email"], name=profile["name"], google_sub=profile["sub"])
        db.add(user)
    else:
        user.name = profile["name"]
        user.email = profile["email"]
    db.flush()
    token = create_access_token(user.id)
    return user, token


def get_current_user_optional(
    access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)
) -> User | None:
    if not access_token:
        return None
    payload = decode_access_token(access_token)
    if not payload:
        return None
    return db.query(User).filter(User.id == int(payload["sub"])).first()


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
```

- [ ] **Step 4: Implement `backend/app/routers/auth.py`**

```python
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.security import get_current_user, upsert_user_and_issue_token
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/google/login")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    profile = token["userinfo"]
    _, jwt_token = upsert_user_and_issue_token(db, profile)
    db.commit()
    response = RedirectResponse(url=settings.frontend_url)
    response.set_cookie("access_token", jwt_token, httponly=True, samesite="lax", max_age=7 * 24 * 3600)
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name}


@router.post("/logout")
def logout():
    response = RedirectResponse(url=settings.frontend_url)
    response.delete_cookie("access_token")
    return response
```

`backend/app/routers/__init__.py`: empty file.

- [ ] **Step 5: Wire the router into `backend/app/main.py`**

```python
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth

app = FastAPI(title="URL Shortener")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.include_router(auth.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: PASS (8 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/security.py backend/app/routers backend/app/main.py backend/tests/test_auth.py
git commit -m "feat: JWT auth helpers and Google OAuth login/callback/me/logout"
```

### Task 8: Link creation endpoint

**Files:**
- Create: `backend/app/schemas.py`, `backend/app/routers/links.py`
- Modify: `backend/app/config.py` (add `public_base_url` setting), `backend/app/main.py` (include `links` router)
- Test: `backend/tests/test_links_create.py`

**Interfaces:**
- Consumes: `generate_code` (Task 4), `cache_set_link` (Task 6), `rate_limit_dependency` (Task 5), `get_current_user_optional` (Task 7), `Link` model (Task 3).
- Produces: `POST /api/links` returning `{id, code, short_url, target_url, is_custom_alias, expires_at, created_at}`. Task 10/11 reuse `schemas.LinkOut`.

- [ ] **Step 1: Add `public_base_url` to `backend/app/config.py`**

```python
    public_base_url: str = "http://localhost:8000"
```
(add as a field on the `Settings` class, alongside the others; add `PUBLIC_BASE_URL=http://localhost:8000` to `.env.example` too)

- [ ] **Step 2: Write the failing tests**

```python
from datetime import datetime, timedelta


def test_create_link_anonymous(client):
    response = client.post("/api/links", json={"url": "https://example.com/some/long/path"})
    assert response.status_code == 201
    body = response.json()
    assert len(body["code"]) == 7
    assert body["short_url"].endswith(body["code"])
    assert body["target_url"] == "https://example.com/some/long/path"


def test_create_link_with_custom_alias(client):
    response = client.post("/api/links", json={"url": "https://example.com", "custom_alias": "my-link"})
    assert response.status_code == 201
    assert response.json()["code"] == "my-link"
    assert response.json()["is_custom_alias"] is True


def test_create_link_rejects_taken_alias(client):
    client.post("/api/links", json={"url": "https://example.com", "custom_alias": "taken"})
    response = client.post("/api/links", json={"url": "https://other.com", "custom_alias": "taken"})
    assert response.status_code == 400


def test_create_link_rejects_invalid_url(client):
    response = client.post("/api/links", json={"url": "not-a-url"})
    assert response.status_code == 422


def test_create_link_accepts_expiry(client):
    expires = (datetime.utcnow() + timedelta(days=1)).isoformat()
    response = client.post("/api/links", json={"url": "https://example.com", "expires_at": expires})
    assert response.status_code == 201
    assert response.json()["expires_at"] is not None


def test_create_link_primes_cache(client, fake_redis):
    import json

    response = client.post("/api/links", json={"url": "https://example.com/cached"})
    code = response.json()["code"]
    cached = json.loads(fake_redis.get(f"short:{code}"))
    assert cached["target_url"] == "https://example.com/cached"
    assert cached["link_id"] == response.json()["id"]


def test_create_link_rate_limited_after_ten_per_minute(client):
    for _ in range(10):
        client.post("/api/links", json={"url": "https://example.com"})
    response = client.post("/api/links", json={"url": "https://example.com"})
    assert response.status_code == 429
    assert "Retry-After" in response.headers
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_links_create.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas'`

- [ ] **Step 4: Implement `backend/app/schemas.py`**

```python
from datetime import datetime

from pydantic import BaseModel, HttpUrl, field_validator


class LinkCreate(BaseModel):
    url: HttpUrl
    custom_alias: str | None = None
    expires_at: datetime | None = None

    @field_validator("custom_alias")
    @classmethod
    def alias_must_be_slug_like(cls, v):
        if v is not None and (len(v) < 3 or not v.replace("-", "").isalnum()):
            raise ValueError("custom_alias must be at least 3 alphanumeric/hyphen characters")
        return v


class LinkOut(BaseModel):
    id: int
    code: str
    short_url: str
    target_url: str
    is_custom_alias: bool
    expires_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 5: Implement `backend/app/routers/links.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cache import cache_set_link, ttl_for_expiry
from app.config import settings
from app.db import get_db
from app.models import Link, User
from app.rate_limit import rate_limit_dependency
from app.redis_client import get_redis
from app.schemas import LinkCreate, LinkOut
from app.security import get_current_user_optional
from app.shortcode import generate_code

router = APIRouter(prefix="/api/links", tags=["links"])

MAX_CODE_ATTEMPTS = 5


def _to_out(link: Link) -> LinkOut:
    return LinkOut(
        id=link.id,
        code=link.code,
        short_url=f"{settings.public_base_url}/{link.code}",
        target_url=link.target_url,
        is_custom_alias=link.is_custom_alias,
        expires_at=link.expires_at,
        created_at=link.created_at,
    )


@router.post("", status_code=201, response_model=LinkOut, dependencies=[Depends(rate_limit_dependency("create", 10, 60))])
def create_link(
    payload: LinkCreate,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis),
    user: User | None = Depends(get_current_user_optional),
):
    if payload.custom_alias:
        existing = db.query(Link).filter(Link.code == payload.custom_alias).first()
        if existing:
            raise HTTPException(status_code=400, detail="Alias already taken")
        code = payload.custom_alias
        is_custom = True
    else:
        code = None
        is_custom = False
        for _ in range(MAX_CODE_ATTEMPTS):
            candidate = generate_code()
            if not db.query(Link).filter(Link.code == candidate).first():
                code = candidate
                break
        if code is None:
            raise HTTPException(status_code=500, detail="Could not generate a unique code")

    link = Link(
        code=code,
        target_url=str(payload.url),
        owner_id=user.id if user else None,
        is_custom_alias=is_custom,
        expires_at=payload.expires_at,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Alias already taken")
    db.refresh(link)

    ttl = ttl_for_expiry(link.expires_at)
    if ttl > 0:
        cache_set_link(redis_client, link.code, link.target_url, link.id, ttl_seconds=ttl)
    return _to_out(link)
```

- [ ] **Step 6: Wire the router into `backend/app/main.py`**

```python
from app.routers import auth, links

app.include_router(links.router)
```
(add this import/include alongside the existing `auth` router registration from Task 7)

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_links_create.py -v`
Expected: PASS (7 tests)

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/links.py backend/app/config.py backend/app/main.py backend/tests/test_links_create.py
git commit -m "feat: link creation endpoint with rate limiting and cache priming"
```

### Task 9: Redirect endpoint

**Files:**
- Create: `backend/app/routers/redirect.py`
- Modify: `backend/app/main.py` (include `redirect` router — must be included **last**, after `/health` and all `/api/*` routers, since `/{code}` is a catch-all single path segment)
- Test: `backend/tests/test_redirect.py`

**Interfaces:**
- Consumes: `cache_get_link`/`cache_set_link`/`ttl_for_expiry` (Task 6), `rate_limit_dependency` (Task 5), `Link`/`Click` models (Task 3).
- Produces: `GET /{code}` — 302 redirect on hit, 404 on miss/expired, logs a click via `BackgroundTasks`. On a cache hit, this handler makes **no Postgres query at all** — `cache_get_link` returns both `target_url` and `link_id`, and `ttl_for_expiry` (used when priming the cache) guarantees a cached entry never outlives the link's real expiry, so a hit can be trusted without re-checking the database.

- [ ] **Step 1: Write the failing tests**

```python
import json
from datetime import datetime, timedelta

from app.models import Link, Click


def test_redirect_hits_db_and_caches_on_first_request(client, db_session, fake_redis):
    link = Link(code="dbonly1", target_url="https://example.com/db")
    db_session.add(link)
    db_session.commit()

    response = client.get("/dbonly1", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/db"
    cached = json.loads(fake_redis.get("short:dbonly1"))
    assert cached == {"target_url": "https://example.com/db", "link_id": link.id}


def test_redirect_on_cache_hit_uses_cached_link_id_for_click_logging(client, db_session, fake_redis):
    from app.cache import cache_set_link

    link = Link(code="cached1", target_url="https://example.com/cached")
    db_session.add(link)
    db_session.commit()
    cache_set_link(fake_redis, "cached1", "https://example.com/cached", link_id=link.id)

    response = client.get("/cached1", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/cached"

    clicks = db_session.query(Click).filter(Click.link_id == link.id).all()
    assert len(clicks) == 1


def test_redirect_404_for_unknown_code(client):
    response = client.get("/doesnotexist", follow_redirects=False)
    assert response.status_code == 404


def test_redirect_404_for_expired_link(client, db_session):
    link = Link(code="expired1", target_url="https://example.com", expires_at=datetime.utcnow() - timedelta(days=1))
    db_session.add(link)
    db_session.commit()

    response = client.get("/expired1", follow_redirects=False)
    assert response.status_code == 404


def test_redirect_does_not_cache_an_already_expired_link(client, db_session, fake_redis):
    link = Link(code="expired2", target_url="https://example.com", expires_at=datetime.utcnow() - timedelta(days=1))
    db_session.add(link)
    db_session.commit()

    client.get("/expired2", follow_redirects=False)
    assert fake_redis.get("short:expired2") is None


def test_redirect_logs_a_click(client, db_session):
    link = Link(code="clicklog", target_url="https://example.com")
    db_session.add(link)
    db_session.commit()

    client.get("/clicklog", follow_redirects=False, headers={"referer": "https://ref.com", "user-agent": "pytest"})

    clicks = db_session.query(Click).filter(Click.link_id == link.id).all()
    assert len(clicks) == 1
    assert clicks[0].referrer == "https://ref.com"


def test_redirect_rate_limited_after_sixty_per_minute(client, db_session):
    link = Link(code="ratelim1", target_url="https://example.com")
    db_session.add(link)
    db_session.commit()

    for _ in range(60):
        client.get("/ratelim1", follow_redirects=False)
    response = client.get("/ratelim1", follow_redirects=False)
    assert response.status_code == 429
```

Note: `BackgroundTasks` run synchronously within `TestClient`'s request/response cycle, so the click row is visible immediately after the request returns — no sleep/poll needed.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_redirect.py -v`
Expected: FAIL — `/dbonly1` etc. return 404 (no such route yet) instead of 302.

- [ ] **Step 3: Implement `backend/app/routers/redirect.py`**

```python
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.cache import cache_get_link, cache_set_link, ttl_for_expiry
from app.db import get_db
from app.models import Click, Link
from app.rate_limit import rate_limit_dependency
from app.redis_client import get_redis

router = APIRouter(tags=["redirect"])


def _log_click(db: Session, link_id: int, referrer: str | None, user_agent: str | None) -> None:
    db.add(Click(link_id=link_id, referrer=referrer, user_agent=user_agent))
    db.commit()


@router.get("/{code}", dependencies=[Depends(rate_limit_dependency("redirect", 60, 60))])
def redirect_to_target(
    code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis),
):
    cached = cache_get_link(redis_client, code)
    if cached is not None:
        target_url = cached["target_url"]
        link_id = cached["link_id"]
    else:
        link = db.query(Link).filter(Link.code == code).first()
        if link is None:
            raise HTTPException(status_code=404, detail="Not found")
        if link.expires_at and link.expires_at < datetime.utcnow():
            raise HTTPException(status_code=404, detail="Link expired")
        target_url = link.target_url
        link_id = link.id
        ttl = ttl_for_expiry(link.expires_at)
        if ttl > 0:
            cache_set_link(redis_client, code, target_url, link_id, ttl_seconds=ttl)

    background_tasks.add_task(
        _log_click, db, link_id, request.headers.get("referer"), request.headers.get("user-agent")
    )
    return RedirectResponse(url=target_url, status_code=302)
```

- [ ] **Step 4: Wire the router into `backend/app/main.py`** (last, after `auth` and `links`)

```python
from app.routers import auth, links, redirect

app.include_router(auth.router)
app.include_router(links.router)
app.include_router(redirect.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_redirect.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/redirect.py backend/app/main.py backend/tests/test_redirect.py
git commit -m "feat: public redirect endpoint with cache-aside lookup and click logging"
```

### Task 10: Link listing and deletion (owned links)

**Files:**
- Modify: `backend/app/routers/links.py` (add `GET /api/links` and `DELETE /api/links/{id}`)
- Test: `backend/tests/test_links_manage.py`

**Interfaces:**
- Consumes: `get_current_user` (Task 7, required — not optional, since these are the "manage my links" routes), `cache_delete_link` (Task 6).
- Produces: `GET /api/links -> list[LinkOut]`, `DELETE /api/links/{id} -> 204`.

- [ ] **Step 1: Write the failing tests**

```python
from app.models import Link, User
from app.security import create_access_token


def _login(client, db_session, email="owner@example.com", sub="owner-sub"):
    user = User(email=email, name="Owner", google_sub=sub)
    db_session.add(user)
    db_session.flush()
    client.cookies.set("access_token", create_access_token(user.id))
    return user


def test_list_requires_auth(client):
    response = client.get("/api/links")
    assert response.status_code == 401


def test_list_returns_only_own_links(client, db_session):
    owner = _login(client, db_session)
    other = User(email="other@example.com", name="Other", google_sub="other-sub")
    db_session.add(other)
    db_session.flush()
    db_session.add_all([
        Link(code="mine0001", target_url="https://example.com/mine", owner_id=owner.id),
        Link(code="theirs01", target_url="https://example.com/theirs", owner_id=other.id),
    ])
    db_session.commit()

    response = client.get("/api/links")
    codes = [link["code"] for link in response.json()]
    assert codes == ["mine0001"]


def test_delete_requires_ownership(client, db_session):
    _login(client, db_session)
    other = User(email="other2@example.com", name="Other2", google_sub="other-sub-2")
    db_session.add(other)
    db_session.flush()
    link = Link(code="notmine1", target_url="https://example.com", owner_id=other.id)
    db_session.add(link)
    db_session.commit()

    response = client.delete(f"/api/links/{link.id}")
    assert response.status_code == 404


def test_delete_removes_link_and_cache_entry(client, db_session, fake_redis):
    owner = _login(client, db_session)
    link = Link(code="deleteme", target_url="https://example.com", owner_id=owner.id)
    db_session.add(link)
    db_session.commit()
    fake_redis.set("short:deleteme", "https://example.com")

    response = client.delete(f"/api/links/{link.id}")
    assert response.status_code == 204
    assert db_session.query(Link).filter(Link.id == link.id).first() is None
    assert fake_redis.get("short:deleteme") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_links_manage.py -v`
Expected: FAIL — `GET /api/links` and `DELETE /api/links/{id}` return 404 (routes don't exist yet).

- [ ] **Step 3: Add the two routes to `backend/app/routers/links.py`** (append below `create_link`, using the same imports already in that file plus `get_current_user`)

```python
from app.cache import cache_delete_link  # add to existing cache import line
from app.security import get_current_user  # add alongside get_current_user_optional import


@router.get("", response_model=list[LinkOut])
def list_my_links(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    links = db.query(Link).filter(Link.owner_id == user.id).order_by(Link.created_at.desc()).all()
    return [_to_out(link) for link in links]


@router.delete("/{link_id}", status_code=204)
def delete_link(
    link_id: int,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis),
    user: User = Depends(get_current_user),
):
    link = db.query(Link).filter(Link.id == link_id, Link.owner_id == user.id).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    cache_delete_link(redis_client, link.code)
    db.delete(link)
    db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_links_manage.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/links.py backend/tests/test_links_manage.py
git commit -m "feat: list and delete endpoints for a user's own links"
```

### Task 11: Click analytics endpoint

**Files:**
- Modify: `backend/app/routers/links.py` (add `GET /api/links/{id}/analytics`), `backend/app/schemas.py` (add `AnalyticsOut`)
- Test: `backend/tests/test_analytics.py`

**Interfaces:**
- Consumes: `Click` model (Task 3), `get_current_user` (Task 7).
- Produces: `GET /api/links/{id}/analytics -> {total_clicks, clicks_by_day: [{date, count}], top_referrers: [{referrer, count}]}`.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timedelta

from app.models import Click, Link, User
from app.security import create_access_token


def _login(client, db_session):
    user = User(email="an@example.com", name="An", google_sub="an-sub")
    db_session.add(user)
    db_session.flush()
    client.cookies.set("access_token", create_access_token(user.id))
    return user


def test_analytics_requires_ownership(client, db_session):
    _login(client, db_session)
    other = User(email="other3@example.com", name="Other3", google_sub="other-sub-3")
    db_session.add(other)
    db_session.flush()
    link = Link(code="notmine2", target_url="https://example.com", owner_id=other.id)
    db_session.add(link)
    db_session.commit()

    response = client.get(f"/api/links/{link.id}/analytics")
    assert response.status_code == 404


def test_analytics_aggregates_clicks(client, db_session):
    owner = _login(client, db_session)
    link = Link(code="stats001", target_url="https://example.com", owner_id=owner.id)
    db_session.add(link)
    db_session.flush()
    db_session.add_all([
        Click(link_id=link.id, clicked_at=datetime.utcnow(), referrer="https://a.com"),
        Click(link_id=link.id, clicked_at=datetime.utcnow(), referrer="https://a.com"),
        Click(link_id=link.id, clicked_at=datetime.utcnow() - timedelta(days=1), referrer="https://b.com"),
    ])
    db_session.commit()

    response = client.get(f"/api/links/{link.id}/analytics")
    body = response.json()
    assert body["total_clicks"] == 3
    assert len(body["clicks_by_day"]) == 2
    assert body["top_referrers"][0] == {"referrer": "https://a.com", "count": 2}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_analytics.py -v`
Expected: FAIL — 404/`ModuleNotFoundError`-style errors since the route and schema don't exist yet.

- [ ] **Step 3: Add `AnalyticsOut` to `backend/app/schemas.py`**

```python
class DailyCount(BaseModel):
    date: str
    count: int


class ReferrerCount(BaseModel):
    referrer: str | None
    count: int


class AnalyticsOut(BaseModel):
    total_clicks: int
    clicks_by_day: list[DailyCount]
    top_referrers: list[ReferrerCount]
```

- [ ] **Step 4: Add the route to `backend/app/routers/links.py`**

```python
from sqlalchemy import func

from app.models import Click  # add alongside existing Link, User import
from app.schemas import AnalyticsOut  # add alongside existing schema imports


@router.get("/{link_id}/analytics", response_model=AnalyticsOut)
def link_analytics(link_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    link = db.query(Link).filter(Link.id == link_id, Link.owner_id == user.id).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    total_clicks = db.query(func.count(Click.id)).filter(Click.link_id == link.id).scalar()

    by_day_rows = (
        db.query(func.date(Click.clicked_at), func.count(Click.id))
        .filter(Click.link_id == link.id)
        .group_by(func.date(Click.clicked_at))
        .order_by(func.date(Click.clicked_at))
        .all()
    )
    clicks_by_day = [{"date": str(day), "count": count} for day, count in by_day_rows]

    top_referrer_rows = (
        db.query(Click.referrer, func.count(Click.id).label("count"))
        .filter(Click.link_id == link.id)
        .group_by(Click.referrer)
        .order_by(func.count(Click.id).desc())
        .limit(5)
        .all()
    )
    top_referrers = [{"referrer": referrer, "count": count} for referrer, count in top_referrer_rows]

    return AnalyticsOut(total_clicks=total_clicks, clicks_by_day=clicks_by_day, top_referrers=top_referrers)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_analytics.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/links.py backend/app/schemas.py backend/tests/test_analytics.py
git commit -m "feat: per-link click analytics endpoint"
```

### Task 12: CORS, global exception handling, and full backend test run

**Files:**
- Modify: `backend/app/main.py` (final version — CORS middleware, global exception handler)
- Test: `backend/tests/test_error_handling.py`

**Interfaces:**
- Produces: the finished `app/main.py` that all backend tasks have been incrementally building; every route from Tasks 7-11 is registered; uncaught exceptions return `{"error": "..."}` as JSON with status 500.

- [ ] **Step 1: Write the failing test**

```python
def test_unknown_route_returns_404_json(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404


def test_cors_allows_frontend_origin(client):
    response = client.options(
        "/api/links",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
```

- [ ] **Step 2: Run tests to verify the CORS test fails**

Run: `cd backend && pytest tests/test_error_handling.py -v`
Expected: `test_unknown_route_returns_404_json` PASSes already (FastAPI's default 404); `test_cors_allows_frontend_origin` FAILs (no `access-control-allow-origin` header yet).

- [ ] **Step 3: Finalize `backend/app/main.py`**

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, links, redirect

app = FastAPI(title="URL Shortener")

app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(links.router)
app.include_router(redirect.router)  # must stay last: catch-all "/{code}" route
```

- [ ] **Step 4: Run the full backend test suite**

Run: `cd backend && pytest -v`
Expected: every test from Tasks 2-12 PASSes (roughly 45+ tests total).

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_error_handling.py
git commit -m "feat: CORS config, global exception handler, finalize router wiring"
```

### Task 13: Frontend API client, auth context, and routing skeleton

**Files:**
- Create: `frontend/src/api.js`, `frontend/src/context/AuthContext.jsx`
- Modify: `frontend/src/App.jsx`, `frontend/.env.example` (create), `frontend/vite.config.js` (no change needed — Vite picks up `VITE_*` env vars automatically)

**Interfaces:**
- Produces: `apiFetch(path, options) -> Promise<Response>` (prefixes `import.meta.env.VITE_API_BASE_URL`, always sends `credentials: 'include'`); `AuthProvider`, `useAuth() -> {user, loading, refresh, logout}`. Tasks 14-17 import both.

- [ ] **Step 1: `frontend/.env.example`**

```
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 2: `frontend/src/api.js`**

```javascript
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  return response
}

export function googleLoginUrl() {
  return `${API_BASE}/api/auth/google/login`
}
```

- [ ] **Step 3: `frontend/src/context/AuthContext.jsx`**

```javascript
import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { apiFetch } from '../api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    const response = await apiFetch('/api/auth/me')
    setUser(response.ok ? await response.json() : null)
    setLoading(false)
  }, [])

  const logout = useCallback(async () => {
    await apiFetch('/api/auth/logout', { method: 'POST' })
    setUser(null)
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <AuthContext.Provider value={{ user, loading, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
```

- [ ] **Step 4: `frontend/src/App.jsx`** (routes filled in fully by Tasks 14-17; this task wires the skeleton with placeholder page components that those tasks replace)

```javascript
import { Routes, Route, Link as RouterLink } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext.jsx'
import Home from './pages/Home.jsx'

function Placeholder({ label }) {
  return <p>{label}</p>
}

export default function App() {
  return (
    <AuthProvider>
      <nav>
        <RouterLink to="/">Home</RouterLink>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/dashboard" element={<Placeholder label="Dashboard coming in Task 16" />} />
        <Route path="/links/:id/analytics" element={<Placeholder label="Analytics coming in Task 17" />} />
      </Routes>
    </AuthProvider>
  )
}
```

`frontend/src/pages/Home.jsx` (placeholder, replaced in Task 14):
```javascript
export default function Home() {
  return <h1>URL Shortener</h1>
}
```

- [ ] **Step 5: Verify it still renders**

Run: `cd frontend && npm install && npm run build`
Expected: build succeeds with no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.js frontend/src/context frontend/src/App.jsx frontend/src/pages/Home.jsx frontend/.env.example
git commit -m "feat: frontend API client, auth context, and routing skeleton"
```

### Task 14: Home page with shorten form

**Files:**
- Modify: `frontend/src/pages/Home.jsx`
- Create: `frontend/src/components/ShortenForm.jsx`
- Test: `frontend/tests/ShortenForm.test.jsx`

**Interfaces:**
- Consumes: `apiFetch` (Task 13).
- Produces: a form that POSTs to `/api/links` and displays the resulting short URL.

- [ ] **Step 1: Write the failing test**

```javascript
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
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/ShortenForm.test.jsx`
Expected: FAIL — `Cannot find module '../src/components/ShortenForm.jsx'`

- [ ] **Step 3: Implement `frontend/src/components/ShortenForm.jsx`**

```javascript
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
```

- [ ] **Step 4: Wire it into `frontend/src/pages/Home.jsx`**

```javascript
import ShortenForm from '../components/ShortenForm.jsx'

export default function Home() {
  return (
    <div>
      <h1>URL Shortener</h1>
      <ShortenForm />
    </div>
  )
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/ShortenForm.test.jsx`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ShortenForm.jsx frontend/src/pages/Home.jsx frontend/tests/ShortenForm.test.jsx
git commit -m "feat: home page with shorten form"
```

### Task 15: Login button and protected routes

**Files:**
- Create: `frontend/src/components/LoginButton.jsx`, `frontend/src/components/RequireAuth.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `useAuth` (Task 13), `googleLoginUrl` (Task 13).
- Produces: a nav bar that shows "Sign in with Google" or the user's name + "Log out"; `RequireAuth` wraps `/dashboard` and `/links/:id/analytics` so unauthenticated visitors see a sign-in prompt instead of the page.

- [ ] **Step 1: `frontend/src/components/LoginButton.jsx`**

```javascript
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
```

- [ ] **Step 2: `frontend/src/components/RequireAuth.jsx`**

```javascript
import { useAuth } from '../context/AuthContext.jsx'
import LoginButton from './LoginButton.jsx'

export default function RequireAuth({ children }) {
  const { user, loading } = useAuth()

  if (loading) return null
  if (!user) {
    return (
      <div>
        <p>Sign in to view this page.</p>
        <LoginButton />
      </div>
    )
  }
  return children
}
```

- [ ] **Step 3: Wire both into `frontend/src/App.jsx`**

```javascript
import { Routes, Route, Link as RouterLink } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext.jsx'
import Home from './pages/Home.jsx'
import LoginButton from './components/LoginButton.jsx'
import RequireAuth from './components/RequireAuth.jsx'

function Placeholder({ label }) {
  return <p>{label}</p>
}

export default function App() {
  return (
    <AuthProvider>
      <nav>
        <RouterLink to="/">Home</RouterLink> | <RouterLink to="/dashboard">My Links</RouterLink>
        <LoginButton />
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <Placeholder label="Dashboard coming in Task 16" />
            </RequireAuth>
          }
        />
        <Route
          path="/links/:id/analytics"
          element={
            <RequireAuth>
              <Placeholder label="Analytics coming in Task 17" />
            </RequireAuth>
          }
        />
      </Routes>
    </AuthProvider>
  )
}
```

- [ ] **Step 4: Verify the build still succeeds**

Run: `cd frontend && npm run build`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/LoginButton.jsx frontend/src/components/RequireAuth.jsx frontend/src/App.jsx
git commit -m "feat: Google login button and protected route wrapper"
```

### Task 16: Dashboard (list + delete)

**Files:**
- Create: `frontend/src/pages/Dashboard.jsx`, `frontend/src/components/LinkList.jsx`
- Modify: `frontend/src/App.jsx` (swap the Dashboard placeholder for the real page)
- Test: `frontend/tests/Dashboard.test.jsx`

**Interfaces:**
- Consumes: `apiFetch` (Task 13).
- Produces: a dashboard listing the current user's links with a working delete button and a link to each one's analytics page.

- [ ] **Step 1: Write the failing test**

```javascript
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/Dashboard.test.jsx`
Expected: FAIL — `Cannot find module '../src/pages/Dashboard.jsx'`

- [ ] **Step 3: Implement `frontend/src/components/LinkList.jsx`**

```javascript
import { Link as RouterLink } from 'react-router-dom'

export default function LinkList({ links, onDelete }) {
  return (
    <ul>
      {links.map((link) => (
        <li key={link.id}>
          <a href={link.short_url}>{link.short_url}</a> → {link.target_url}{' '}
          <RouterLink to={`/links/${link.id}/analytics`}>Analytics</RouterLink>{' '}
          <button onClick={() => onDelete(link.id)}>Delete</button>
        </li>
      ))}
    </ul>
  )
}
```

- [ ] **Step 4: Implement `frontend/src/pages/Dashboard.jsx`**

```javascript
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
```

- [ ] **Step 5: Swap the placeholder in `frontend/src/App.jsx`**

```javascript
import Dashboard from './pages/Dashboard.jsx'
```
Replace `<Placeholder label="Dashboard coming in Task 16" />` with `<Dashboard />`.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/Dashboard.test.jsx`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Dashboard.jsx frontend/src/components/LinkList.jsx frontend/src/App.jsx frontend/tests/Dashboard.test.jsx
git commit -m "feat: dashboard listing and deleting the user's links"
```

### Task 17: Per-link analytics page

**Files:**
- Create: `frontend/src/pages/LinkAnalytics.jsx`
- Modify: `frontend/src/App.jsx` (swap the analytics placeholder for the real page)

**Interfaces:**
- Consumes: `apiFetch` (Task 13), `useParams` from `react-router-dom`.
- Produces: a page showing total clicks, a per-day table, and top referrers for one link.

- [ ] **Step 1: Implement `frontend/src/pages/LinkAnalytics.jsx`**

```javascript
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
```

- [ ] **Step 2: Swap the placeholder in `frontend/src/App.jsx`**

```javascript
import LinkAnalytics from './pages/LinkAnalytics.jsx'
```
Replace `<Placeholder label="Analytics coming in Task 17" />` with `<LinkAnalytics />`.

- [ ] **Step 3: Verify the build succeeds**

Run: `cd frontend && npm run build`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LinkAnalytics.jsx frontend/src/App.jsx
git commit -m "feat: per-link analytics page"
```

### Task 18: Production Docker images and full-stack verification

**Files:**
- Modify: `backend/Dockerfile` (drop `--reload` for production), `docker-compose.yml` (add dev-only overrides), `frontend/Dockerfile` (multi-stage: dev / build / nginx production)
- Create: `frontend/nginx.conf`

**Interfaces:**
- Produces: a `backend/Dockerfile` and `frontend/Dockerfile` that build clean production images (no dev servers, no bind-mounted source), while `docker-compose.yml` still runs the dev-friendly versions locally.

- [ ] **Step 1: Finalize `backend/Dockerfile` for production (no `--reload`)**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Add a dev-mode override for the backend in `docker-compose.yml`** (add this `command:` line to the existing `backend` service block from Task 1)

```yaml
  backend:
    build: ./backend
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    env_file: .env
    ports: ["8000:8000"]
    volumes: ["./backend:/app"]
    depends_on: [postgres, redis]
```

- [ ] **Step 3: Multi-stage `frontend/Dockerfile`**

```dockerfile
FROM node:20-slim AS base
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .

FROM base AS dev
CMD ["npm", "run", "dev"]

FROM base AS build
RUN npm run build

FROM nginx:1.27-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

`frontend/nginx.conf`:
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri /index.html;
    }
}
```

- [ ] **Step 4: Point `docker-compose.yml`'s frontend service at the `dev` stage** (add `target: dev` to the existing `frontend` service block from Task 1)

```yaml
  frontend:
    build:
      context: ./frontend
      target: dev
    ports: ["5173:5173"]
    volumes: ["./frontend:/app", "/app/node_modules"]
    depends_on: [backend]
```

(a plain `docker build ./frontend` with no `--target` — which is what Render will do — builds the last stage, `production`, giving the Nginx image; `docker-compose` builds the `dev` stage explicitly for local development)

- [ ] **Step 5: Full-stack smoke test**

Run:
```bash
cp .env.example .env
docker-compose up --build -d
sleep 8
curl -s http://localhost:8000/health
CODE=$(curl -s -X POST http://localhost:8000/api/links -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/smoke-test"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['code'])")
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/$CODE"
curl -s http://localhost:5173 | grep -o "<title>.*</title>"
```
Expected, in order: `{"status":"ok"}`, no output from the `CODE=` line itself, `302` for the redirect check, and `<title>URL Shortener</title>` from the frontend.

- [ ] **Step 6: Commit**

```bash
git add backend/Dockerfile docker-compose.yml frontend/Dockerfile frontend/nginx.conf
git commit -m "chore: production Docker images for backend and frontend"
```

### Task 19: Deploy to Render with Google OAuth

This task is executed manually against real Render and Google Cloud accounts — there are no automated tests, since it depends on external services and credentials only the account owner has. Render's exact dashboard labels/pricing can change, so treat plan names and free-tier availability as something to confirm in the dashboard at deploy time, not as fixed facts.

**Files:**
- Create: `render.yaml`

- [ ] **Step 1: Push the repo to GitHub**

```bash
git remote add origin <your-new-empty-github-repo-url>
git push -u origin master
```

- [ ] **Step 2: Create the `render.yaml` blueprint**

```yaml
databases:
  - name: url-shortener-db

services:
  - type: keyvalue
    name: url-shortener-redis
    ipAllowList:
      - source: 0.0.0.0/0
        description: allow all (demo project — narrow this if you keep the app running)

  - type: web
    name: url-shortener-backend
    runtime: docker
    dockerfilePath: ./backend/Dockerfile
    dockerContext: ./backend
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: url-shortener-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: url-shortener-redis
          type: keyvalue
          property: connectionString
      - key: JWT_SECRET
        sync: false
      - key: SESSION_SECRET
        sync: false
      - key: GOOGLE_CLIENT_ID
        sync: false
      - key: GOOGLE_CLIENT_SECRET
        sync: false
      - key: GOOGLE_REDIRECT_URI
        sync: false
      - key: FRONTEND_URL
        sync: false
      - key: PUBLIC_BASE_URL
        sync: false

  - type: web
    name: url-shortener-frontend
    runtime: docker
    dockerfilePath: ./frontend/Dockerfile
    dockerContext: ./frontend
```

Commit it: `git add render.yaml && git commit -m "chore: add Render blueprint"` and push.

- [ ] **Step 3: Create the Google OAuth credentials**

In the Google Cloud Console: create a project, configure the OAuth consent screen (External, test/publish as needed), then create an OAuth Client ID of type "Web application". Add an authorized redirect URI of `https://url-shortener-backend.onrender.com/api/auth/google/callback` (the backend's URL is predictable from the `name` in `render.yaml` above — confirm it matches exactly once the service exists, in case Render appended a suffix). Save the generated Client ID and Client Secret.

- [ ] **Step 4: Deploy the blueprint on Render**

In the Render dashboard: New → Blueprint → connect the GitHub repo → Render reads `render.yaml` and creates the database, the Key Value instance, and both web services. `DATABASE_URL` and `REDIS_URL` populate automatically; for every other backend env var marked `sync: false`, set the value manually in the backend service's Environment tab:
- `JWT_SECRET`, `SESSION_SECRET`: any long random string (e.g. `openssl rand -hex 32`).
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: from Step 3.
- `GOOGLE_REDIRECT_URI`: `https://url-shortener-backend.onrender.com/api/auth/google/callback`.
- `PUBLIC_BASE_URL`: `https://url-shortener-backend.onrender.com`.
- `FRONTEND_URL`: `https://url-shortener-frontend.onrender.com` (confirm the real assigned URL in the dashboard first).

- [ ] **Step 5: Bake the backend URL into the frontend build**

Create `frontend/.env.production`:
```
VITE_API_BASE_URL=https://url-shortener-backend.onrender.com
```
(Render's Docker builds don't support passing custom build args from `render.yaml`, and this value isn't a secret, so committing it as a build-time `.env.production` file is the simplest way to get it into the Vite bundle. If the confirmed backend URL differs from the one assumed here, update this file and redeploy.)

```bash
git add frontend/.env.production
git commit -m "chore: point production frontend build at the deployed backend URL"
git push
```

- [ ] **Step 6: Run the database migration against the deployed Postgres**

From your machine, using the **external** connection string shown in the Render Postgres dashboard:
```bash
cd backend
DATABASE_URL="<external-connection-string-from-render-dashboard>" alembic upgrade head
```
Expected: Alembic reports it applied revision `0001`.

- [ ] **Step 7: Verify the live app end-to-end**

Visit `https://url-shortener-frontend.onrender.com`, shorten a URL, confirm the short link redirects, sign in with Google, confirm the link now appears on the dashboard tied to your account, and confirm its analytics page shows at least one click.

- [ ] **Step 8: Commit any final fixes discovered during verification, then record the live demo link**

```bash
git add -A
git commit -m "chore: deployment fixes from Render verification pass"
```

