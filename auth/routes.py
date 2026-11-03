"""Регистрация, вход и выход создателей."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.security import (
    hash_password,
    is_valid_email,
    login_user,
    logout_user,
    normalize_email,
    safe_next,
    validate_password,
    verify_csrf,
    verify_password,
)
from database.db import get_db
from database.models import User
from web import flash, render

router = APIRouter(prefix="/auth", tags=["auth"])


def _value(form, key: str) -> str:
    value = form.get(key)
    return "" if value is None else str(value)


@router.get("/register", name="register")
def register_page(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    if user:
        return RedirectResponse("/surveys", status_code=303)
    return render(request, "auth/register.html", {"current_user": user, "email": ""})


@router.post("/register", name="register_submit")
async def register_submit(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if user:
        return RedirectResponse("/surveys", status_code=303)

    form = await request.form()
    verify_csrf(request, _value(form, "csrf_token"))

    email = normalize_email(_value(form, "email"))
    password = _value(form, "password")
    password_confirm = _value(form, "password_confirm")

    errors: list[str] = []
    if not is_valid_email(email):
        errors.append("Укажите корректный email.")
    password_error = validate_password(password)
    if password_error:
        errors.append(password_error)
    if password != password_confirm:
        errors.append("Пароли не совпадают.")
    if db.scalar(select(User).where(User.email == email)) is not None:
        errors.append("Пользователь с таким email уже зарегистрирован.")

    if errors:
        return render(
            request,
            "auth/register.html",
            {"current_user": None, "email": email, "errors": errors},
            status_code=400,
        )

    new_user = User(email=email, password_hash=hash_password(password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    login_user(request, new_user.id)
    flash(request, "Регистрация завершена. Добро пожаловать!", "success")
    return RedirectResponse("/surveys", status_code=303)


@router.get("/login", name="login")
def login_page(
    request: Request,
    next: str | None = None,
    user: User | None = Depends(get_current_user),
):
    if user:
        return RedirectResponse("/surveys", status_code=303)
    return render(
        request,
        "auth/login.html",
        {"current_user": None, "email": "", "next_url": safe_next(next, "")},
    )


@router.post("/login", name="login_submit")
async def login_submit(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    verify_csrf(request, _value(form, "csrf_token"))

    email = normalize_email(_value(form, "email"))
    password = _value(form, "password")
    next_url = safe_next(_value(form, "next_url"), "/surveys")

    errors: list[str] = []
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        errors.append("Неверный email или пароль.")

    if errors:
        return render(
            request,
            "auth/login.html",
            {
                "current_user": None,
                "email": email,
                "errors": errors,
                "next_url": next_url,
            },
            status_code=400,
        )

    login_user(request, user.id)
    flash(request, "Вы вошли в систему.", "success")
    return RedirectResponse(next_url, status_code=303)


@router.post("/logout", name="logout")
async def logout(request: Request):
    form = await request.form()
    verify_csrf(request, _value(form, "csrf_token"))
    logout_user(request)
    flash(request, "Вы вышли из системы.", "info")
    return RedirectResponse("/", status_code=303)
