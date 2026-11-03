"""Демо-данные: пользователь, три опроса из шаблонов и ответы.

Запуск:
    python -m database.seed
    python -m database.seed --reset
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from auth.security import hash_password
from config import DEMO_EMAIL, DEMO_PASSWORD
from database.db import Base, SessionLocal, engine
from database.models import Answer, Response, Survey, User
from surveys.service import compute_score, create_survey_from_template
from surveys.template_loader import TEMPLATE_META

NAMES = [
    "Анна",
    "Иван",
    "Мария",
    "Дмитрий",
    "Елена",
    "Сергей",
    "Ольга",
    "Алексей",
    "Татьяна",
    "Павел",
    "Ксения",
    "Артём",
]

SAMPLE_TEXTS = [
    "Всё понравилось, спасибо!",
    "Хотелось бы больше информации о статусе заказа.",
    "Удобный сервис, буду пользоваться ещё.",
    "Доставка могла бы быть быстрее.",
    "Отличная поддержка, быстро ответили.",
    "Цена немного выше ожидаемой.",
    "В целом хорошо, но есть куда расти.",
]

QUIZ_TEXTS = [
    "Переменная — это имя для хранения значения.",
    "Это контейнер, в котором лежат данные.",
    "Именованная область памяти для значения.",
    "Способ сохранить значение и обращаться к нему по имени.",
]


def ensure_demo_user(db) -> User:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Создан демо-пользователь: {DEMO_EMAIL}")
    return user


def ensure_surveys(db, user: User) -> list[Survey]:
    surveys: list[Survey] = []
    for key in TEMPLATE_META:
        survey = db.scalar(
            select(Survey).where(
                Survey.user_id == user.id, Survey.template_key == key
            )
        )
        if survey is None:
            survey = create_survey_from_template(db, user, key)
            print(f"Создан опрос из шаблона: {survey.title}")
        surveys.append(survey)
    return surveys


def _pick_options(question, rng: random.Random) -> list:
    options = list(question.options)
    if not options:
        return []

    if question.type == "single":
        if any(option.is_correct for option in options) and rng.random() < 0.62:
            correct = [option for option in options if option.is_correct]
            return [rng.choice(correct)]
        return [rng.choice(options)]

    correct = [option for option in options if option.is_correct]
    if correct and rng.random() < 0.5:
        return correct
    count = rng.randint(1, min(3, len(options)))
    return rng.sample(options, count)


def seed_responses(db, survey: Survey, rng: random.Random) -> int:
    existing = db.scalar(
        select(Response.id).where(Response.survey_id == survey.id).limit(1)
    )
    if existing is not None:
        return 0

    now = datetime.now(timezone.utc)
    texts = QUIZ_TEXTS if survey.template_key == "knowledge_test" else SAMPLE_TEXTS
    created = 0

    for index in range(8):
        response = Response(
            survey_id=survey.id,
            respondent_name=NAMES[index % len(NAMES)],
            created_at=now
            - timedelta(
                days=rng.randint(0, 13),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            ),
        )
        drafts: list[dict] = []

        for question in survey.questions:
            if question.type == "text":
                if question.required or rng.random() < 0.75:
                    value = rng.choice(texts)
                    drafts.append(
                        {
                            "question_id": question.id,
                            "option_id": None,
                            "text_value": value,
                        }
                    )
                continue

            if not question.required and rng.random() < 0.15:
                continue

            selected = _pick_options(question, rng)
            use_other = question.allow_other and rng.random() < 0.14

            if use_other and question.type == "single":
                selected = []

            for option in selected:
                drafts.append(
                    {
                        "question_id": question.id,
                        "option_id": option.id,
                        "text_value": None,
                    }
                )
            if use_other:
                drafts.append(
                    {
                        "question_id": question.id,
                        "option_id": None,
                        "text_value": rng.choice(
                            [
                                "Очень удобная навигация",
                                "Быстрая доставка",
                                "Приятный менеджер",
                                "Хорошее соотношение цены и качества",
                            ]
                        ),
                    }
                )

        score, max_score = compute_score(survey, drafts)
        response.score = score
        response.max_score = max_score

        for draft in drafts:
            response.answers.append(
                Answer(
                    question_id=draft["question_id"],
                    option_id=draft["option_id"],
                    text_value=draft["text_value"],
                )
            )

        db.add(response)
        created += 1

    db.commit()
    return created


def seed(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
        print("Старые таблицы удалены.")
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        user = ensure_demo_user(db)
        user_id = user.id
        surveys = ensure_surveys(db, user)
        rng = random.Random(42)
        for survey in surveys:
            created = seed_responses(db, survey, rng)
            if created:
                print(f"Добавлено {created} демо-ответов: {survey.title}")

    print("\nГотово.")
    print(f"Демо-доступ: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print("Опросы:")
    with SessionLocal() as db:
        for survey in db.scalars(
            select(Survey).where(Survey.user_id == user_id).order_by(Survey.id)
        ):
            total = (
                db.scalar(
                    select(func.count(Response.id)).where(
                        Response.survey_id == survey.id
                    )
                )
                or 0
            )
            print(f"  • {survey.title}: /survey/{survey.slug} ({total} ответов)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Заполнить базу демо-данными.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Удалить все таблицы и создать заново.",
    )
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
