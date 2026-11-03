"""Агрегаты для страницы статистики."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from database.models import Answer, Response, Survey


def get_survey_stats(db: Session, survey: Survey) -> dict:
    total_responses = (
        db.scalar(select(func.count(Response.id)).where(Response.survey_id == survey.id))
        or 0
    )
    total_answers = (
        db.scalar(
            select(func.count(Answer.id))
            .join(Response, Answer.response_id == Response.id)
            .where(Response.survey_id == survey.id)
        )
        or 0
    )
    last_response_at = db.scalar(
        select(func.max(Response.created_at)).where(Response.survey_id == survey.id)
    )

    max_score = (
        sum(1 for question in survey.questions if question.type != "text")
        if survey.scoring_enabled
        else None
    )
    average_score = None
    score_distribution: list[dict] = []
    if survey.scoring_enabled:
        average_score = db.scalar(
            select(func.avg(Response.score)).where(
                Response.survey_id == survey.id, Response.score.is_not(None)
            )
        )
        score_rows = db.execute(
            select(Response.score, func.count(Response.id))
            .where(Response.survey_id == survey.id, Response.score.is_not(None))
            .group_by(Response.score)
            .order_by(Response.score)
        ).all()
        scored_total = sum(count for _, count in score_rows)
        for score, count in score_rows:
            score_distribution.append(
                {
                    "score": score,
                    "count": count,
                    "percent": (count / scored_total * 100) if scored_total else 0,
                }
            )

    questions_stats: list[dict] = []
    for question in survey.questions:
        answered = (
            db.scalar(
                select(func.count(func.distinct(Answer.response_id))).where(
                    Answer.question_id == question.id
                )
            )
            or 0
        )
        options_stats: list[dict] = []
        other_answers: list[str] = []
        text_answers: list[str] = []
        correct_count: int | None = None
        correct_percent: float | None = None

        if question.type == "text":
            text_answers = list(
                db.scalars(
                    select(Answer.text_value)
                    .where(
                        Answer.question_id == question.id,
                        Answer.text_value.is_not(None),
                    )
                    .order_by(Answer.id.desc())
                    .limit(20)
                ).all()
            )
        else:
            for option in question.options:
                count = (
                    db.scalar(
                        select(func.count(Answer.id)).where(
                            Answer.option_id == option.id
                        )
                    )
                    or 0
                )
                options_stats.append(
                    {
                        "id": option.id,
                        "text": option.text,
                        "count": count,
                        "percent": (count / answered * 100) if answered else 0,
                    }
                )
            other_answers = list(
                db.scalars(
                    select(Answer.text_value)
                    .where(
                        Answer.question_id == question.id,
                        Answer.option_id.is_(None),
                        Answer.text_value.is_not(None),
                    )
                    .order_by(Answer.id.desc())
                    .limit(20)
                ).all()
            )

            if survey.scoring_enabled:
                rows = db.execute(
                    select(Answer.response_id, Answer.option_id).where(
                        Answer.question_id == question.id
                    )
                ).all()
                selected_by_response: dict[int, set[int]] = defaultdict(set)
                for response_id, option_id in rows:
                    if option_id is not None:
                        selected_by_response[response_id].add(option_id)
                correct_ids = {
                    option.id for option in question.options if option.is_correct
                }
                correct_count = sum(
                    1
                    for selected in selected_by_response.values()
                    if correct_ids and selected == correct_ids
                )
                correct_percent = (
                    (correct_count / answered * 100) if answered else 0
                )

        questions_stats.append(
            {
                "question": question,
                "answered": answered,
                "options": options_stats,
                "other_answers": other_answers,
                "text_answers": text_answers,
                "correct_count": correct_count,
                "correct_percent": correct_percent,
                "is_scored": survey.scoring_enabled and question.type != "text",
            }
        )

    responses = db.scalars(
        select(Response)
        .where(Response.survey_id == survey.id)
        .options(
            selectinload(Response.answers).selectinload(Answer.question),
            selectinload(Response.answers).selectinload(Answer.option),
        )
        .order_by(Response.created_at.desc(), Response.id.desc())
        .limit(10)
    ).all()

    last_responses: list[dict] = []
    for response in responses:
        grouped: dict[int, list[str]] = defaultdict(list)
        for answer in response.answers:
            if answer.option is not None:
                grouped[answer.question_id].append(answer.option.text)
            elif answer.text_value:
                grouped[answer.question_id].append(answer.text_value)
        answer_rows = [
            {"question": question.text, "values": grouped[question.id]}
            for question in survey.questions
            if grouped.get(question.id)
        ]
        last_responses.append(
            {
                "name": response.respondent_name,
                "created_at": response.created_at,
                "score": response.score,
                "max_score": response.max_score,
                "answers": answer_rows,
            }
        )

    return {
        "total_responses": total_responses,
        "total_answers": total_answers,
        "last_response_at": last_response_at,
        "average_score": average_score,
        "max_score": max_score,
        "score_distribution": score_distribution,
        "questions": questions_stats,
        "last_responses": last_responses,
    }
