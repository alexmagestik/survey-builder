"""Бизнес-логика опросов: создание, валидация, сохранение ответов."""

from __future__ import annotations

import re
import secrets
from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import (
    MAX_OPTION_TEXT,
    MAX_OPTIONS,
    MAX_QUESTION_TEXT,
    MAX_QUESTIONS,
    MAX_RESPONDENT_NAME,
    MAX_TEXT_ANSWER,
)
from database.models import Answer, Option, Question, Response, Survey, User
from surveys.template_loader import load_template, template_to_form

SLUG_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
SLUG_LENGTH = 8


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def generate_slug(db: Session) -> str:
    for _ in range(20):
        slug = "".join(secrets.choice(SLUG_ALPHABET) for _ in range(SLUG_LENGTH))
        if db.scalar(select(Survey.id).where(Survey.slug == slug)) is None:
            return slug
    raise RuntimeError("Не удалось сгенерировать уникальную ссылку.")


def _make_survey(
    db: Session,
    user: User,
    title: str,
    description: str,
    questions: list[dict],
    scoring_enabled: bool,
    template_key: str | None,
) -> Survey:
    survey = Survey(
        user_id=user.id,
        slug=generate_slug(db),
        title=title,
        description=description,
        template_key=template_key,
        scoring_enabled=scoring_enabled,
    )
    for q_position, question_data in enumerate(questions):
        question = Question(
            text=question_data["text"],
            type=question_data["type"],
            required=bool(question_data.get("required")),
            allow_other=bool(question_data.get("allow_other")),
            position=q_position,
        )
        for o_position, option_data in enumerate(question_data.get("options", [])):
            question.options.append(
                Option(
                    text=option_data["text"],
                    position=o_position,
                    is_correct=bool(option_data.get("correct")) if scoring_enabled else False,
                )
            )
        survey.questions.append(question)
    return survey


def create_survey(
    db: Session,
    user: User,
    title: str,
    description: str,
    questions: list[dict],
    scoring_enabled: bool = False,
    template_key: str | None = None,
) -> Survey:
    for _ in range(5):
        survey = _make_survey(
            db,
            user,
            title=title,
            description=description,
            questions=questions,
            scoring_enabled=scoring_enabled,
            template_key=template_key,
        )
        db.add(survey)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(survey)
        return survey
    raise RuntimeError("Не удалось сохранить опрос: попробуйте ещё раз.")


def create_survey_from_template(db: Session, user: User, key: str) -> Survey:
    template = load_template(key)
    form = template_to_form(template)
    return create_survey(
        db,
        user,
        title=form["title"],
        description=form["description"],
        questions=form["questions"],
        scoring_enabled=form["scoring_enabled"],
        template_key=key,
    )


def get_owned_survey(db: Session, survey_id: int, user: User) -> Survey:
    survey = db.scalar(
        select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id)
    )
    if survey is None:
        raise HTTPException(status_code=404, detail="Опрос не найден.")
    return survey


def get_active_survey_by_slug(db: Session, slug: str) -> Survey:
    survey = db.scalar(
        select(Survey).where(Survey.slug == slug, Survey.is_active.is_(True))
    )
    if survey is None:
        raise HTTPException(status_code=404, detail="Опрос не найден или закрыт.")
    return survey


def list_user_surveys(db: Session, user_id: int) -> list[dict]:
    rows = db.execute(
        select(Survey, func.count(Response.id).label("response_count"))
        .outerjoin(Response, Response.survey_id == Survey.id)
        .where(Survey.user_id == user_id)
        .group_by(Survey.id)
        .order_by(Survey.created_at.desc())
    ).all()
    return [{"survey": survey, "response_count": count} for survey, count in rows]


def get_response_count(db: Session, survey_id: int) -> int:
    return (
        db.scalar(select(func.count(Response.id)).where(Response.survey_id == survey_id))
        or 0
    )


