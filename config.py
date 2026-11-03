"""Настройки приложения.

Значения читаются из переменных окружения и файла .env (если он есть).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# SQLite-файл лежит рядом с пакетом database
(BASE_DIR / "database").mkdir(exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'database' / 'survey.db'}",
)

DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@example.com")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo12345")

SESSION_COOKIE = "survey_session"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Ограничения валидации
MAX_RESPONDENT_NAME = 120
MAX_QUESTION_TEXT = 500
MAX_OPTION_TEXT = 200
MAX_TEXT_ANSWER = 2000
MAX_QUESTIONS = 50
MAX_OPTIONS = 20
