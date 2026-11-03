"""Пароли, CSRF и работа с сессией."""

from __future__ import annotations

import re
import secrets

import bcrypt
from fastapi import HTTPException, Request

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def validate_password(password: str) -> str | None:
    """Возвращает текст ошибки или None."""
    if len(password) < 8:
        return "Пароль должен быть не короче 8 символов."
    if len(password.encode("utf-8")) > 72:
        return "Пароль слишком длинный (максимум 72 байта)."
    return None


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email)) and len(email) <= 255


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def verify_csrf(request: Request, token: str | None) -> None:
    expected = request.session.get("csrf_token")
    if not expected or not token or not secrets.compare_digest(str(expected), str(token)):
        raise HTTPException(status_code=400, detail="Недействительный CSRF-токен.")


def login_user(request: Request, user_id: int) -> None:
    request.session["user_id"] = user_id


def logout_user(request: Request) -> None:
    request.session.clear()


def safe_next(url: str | None, default: str = "/surveys") -> str:
    """Не даём увести пользователя на внешний сайт через ?next=."""
    if not url:
        return default
    if not url.startswith("/") or url.startswith("//"):
        return default
    return url
