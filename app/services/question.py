from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.redis import redis_client
from app.models.question import Question, QuestionTagLink, Tag
from app.schemas.speaking import QuestionCreateSchema


CACHE_KEY = "questions_full_cache"
CACHE_TTL = 3600


def _question_from_cache_row(q: dict[str, Any]) -> Question:
    created_at_raw = q.get("created_at")
    created_at = None

    if isinstance(created_at_raw, str):
        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except ValueError:
            created_at = None

    question_kwargs: dict[str, Any] = {
        "id": q["id"],
        "title": q["title"],
        "description": q["description"],
        "day_unlock": q["day_unlock"],
        "tags": [Tag(name=tag_name) for tag_name in q.get("tags", [])],
    }

    if created_at is not None:
        question_kwargs["created_at"] = created_at

    return Question(**question_kwargs)


# ============================================================
# CACHE HELPERS
# ============================================================

def rebuild_cache(session: Session) -> None:
    """
    Rebuild full question/tag cache from DB.
    """

    questions = session.exec(select(Question)).all()
    tags = session.exec(select(Tag)).all()
    links = session.exec(select(QuestionTagLink)).all()

    tag_map = {t.id: t.name for t in tags}
    question_tags = defaultdict(list)

    for link in links:
        question_tags[link.question_id].append(
            tag_map.get(link.tag_id)
        )

    payload = [
        {
            "id": q.id,
            "title": q.title,
            "description": q.description,
            "day_unlock": q.day_unlock,
            "created_at": q.created_at.isoformat() if q.created_at else None,
            "tags": question_tags.get(q.id, [])
        }
        for q in questions
    ]

    redis_client.setex(
        CACHE_KEY,
        CACHE_TTL,
        json.dumps(payload)
    )


def get_cached_questions(session: Session):

    cached = redis_client.get(CACHE_KEY)

    if not cached:
        rebuild_cache(session)
        cached = redis_client.get(CACHE_KEY)

    return json.loads(cached)


def invalidate_cache():
    redis_client.delete(CACHE_KEY)


# ============================================================
# CREATE TAG
# ============================================================

def create_tag(tag_name: str, session: Session) -> Tag:
    normalized = tag_name.strip().lower()

    tag = session.exec(
        select(Tag).where(Tag.name == normalized)
    ).first()

    if tag:
        return tag

    tag = Tag(name=normalized)
    session.add(tag)
    session.flush()

    return tag


# ============================================================
# CREATE TAG LINKS
# ============================================================

def create_tags_for_question(
    question: Question,
    tag_names: list[str],
    session: Session
) -> None:

    if not tag_names:
        return

    # normalize + remove duplicates
    normalized = list({
        name.strip().lower()
        for name in tag_names
        if name.strip()
    })

    # fetch all existing tags in ONE query
    existing_tags = session.exec(
        select(Tag).where(
            Tag.name.in_(normalized)
        )
    ).all()

    existing_map = {
        tag.name: tag
        for tag in existing_tags
    }

    # create only missing tags
    new_tags = []

    for name in normalized:
        if name not in existing_map:
            tag = Tag(name=name)
            session.add(tag)
            new_tags.append(tag)

    # flush once to get ids
    session.flush()

    all_tags = existing_tags + new_tags

    # fetch all existing links in ONE query
    existing_links = {
        link.tag_id
        for link in session.exec(
            select(QuestionTagLink).where(
                QuestionTagLink.question_id == question.id
            )
        ).all()
    }

    # create missing links
    for tag in all_tags:
        if tag.id not in existing_links:
            session.add(
                QuestionTagLink(
                    question_id=question.id,
                    tag_id=tag.id
                )
            )

    session.commit()


# ============================================================
# REMOVE TAGS
# ============================================================

def remove_tags_from_question(
    question: Question,
    tag_names: list[str],
    session: Session
) -> None:

    normalized = {
        t.strip().lower()
        for t in tag_names
    }

    tags = session.exec(
        select(Tag).where(Tag.name.in_(normalized))
    ).all()

    tag_ids = {t.id for t in tags}

    links = session.exec(
        select(QuestionTagLink).where(
            QuestionTagLink.question_id == question.id,
            QuestionTagLink.tag_id.in_(tag_ids)
        )
    ).all()

    for link in links:
        session.delete(link)

    session.commit()
    invalidate_cache()


# ============================================================
# CREATE QUESTION
# ============================================================

def create_question(
    question_data: QuestionCreateSchema,
    session: Session
) -> Question:

    question = Question(
        title=question_data.title,
        description=question_data.description,
        day_unlock=question_data.day_unlock
    )

    session.add(question)
    session.flush()

    if question_data.tags:
        create_tags_for_question(
            question,
            question_data.tags,
            session
        )

    session.commit()
    session.refresh(question)

    rebuild_cache(session)

    return question


# ============================================================
# GET BY ID
# ============================================================

def get_question_by_id(
    question_id: int,
    session: Session
) -> Question | None:

    if question_id <= 0:
        return None

    questions = get_cached_questions(session)

    for q in questions:
        if q["id"] == question_id:
            return _question_from_cache_row(q)

    return None


# ============================================================
# GET ALL TAGS
# ============================================================

def get_all_tags(
    session: Session
) -> Sequence[tuple[Tag, int]]:
    rows = session.exec(
        select(Tag, func.count(QuestionTagLink.question_id))
        .join(QuestionTagLink, QuestionTagLink.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.count(QuestionTagLink.question_id).desc())
    ).all()

    return [(tag, int(count)) for tag, count in rows]


# ============================================================
# FILTER BY TAGS
# ============================================================

def get_questions_by_tags(
    tag_names: list[str] | None,
    session: Session
) -> Sequence[tuple[Question, int]]:

    questions = get_cached_questions(session)

    if not tag_names:
        return [(_question_from_cache_row(q), 0) for q in questions]

    normalized = {
        t.strip().lower()
        for t in tag_names
    }

    result: list[tuple[Question, int]] = []

    for q in questions:
        matches = normalized.intersection(q["tags"])

        if matches:
            result.append(
                (
                    _question_from_cache_row(q),
                    len(matches),
                )
            )

    return sorted(result, key=lambda x: x[1], reverse=True)




# ============================================================
# KEYWORD SEARCH
# ============================================================

def search_questions_by_keyword(
    keyword: str,
    session: Session
) -> Sequence[Question]:

    keyword = keyword.strip().lower()

    if not keyword:
        return []

    questions = get_cached_questions(session)

    result = []

    for q in questions:

        haystack = (
            q["title"] +
            q["description"] +
            " ".join(q["tags"])
        ).lower()

        if keyword in haystack:
            result.append(_question_from_cache_row(q))

    return result


# ============================================================
# RECOMMEND SIMILAR
# ============================================================

def recommend_questions_with_similar_tags(
    question_id: int,
    session: Session
) -> Sequence[tuple[Question, int]]:

    questions = get_cached_questions(session)

    target = None

    for q in questions:
        if q["id"] == question_id:
            target = q
            break

    if not target:
        return []

    target_tags = set(target["tags"])

    result = []

    for q in questions:

        if q["id"] == question_id:
            continue

        shared = len(
            target_tags.intersection(q["tags"])
        )

        if shared:
            result.append(
                (
                    _question_from_cache_row(q),
                    shared
                )
            )

    return sorted(
        result,
        key=lambda x: x[1],
        reverse=True
    )