from __future__ import annotations

from sqlalchemy import select

from database.db import SessionLocal
from database.models import Survey
from tests.helpers import create_survey, logout, register


def _survey_from_location(location: str) -> int:
    return int(location.rstrip("/").rsplit("/", 1)[1])


def test_create_survey_and_unique_slug(client):
    register(client)
    first = create_survey(client, title="Первый опрос")
    second = create_survey(client, title="Второй опрос")
    assert first.status_code == 303
    assert second.status_code == 303

    with SessionLocal() as db:
        surveys = db.scalars(select(Survey).order_by(Survey.id)).all()
        assert len(surveys) == 2
        assert surveys[0].slug != surveys[1].slug
        assert len(surveys[0].slug) == 8
        assert len(surveys[0].questions) == 2


def test_new_survey_page_prefills_template(client):
    register(client)
    response = client.get("/surveys/new?template=knowledge_test")
    assert response.status_code == 200
    assert "Тест по основам Python" in response.text
    assert "Что такое Python?" in response.text
    assert "верный" in response.text


def test_delete_survey(client):
    register(client)
    created = create_survey(client)
    survey_id = _survey_from_location(created.headers["location"])

    detail = client.get(f"/surveys/{survey_id}")
    response = client.post(
        f"/surveys/{survey_id}/delete",
        data={"csrf_token": _csrf_from_page(detail.text)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with SessionLocal() as db:
        assert db.get(Survey, survey_id) is None


def test_owner_cannot_open_foreign_survey(client):
    register(client, email="first@example.com")
    created = create_survey(client)
    survey_id = _survey_from_location(created.headers["location"])
    logout(client)
    register(client, email="second@example.com")

    assert client.get(f"/surveys/{survey_id}").status_code == 404
    assert client.get(f"/surveys/{survey_id}/stats").status_code == 404


def _csrf_from_page(html: str) -> str:
    import re

    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)
