from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.question import Question, QuestionTagLink, Tag
from app.schemas.speaking import QuestionCreateSchema


def create_tag(tag_name: str, session: Session) -> Tag:
    normalized = tag_name.strip().lower()
    tag = session.exec(select(Tag).where(Tag.name == normalized)).first()
    if tag:
        return tag

    tag = Tag(name=normalized)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def create_tags_for_question(question: Question, tag_names: list[str], session: Session) -> None:
    for tag_name in tag_names:
        tag = create_tag(tag_name, session)
        exists = session.exec(
            select(QuestionTagLink).where(
                QuestionTagLink.question_id == question.id,
                QuestionTagLink.tag_id == tag.id,
            )
        ).first()
        if not exists:
            session.add(QuestionTagLink(question_id=question.id, tag_id=tag.id))
    session.commit()


def remove_tags_from_question(question: Question, tag_names: list[str], session: Session) -> None:
    for tag_name in tag_names:
        normalized = tag_name.strip().lower()
        tag = session.exec(select(Tag).where(Tag.name == normalized)).first()
        if not tag:
            continue

        link = session.exec(
            select(QuestionTagLink).where(
                QuestionTagLink.question_id == question.id,
                QuestionTagLink.tag_id == tag.id,
            )
        ).first()
        if link:
            session.delete(link)
    session.commit()


def create_question(question_data: QuestionCreateSchema, session: Session) -> Question:
    new_question = Question(
        title=question_data.title,
        description=question_data.description,
        day_unlock=question_data.day_unlock,
    )
    session.add(new_question)
    session.commit()
    session.refresh(new_question)

    if question_data.tags:
        create_tags_for_question(new_question, question_data.tags, session)
        session.refresh(new_question)

    return new_question


def get_question_by_id(question_id: int, session: Session) -> Question | None:
    if question_id <= 0:
        return None
    return session.get(Question, question_id)


def get_all_tags(session: Session) -> Sequence[tuple[Tag, int]]:
    statement = (
        select(Tag, func.count(QuestionTagLink.question_id).label("question_count"))
        .outerjoin(QuestionTagLink, Tag.id == QuestionTagLink.tag_id)
        .group_by(Tag.id)
        .order_by(func.count(QuestionTagLink.question_id).desc())
    )
    return session.exec(statement).all()


def get_questions_by_tags(tag_names: list[str] | None, session: Session) -> Sequence[tuple[Question, int]]:
    statement = (
        select(Question, func.count(QuestionTagLink.tag_id).label("tag_count"))
        .join(QuestionTagLink, Question.id == QuestionTagLink.question_id)
        .join(Tag, Tag.id == QuestionTagLink.tag_id)
        .group_by(Question.id)
    )

    if tag_names:
        normalized = [tag.strip().lower() for tag in tag_names if tag.strip()]
        if normalized:
            statement = statement.where(Tag.name.in_(normalized))

    statement = statement.order_by(func.count(QuestionTagLink.tag_id).desc())
    return session.exec(statement).all()


def search_questions_by_keyword(keyword: str, session: Session) -> Sequence[Question]:
    normalized = keyword.strip()
    if not normalized:
        return []

    statement = (
        select(Question)
        .outerjoin(QuestionTagLink, Question.id == QuestionTagLink.question_id)
        .outerjoin(Tag, Tag.id == QuestionTagLink.tag_id)
        .where(
            Question.title.ilike(f"%{normalized}%")
            | Question.description.ilike(f"%{normalized}%")
            | Tag.name.ilike(f"%{normalized}%")
        )
        .distinct()
    )
    return session.exec(statement).all()


def recommend_questions_with_similar_tags(question_id: int, session: Session) -> Sequence[tuple[Question, int]]:
    question = session.get(Question, question_id)
    if not question:
        return []

    tag_ids = session.exec(
        select(QuestionTagLink.tag_id).where(QuestionTagLink.question_id == question_id)
    ).all()
    if not tag_ids:
        return []

    statement = (
        select(Question, func.count(QuestionTagLink.tag_id).label("shared_tag_count"))
        .join(QuestionTagLink, Question.id == QuestionTagLink.question_id)
        .where(
            QuestionTagLink.tag_id.in_(tag_ids),
            Question.id != question_id,
        )
        .group_by(Question.id)
        .order_by(func.count(QuestionTagLink.tag_id).desc())
    )
    return session.exec(statement).all()




