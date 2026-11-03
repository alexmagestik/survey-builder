"""Загрузка Jinja2-шаблонов опросов из templates/survey_templates."""

from __future__ import annotations

import json

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from config import TEMPLATES_DIR
from surveys.schemas import SurveyTemplate

SURVEY_TEMPLATES_DIR = TEMPLATES_DIR / "survey_templates"

_env = Environment(
    loader=FileSystemLoader(str(SURVEY_TEMPLATES_DIR)),
    autoescape=False,
    keep_trailing_newline=True,
)

TEMPLATE_META: dict[str, dict[str, str]] = {
    "satisfaction": {
        "name": "Опрос удовлетворённости",
        "description": "CSAT: общая оценка, что понравилось и что улучшить.",
        "icon": "😊",
    },
    "post_purchase": {
        "name": "Анкета после покупки",
        "description": "Доставка, качество товара, проблемы и комментарии.",
        "icon": "📦",
    },
    "knowledge_test": {
        "name": "Тестирование знаний",
        "description": "Тест по основам Python с автоматическим подсчётом баллов.",
        "icon": "🎓",
    },
}


def load_template(key: str) -> SurveyTemplate:
    if key not in TEMPLATE_META:
        raise KeyError(f"Неизвестный шаблон: {key}")
    try:
        source = _env.get_template(f"{key}.json.j2").render()
    except TemplateNotFound as exc:
        raise KeyError(f"Файл шаблона не найден: {key}") from exc

    data = json.loads(source)
    template = SurveyTemplate.model_validate(data)
    if template.key != key:
        raise ValueError(
            f"Ключ внутри шаблона ({template.key}) не совпадает с именем файла ({key})."
        )
    return template


def list_templates() -> list[dict]:
    result: list[dict] = []
    for key, meta in TEMPLATE_META.items():
        template = load_template(key)
        result.append(
            {
                "key": key,
                "name": meta["name"],
                "description": meta["description"],
                "icon": meta["icon"],
                "question_count": len(template.questions),
                "scoring": template.scoring,
            }
        )
    return result


def template_to_form(template: SurveyTemplate) -> dict:
    return {
        "title": template.title,
        "description": template.description,
        "scoring_enabled": template.scoring,
        "questions": [
            {
                "text": question.text,
                "type": question.type,
                "required": question.required,
                "allow_other": question.allow_other,
                "options": [
                    {"text": option.text, "correct": option.correct}
                    for option in question.options
                ],
            }
            for question in template.questions
        ],
    }


def blank_form() -> dict:
    return {
        "title": "",
        "description": "",
        "scoring_enabled": False,
        "questions": [
            {
                "text": "",
                "type": "single",
                "required": True,
                "allow_other": False,
                "options": [
                    {"text": "", "correct": False},
                    {"text": "", "correct": False},
                ],
            }
        ],
    }
