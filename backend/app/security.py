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