def parse_builder_form(form: Any) -> tuple[dict, list[str]]:
    """Разбирает поля конструктора questions-{i}-options-{j}-*."""
    question_indices: set[int] = set()
    for key in form.keys():
        match = re.match(r"^questions-(\d+)-", key)
        if match:
            question_indices.add(int(match.group(1)))

    questions: list[dict] = []
    for q_index in sorted(question_indices):
        question = {
            "text": _to_str(form.get(f"questions-{q_index}-text")).strip(),
            "type": _to_str(form.get(f"questions-{q_index}-type")) or "single",
            "required": _to_str(form.get(f"questions-{q_index}-required")) == "1",
            "allow_other": _to_str(form.get(f"questions-{q_index}-allow-other")) == "1",
            "options": [],
        }

        option_indices: set[int] = set()
        option_prefix = f"questions-{q_index}-options-"
        for key in form.keys():
            if key.startswith(option_prefix):
                match = re.match(
                    rf"^questions-{q_index}-options-(\d+)-", key
                )
                if match:
                    option_indices.add(int(match.group(1)))

        for o_index in sorted(option_indices):
            option_text = _to_str(
                form.get(f"questions-{q_index}-options-{o_index}-text")
            ).strip()
            if not option_text:
                continue
            question["options"].append(
                {
                    "text": option_text,
                    "correct": _to_str(
                        form.get(f"questions-{q_index}-options-{o_index}-correct")
                    )
                    == "1",
                }
            )
        questions.append(question)

    data = {
        "title": _to_str(form.get("title")).strip(),
        "description": _to_str(form.get("description")).strip(),
        "scoring_enabled": _to_str(form.get("scoring_enabled")) == "1",
        "questions": questions,
    }
    return data, validate_survey_input(data)


def validate_survey_input(data: dict) -> list[str]:
    errors: list[str] = []
    title = data.get("title", "")
    description = data.get("description", "")
    questions = data.get("questions", [])
    scoring = bool(data.get("scoring_enabled"))

    if not 3 <= len(title) <= 200:
        errors.append("Название опроса должно быть от 3 до 200 символов.")
    if len(description) > 2000:
        errors.append("Описание не должно превышать 2000 символов.")
    if not 1 <= len(questions) <= MAX_QUESTIONS:
        errors.append(f"Добавьте от 1 до {MAX_QUESTIONS} вопросов.")
        return errors

    scorable_questions = 0
    for index, question in enumerate(questions, start=1):
        text = question.get("text", "")
        q_type = question.get("type")
        if not 1 <= len(text) <= MAX_QUESTION_TEXT:
            errors.append(
                f"Вопрос №{index}: текст должен быть от 1 до {MAX_QUESTION_TEXT} символов."
            )
        if q_type not in {"single", "multiple", "text"}:
            errors.append(f"Вопрос №{index}: неизвестный тип.")
            continue

        if q_type == "text":
            question["options"] = []
            question["allow_other"] = False
            continue

        scorable_questions += 1
        options = question.get("options", [])
        if not 2 <= len(options) <= MAX_OPTIONS:
            errors.append(
                f"Вопрос №{index}: нужно от 2 до {MAX_OPTIONS} вариантов ответа."
            )
        seen: set[str] = set()
        for option in options:
            option_text = option.get("text", "")
            if not 1 <= len(option_text) <= MAX_OPTION_TEXT:
                errors.append(
                    f"Вопрос №{index}: вариант должен быть от 1 до {MAX_OPTION_TEXT} символов."
                )
            if option_text in seen:
                errors.append(f"Вопрос №{index}: вариант «{option_text}» повторяется.")
            seen.add(option_text)
        if scoring:
            correct_count = sum(1 for o in options if o.get("correct"))
            if correct_count == 0:
                errors.append(
                    f"Вопрос №{index}: отметьте хотя бы один правильный вариант."
                )
            if q_type == "single" and correct_count > 1:
                errors.append(
                    f"Вопрос №{index}: для вопроса с одним вариантом "
                    "должен быть ровно один правильный ответ."
                )

    if scoring and scorable_questions == 0:
        errors.append("В тесте должен быть хотя бы один вопрос с вариантами.")
    return errors


