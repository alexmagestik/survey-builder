"""Маршруты создания опросов и публичного прохождения."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user, require_user
from auth.security import verify_csrf
from database.db import get_db
from database.models import User
from surveys.service import (
    create_survey as create_survey_service,
    get_active_survey_by_slug,
    get_owned_survey,
    get_response_count,
    list_user_surveys,
    parse_builder_form,
    save_response,
    validate_submission,
)
from surveys.template_loader import (
    blank_form,
    list_templates,
    load_template,
    template_to_form,
)
from web import flash, render

router = APIRouter()


def _value(form, key: str) -> str:
    value = form.get(key)
    return "" if value is None else str(value)


@router.get("/surveys", name="survey_list")
def survey_list(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    return render(
        request,
        "surveys/list.html",
        {"current_user": user, "items": list_user_surveys(db, user.id)},
    )


@router.get("/surveys/new", name="survey_new")
def new_survey(
    request: Request,
    template: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    templates_list = list_templates()
    selected_template = None
    if template:
        try:
            selected_template = template
            form = template_to_form(load_template(template))
        except (KeyError, ValueError):
            flash(request, "Шаблон не найден, открыт пустой конструктор.", "error")
            form = blank_form()
    else:
        form = blank_form()

    return render(
        request,
        "surveys/new.html",
        {
            "current_user": user,
            "form": form,
            "errors": [],
            "templates_list": templates_list,
            "selected_template": selected_template,
        },
    )


@router.post("/surveys", name="survey_create")
async def create_survey_route(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    verify_csrf(request, _value(form, "csrf_token"))
    data, errors = parse_builder_form(form)

    if errors:
        return render(
            request,
            "surveys/new.html",
            {
                "current_user": user,
                "form": data,
                "errors": errors,
                "templates_list": list_templates(),
                "selected_template": None,
            },
            status_code=400,
        )

    survey = create_survey_service(
        db,
        user,
        title=data["title"],
        description=data["description"],
        questions=data["questions"],
        scoring_enabled=data["scoring_enabled"],
    )
    flash(request, "Опрос создан. Ссылка готова к отправке.", "success")
    return RedirectResponse(f"/surveys/{survey.id}", status_code=303)


@router.get("/surveys/{survey_id}", name="survey_detail")
def survey_detail(
    survey_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    survey = get_owned_survey(db, survey_id, user)
    return render(
        request,
        "surveys/detail.html",
        {
            "current_user": user,
            "survey": survey,
            "response_count": get_response_count(db, survey.id),
            "public_url": str(request.url_for("public_survey", slug=survey.slug)),
        },
    )


@router.post("/surveys/{survey_id}/delete", name="survey_delete")
async def delete_survey(
    survey_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    verify_csrf(request, _value(form, "csrf_token"))
    survey = get_owned_survey(db, survey_id, user)
    title = survey.title
    db.delete(survey)
    db.commit()
    flash(request, f"Опрос «{title}» удалён.", "info")
    return RedirectResponse("/surveys", status_code=303)


@router.get("/survey/{slug}", name="public_survey")
def public_survey(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    survey = get_active_survey_by_slug(db, slug)
    return render(
        request,
        "surveys/public.html",
        {
            "current_user": current_user,
            "survey": survey,
            "submitted": None,
            "errors": [],
        },
    )


def _build_submitted(survey, form, name: str) -> dict:
    values: dict[str, list[str]] = {}
    other: dict[str, str] = {}
    text: dict[str, str] = {}
    for question in survey.questions:
        if question.type == "text":
            text[str(question.id)] = _value(form, f"q_{question.id}")
        else:
            values[str(question.id)] = [
                str(value) for value in form.getlist(f"q_{question.id}")
            ]
            other[str(question.id)] = _value(form, f"q_{question.id}_other")
    return {"name": name, "values": values, "other": other, "text": text}


@router.post("/survey/{slug}", name="public_survey_submit")
async def submit_survey(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    survey = get_active_survey_by_slug(db, slug)
    form = await request.form()
    verify_csrf(request, _value(form, "csrf_token"))

    name, drafts, errors = validate_submission(survey, form)
    if errors:
        return render(
            request,
            "surveys/public.html",
            {
                "current_user": current_user,
                "survey": survey,
                "submitted": _build_submitted(survey, form, name),
                "errors": errors,
            },
            status_code=400,
        )

    response = save_response(db, survey, name, drafts)
    request.session[f"last_result_{survey.slug}"] = {
        "score": response.score,
        "max_score": response.max_score,
    }
    return RedirectResponse(f"/survey/{survey.slug}/thanks", status_code=303)


@router.get("/survey/{slug}/thanks", name="public_survey_thanks")
def survey_thanks(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    survey = get_active_survey_by_slug(db, slug)
    result = request.session.pop(f"last_result_{survey.slug}", None)
    return render(
        request,
        "surveys/thanks.html",
        {
            "current_user": current_user,
            "survey": survey,
            "result": result,
        },
    )
