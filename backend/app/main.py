from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, links, redirect

app = FastAPI(title="URL Shortener")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.include_router(auth.router)
app.include_router(links.router)
app.include_router(redirect.router)


@app.get("/health")
def health():
    return {"status": "ok"}
