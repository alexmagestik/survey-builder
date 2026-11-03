from __future__ import annotations

from sqlalchemy import select

from database.db import SessionLocal
from database.models import Question
from tests.helpers import create_survey, logout, register, submit_survey


def _created_id(response) -> int:
    return int(response.headers["location"].rstrip("/").rsplit("/", 1)[1])


def test_stats_show_responses_and_distribution(client):
    register(client)
    created = create_survey(client)
    survey_id = _created_id(created)

    from tests.test_public import _survey_parts

    slug, q0_id, q1_id, option_id = _survey_parts(survey_id)
    for name in ("Анна", "Иван"):
        submit_survey(
            client,
            slug,
            {
                "respondent_name": name,
                f"q_{q0_id}": str(option_id),
                f"q_{q1_id}": "Комментарий",
            },
        )

    stats = client.get(f"/surveys/{survey_id}/stats")
    assert stats.status_code == 200
    assert "2" in stats.text
    assert "Красный" in stats.text
    assert "Анна" in stats.text
    assert "Иван" in stats.text


def test_stats_are_owner_only(client):
    register(client, email="owner@example.com")
    created = create_survey(client)
    survey_id = _created_id(created)
    logout(client)
    register(client, email="intruder@example.com")

    assert client.get(f"/surveys/{survey_id}/stats").status_code == 404


def test_quiz_stats_show_average_score(client):
    register(client)
    created = create_survey(client, title="Тест", scoring=True)
    survey_id = _created_id(created)

    from tests.test_public import _survey_parts

    slug, q0_id, q1_id, correct_option_id = _survey_parts(survey_id)

    # Правильный ответ
    submit_survey(
        client,
        slug,
        {
            "respondent_name": "Отличник",
            f"q_{q0_id}": str(correct_option_id),
            f"q_{q1_id}": "",
        },
    )
    # Неправильный ответ
    with SessionLocal() as db:
        question = db.get(Question, q0_id)
        wrong = next(o for o in question.options if not o.is_correct)
        wrong_id = wrong.id

    submit_survey(
        client,
        slug,
        {
            "respondent_name": "Новичок",
            f"q_{q0_id}": str(wrong_id),
            f"q_{q1_id}": "",
        },
    )

    stats = client.get(f"/surveys/{survey_id}/stats")
    assert stats.status_code == 200
    assert "Средний балл" in stats.text
    assert "0.5" in stats.text
