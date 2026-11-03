"""Зависимости FastAPI для текущего пользователя."""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import User


class AuthRequired(Exception):
    """Пользователь не вошёл — обработчик перенаправит на логин."""

    def __init__(self, next_url: str = "/surveys") -> None:
        self.next_url = next_url
        super().__init__("auth required")


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if user is None:
        request.session.pop("user_id", None)
    return user


def require_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    user = get_current_user(request, db)
    if user is None:
        raise AuthRequired(next_url=request.url.path)
    return user
