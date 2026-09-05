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
