from __future__ import annotations

from sqlalchemy import func, select

from database.db import SessionLocal
from database.models import Answer, Option, Question, Response, Survey
from tests.helpers import create_survey, register, submit_survey


def _survey_parts(survey_id: int):
    with SessionLocal() as db:
        survey = db.get(Survey, survey_id)
        questions = db.scalars(
            select(Question)
            .where(Question.survey_id == survey.id)
            .order_by(Question.position)
        ).all()
        options = db.scalars(
            select(Option)
            .where(Option.question_id == questions[0].id)
            .order_by(Option.position)
        ).all()
        return survey.slug, questions[0].id, questions[1].id, options[0].id


def _created_id(response) -> int:
    return int(response.headers["location"].rstrip("/").rsplit("/", 1)[1])


def test_public_form_submit_saves_answers(client):
    register(client)
    created = create_survey(client)
    slug, q0_id, q1_id, option_id = _survey_parts(_created_id(created))

    page = client.get(f"/survey/{slug}")
    assert page.status_code == 200
    assert "Ваше имя" in page.text

    response = submit_survey(
        client,
        slug,
        {
            "respondent_name": "Анна",
            f"q_{q0_id}": str(option_id),
            f"q_{q1_id}": "Всё понравилось",
        },
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("/thanks")

    with SessionLocal() as db:
        survey = db.scalar(select(Survey).where(Survey.slug == slug))
        assert db.scalar(
            select(func.count(Response.id)).where(Response.survey_id == survey.id)
        ) == 1
        assert db.scalar(
            select(func.count(Answer.id))
            .join(Response, Answer.response_id == Response.id)
            .where(Response.survey_id == survey.id)
        ) == 2
        response_row = db.scalar(
            select(Response).where(Response.survey_id == survey.id)
        )
        assert response_row.respondent_name == "Анна"

    thanks = client.get(response.headers["location"])
    assert thanks.status_code == 200
    assert "Спасибо" in thanks.text


def test_required_name_is_validated(client):
    register(client)
    created = create_survey(client)
    slug, q0_id, _, option_id = _survey_parts(_created_id(created))

    response = submit_survey(
        client,
        slug,
        {"respondent_name": "", f"q_{q0_id}": str(option_id)},
    )
    assert response.status_code == 400
    assert "Укажите имя" in response.text


def test_required_question_is_validated(client):
    register(client)
    created = create_survey(client)
    slug, _, _, _ = _survey_parts(_created_id(created))

    response = submit_survey(client, slug, {"respondent_name": "Иван"})
    assert response.status_code == 400
    assert "Ответьте на вопрос" in response.text


def test_tampered_option_is_rejected(client):
    register(client)
    created = create_survey(client)
    slug, q0_id, _, _ = _survey_parts(_created_id(created))
    other = create_survey(client, title="Другой опрос")
    _, _, _, other_option_id = _survey_parts(_created_id(other))

    response = submit_survey(
        client,
        slug,
        {"respondent_name": "Иван", f"q_{q0_id}": str(other_option_id)},
    )
    assert response.status_code == 400
    assert "не относится" in response.text


def test_inactive_survey_returns_404(client):
    register(client)
    created = create_survey(client)
    survey_id = _created_id(created)
    slug, _, _, _ = _survey_parts(survey_id)

    with SessionLocal() as db:
        survey = db.get(Survey, survey_id)
        survey.is_active = False
        db.commit()

    assert client.get(f"/survey/{slug}").status_code == 404


def test_other_field_is_hidden_until_other_selected(client):
    register(client)
    created = create_survey(client, allow_other=True)
    slug, _, _, _ = _survey_parts(_created_id(created))

    page = client.get(f"/survey/{slug}")
    assert page.status_code == 200
    assert "data-other-field hidden" in page.text
    assert "Ваш вариант" in page.text


def test_other_text_without_checkbox_is_accepted(client):
    register(client)
    created = create_survey(client, allow_other=True)
    survey_id = _created_id(created)
    slug, q0_id, q1_id, _ = _survey_parts(survey_id)

    response = submit_survey(
        client,
        slug,
        {
            "respondent_name": "Анна",
            f"q_{q0_id}_other": "Мятный",
            f"q_{q1_id}": "",
        },
    )
    assert response.status_code == 303

    with SessionLocal() as db:
        survey = db.scalar(select(Survey).where(Survey.slug == slug))
        row = db.scalar(select(Response).where(Response.survey_id == survey.id))
        values = [
            answer.text_value
            for answer in row.answers
            if answer.question_id == q0_id
        ]
        assert values == ["Мятный"]


def test_other_selected_without_text_is_rejected(client):
    register(client)
    created = create_survey(client, allow_other=True)
    slug, q0_id, _, _ = _survey_parts(_created_id(created))

    response = submit_survey(
        client,
        slug,
        {"respondent_name": "Анна", f"q_{q0_id}": "other"},
    )
    assert response.status_code == 400
    assert "Укажите свой вариант" in response.text
    assert "data-other-field hidden" not in response.text


def test_quiz_scores_correct_answers(client):
    register(client)
    created = create_survey(client, title="Мини-тест", scoring=True)
    survey_id = _created_id(created)
    slug, q0_id, q1_id, correct_option_id = _survey_parts(survey_id)

    response = submit_survey(
        client,
        slug,
        {
            "respondent_name": "Отличник",
            f"q_{q0_id}": str(correct_option_id),
            f"q_{q1_id}": "Комментарий",
        },
    )
    assert response.status_code == 303
    thanks = client.get(response.headers["location"])
    assert "1 из 1" in thanks.text

    with SessionLocal() as db:
        survey = db.scalar(select(Survey).where(Survey.slug == slug))
        row = db.scalar(select(Response).where(Response.survey_id == survey.id))
        assert row.score == 1
        assert row.max_score == 1
