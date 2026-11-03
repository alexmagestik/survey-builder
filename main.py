"""Точка входа приложения Survey Builder."""

from __future__ import annotations

from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from analytics.routes import router as analytics_router
from auth.dependencies import AuthRequired, get_current_user
from auth.routes import router as auth_router
from config import SECRET_KEY, SESSION_COOKIE, STATIC_DIR
from database import models as _models  # noqa: F401  (регистрация моделей)
from database.db import Base, engine
from database.models import User
from surveys.routes import router as surveys_router
from surveys.template_loader import list_templates
from web import render


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Survey Builder", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=SESSION_COOKIE,
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(auth_router)
app.include_router(surveys_router)
app.include_router(analytics_router)


@app.exception_handler(AuthRequired)
async def auth_required_handler(_request: Request, exc: AuthRequired):
    return RedirectResponse(
        f"/auth/login?next={quote(exc.next_url, safe='/')}", status_code=303
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code in (400, 403, 404):
        return render(
            request,
            f"errors/{exc.status_code}.html",
            {"detail": exc.detail},
            status_code=exc.status_code,
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/v1/models", include_in_schema=False)
def models_probe():
    """Служебная заглушка для клиентов, проверяющих OpenAI-совместимый API."""
    return {"object": "list", "data": []}


@app.get("/", name="index")
def index(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    if user:
        return RedirectResponse("/surveys", status_code=303)
    return render(
        request,
        "index.html",
        {"current_user": user, "templates_list": list_templates()},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