def validate_submission(survey: Survey, form: Any) -> tuple[str, list[dict], list[str]]:
    errors: list[str] = []
    name = _to_str(form.get("respondent_name")).strip()
    if not name:
        errors.append("Укажите имя: без него нельзя отправить ответы.")
    elif len(name) > MAX_RESPONDENT_NAME:
        errors.append(f"Имя не должно превышать {MAX_RESPONDENT_NAME} символов.")

    drafts: list[dict] = []
    for question in survey.questions:
        if question.type == "text":
            value = _to_str(form.get(f"q_{question.id}")).strip()
            if len(value) > MAX_TEXT_ANSWER:
                errors.append(
                    f"Ответ на вопрос «{question.text}» слишком длинный "
                    f"(максимум {MAX_TEXT_ANSWER} символов)."
                )
                continue
            if question.required and not value:
                errors.append(f"Ответьте на вопрос «{question.text}».")
            if value:
                drafts.append(
                    {
                        "question_id": question.id,
                        "option_id": None,
                        "text_value": value,
                    }
                )
            continue

        raw_values = form.getlist(f"q_{question.id}") if hasattr(form, "getlist") else []
        raw_values = [_to_str(v) for v in raw_values]
        other_selected = "other" in raw_values
        other_text = _to_str(form.get(f"q_{question.id}_other")).strip()
        if len(other_text) > MAX_OPTION_TEXT:
            errors.append(
                f"Свой вариант в вопросе «{question.text}» слишком длинный."
            )

        selected_ids: list[int] = []
        for raw in raw_values:
            if raw == "other":
                continue
            try:
                option_id = int(raw)
            except (TypeError, ValueError):
                errors.append(f"Некорректный вариант в вопросе «{question.text}».")
                continue
            option = next((o for o in question.options if o.id == option_id), None)
            if option is None:
                errors.append(f"Вариант не относится к вопросу «{question.text}».")
                continue
            if option_id not in selected_ids:
                selected_ids.append(option_id)

        # Если текст «Своего варианта» заполнен, а обычные варианты не выбраны,
        # считаем «Другое» выбранным. Это защищает от потери ответа, когда
        # пользователь ввёл текст, но забыл отметить пункт «Другое».
        if other_text and question.allow_other and not selected_ids:
            other_selected = True

        if question.type == "single" and len(selected_ids) > 1:
            errors.append(f"В вопросе «{question.text}» можно выбрать только один вариант.")
        if question.type == "single" and selected_ids and other_selected:
            errors.append(
                f"В вопросе «{question.text}» нельзя одновременно выбрать вариант и «Другое»."
            )
        if other_selected and not other_text:
            errors.append(f"Укажите свой вариант в вопросе «{question.text}».")
        if question.required and not selected_ids and not (other_selected and other_text):
            errors.append(f"Ответьте на вопрос «{question.text}».")

        for option_id in selected_ids:
            drafts.append(
                {
                    "question_id": question.id,
                    "option_id": option_id,
                    "text_value": None,
                }
            )
        if other_selected and other_text:
            drafts.append(
                {
                    "question_id": question.id,
                    "option_id": None,
                    "text_value": other_text,
                }
            )

    return name, drafts, errors


def compute_score(survey: Survey, drafts: list[dict]) -> tuple[int | None, int | None]:
    if not survey.scoring_enabled:
        return None, None

    selected: dict[int, set[int]] = defaultdict(set)
    for draft in drafts:
        if draft.get("option_id") is not None:
            selected[draft["question_id"]].add(draft["option_id"])

    score = 0
    max_score = 0
    for question in survey.questions:
        if question.type == "text":
            continue
        max_score += 1
        correct_ids = {option.id for option in question.options if option.is_correct}
        if correct_ids and selected.get(question.id, set()) == correct_ids:
            score += 1
    return score, max_score


def save_response(
    db: Session, survey: Survey, respondent_name: str, drafts: list[dict]
) -> Response:
    score, max_score = compute_score(survey, drafts)
    response = Response(
        survey_id=survey.id,
        respondent_name=respondent_name,
        score=score,
        max_score=max_score,
    )
    for draft in drafts:
        response.answers.append(
            Answer(
                question_id=draft["question_id"],
                option_id=draft.get("option_id"),
                text_value=draft.get("text_value"),
            )
        )
    db.add(response)
    db.commit()
    db.refresh(response)
    return response
