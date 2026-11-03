"""Pydantic-схемы для Jinja2-шаблонов опросов."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

QuestionType = Literal["single", "multiple", "text"]


class TemplateOption(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    correct: bool = False


class TemplateQuestion(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    type: QuestionType
    required: bool = False
    allow_other: bool = False
    options: list[TemplateOption] = Field(default_factory=list)


class SurveyTemplate(BaseModel):
    key: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=2000)
    scoring: bool = False
    questions: list[TemplateQuestion] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_questions(self) -> "SurveyTemplate":
        for question in self.questions:
            if question.type == "text":
                question.options = []
                question.allow_other = False
                continue

            if not 2 <= len(question.options) <= 20:
                raise ValueError(
                    f"В вопросе «{question.text}» должно быть от 2 до 20 вариантов."
                )

            if self.scoring:
                correct_count = sum(1 for o in question.options if o.correct)
                if correct_count == 0:
                    raise ValueError(
                        f"В тестовом вопросе «{question.text}» не отмечен правильный вариант."
                    )
                if question.type == "single" and correct_count > 1:
                    raise ValueError(
                        f"В тестовом вопросе «{question.text}» должен быть "
                        "ровно один правильный вариант."
                    )

        if self.scoring and not any(q.type != "text" for q in self.questions):
            raise ValueError("В тесте должен быть хотя бы один вопрос с вариантами.")
        return self
