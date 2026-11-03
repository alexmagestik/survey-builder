from __future__ import annotations

import re


def csrf(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match, response.text[:1000]
    return match.group(1)


def register(client, email: str = "user@example.com", password: str = "password123"):
    response = client.get("/auth/register")
    return client.post(
        "/auth/register",
        data={
            "csrf_token": csrf(response),
            "email": email,
            "password": password,
            "password_confirm": password,
        },
        follow_redirects=False,
    )


def login(client, email: str = "user@example.com", password: str = "password123"):
    response = client.get("/auth/login")
    return client.post(
        "/auth/login",
        data={
            "csrf_token": csrf(response),
            "email": email,
            "password": password,
        },
        follow_redirects=False,
    )


def logout(client):
    response = client.get("/surveys")
    return client.post(
        "/auth/logout",
        data={"csrf_token": csrf(response)},
        follow_redirects=False,
    )


def create_survey(
    client,
    title: str = "Тестовый опрос",
    scoring: bool = False,
    allow_other: bool = False,
):
    response = client.get("/surveys/new")
    data = {
        "csrf_token": csrf(response),
        "title": title,
        "description": "Описание тестового опроса",
        "questions-0-text": "Ваш любимый цвет?",
        "questions-0-type": "single",
        "questions-0-required": "1",
        "questions-0-options-0-text": "Красный",
        "questions-0-options-1-text": "Синий",
        "questions-1-text": "Комментарий",
        "questions-1-type": "text",
        "questions-1-required": "",
    }
    if scoring:
        data["scoring_enabled"] = "1"
        data["questions-0-options-0-correct"] = "1"
    if allow_other:
        data["questions-0-allow-other"] = "1"
    return client.post("/surveys", data=data, follow_redirects=False)


def submit_survey(client, slug: str, payload: dict):
    response = client.get(f"/survey/{slug}")
    data = {"csrf_token": csrf(response), **payload}
    return client.post(f"/survey/{slug}", data=data, follow_redirects=False)
