"""Модели: пользователи, опросы, вопросы, варианты, отправки и ответы."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    surveys: Mapped[list["Survey"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    template_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    owner: Mapped["User"] = relationship(back_populates="surveys")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="survey",
        cascade="all, delete-orphan",
        order_by="Question.position",
    )
    responses: Mapped[list["Response"]] = relationship(
        back_populates="survey",
        cascade="all, delete-orphan",
        order_by="Response.created_at.desc()",
    )


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('single', 'multiple', 'text')", name="ck_question_type"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    survey_id: Mapped[int] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    allow_other: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    survey: Mapped["Survey"] = relationship(back_populates="questions")
    options: Mapped[list["Option"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="Option.position",
    )
    answers: Mapped[list["Answer"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class Option(Base):
    __tablename__ = "options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    question: Mapped["Question"] = relationship(back_populates="options")
    answers: Mapped[list["Answer"]] = relationship(
        back_populates="option", cascade="all, delete-orphan"
    )


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        Index("ix_responses_survey_created", "survey_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    survey_id: Mapped[int] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False
    )
    respondent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    survey: Mapped["Survey"] = relationship(back_populates="responses")
    answers: Mapped[list["Answer"]] = relationship(
        back_populates="response",
        cascade="all, delete-orphan",
        order_by="Answer.id",
    )


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (
        UniqueConstraint(
            "response_id",
            "question_id",
            "option_id",
            name="uq_answer_response_question_option",
        ),
        CheckConstraint(
            "option_id IS NOT NULL OR text_value IS NOT NULL",
            name="ck_answer_has_value",
        ),
        Index("ix_answers_response", "response_id"),
        Index("ix_answers_question", "question_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    response_id: Mapped[int] = mapped_column(
        ForeignKey("responses.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    option_id: Mapped[int | None] = mapped_column(
        ForeignKey("options.id", ondelete="CASCADE"), nullable=True
    )
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    response: Mapped["Response"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship(back_populates="answers")
    option: Mapped["Option | None"] = relationship(back_populates="answers")
