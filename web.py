"""Общие помощники для HTML-страниц: Jinja2, flash-сообщения, CSRF."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from auth.security import get_csrf_token
from config import TEMPLATES_DIR

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def ru_plural(number: int, one: str, few: str, many: str) -> str:
    """Русское склонение: 1 вопрос, 2 вопроса, 5 вопросов."""
    number = abs(int(number))
    if number % 10 == 1 and number % 100 != 11:
        return one
    if number % 10 in (2, 3, 4) and number % 100 not in (12, 13, 14):
        return few
    return many


templates.env.globals["plural"] = ru_plural


def flash(request: Request, message: str, category: str = "info") -> None:
    request.session.setdefault("_flashes", []).append(
        {"message": message, "category": category}
    )


def pop_flashes(request: Request) -> list[dict[str, str]]:
    return request.session.pop("_flashes", [])


def render(
    request: Request,
    template_name: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
):
    ctx: dict[str, Any] = {
        "request": request,
        "csrf_token": get_csrf_token(request),
        "current_user": None,
        "flashes": pop_flashes(request),
    }
    if context:
        ctx.update(context)
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=ctx,
        status_code=status_code,
    )
