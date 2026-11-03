"""Страница статистики опроса."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from analytics.service import get_survey_stats
from auth.dependencies import require_user
from database.db import get_db
from database.models import User
from surveys.service import get_owned_survey
from web import render

router = APIRouter()


@router.get("/surveys/{survey_id}/stats", name="survey_stats")
def survey_stats(
    survey_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    survey = get_owned_survey(db, survey_id, user)
    stats = get_survey_stats(db, survey)
    public_url = str(request.url_for("public_survey", slug=survey.slug))
    return render(
        request,
        "analytics/stats.html",
        {
            "current_user": user,
            "survey": survey,
            "stats": stats,
            "public_url": public_url,
        },
    )
