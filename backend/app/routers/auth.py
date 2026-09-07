from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
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
    # samesite="none" (with secure=True, required alongside it) is needed
    # because the frontend (vercel.app) and backend (onrender.com) are
    # different sites — any fetch() the frontend makes to the API is a
    # cross-site request, and browsers only attach samesite="lax"/"strict"
    # cookies to top-level navigations, never to cross-site fetch/XHR calls
    # even with credentials: 'include'. Without this, login would appear to
    # silently fail: the cookie gets set but is never sent back.
    response.set_cookie(
        "access_token", jwt_token, httponly=True, samesite="none", secure=True, max_age=7 * 24 * 3600
    )
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name}


@router.post("/logout")
def logout():
    # A plain JSON response, not a redirect: the frontend calls this via
    # fetch(), which auto-follows redirects — a redirect back to the
    # (static, non-API) frontend origin has nothing to serve for a POST
    # and returns 405, making logout appear to silently do nothing.
    response = JSONResponse(content={"status": "logged out"})
    response.delete_cookie("access_token", httponly=True, samesite="none", secure=True)
    return response
