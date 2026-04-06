from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db.postgran import get_session
from app.models.question import Question
from app.schemas.speaking import (
    QuestionByTagsQuerySchema,
    QuestionCreateSchema,
    QuestionReadSchema,
    QuestionSearchQuerySchema,
    QuestionTagsUpdateSchema,
    QuestionWithCountSchema,
    TagCreateSchema,
    TagReadSchema,
    TagStatSchema,
)
from app.services.question import (
    create_question,
    create_tag,
    create_tags_for_question,
    get_all_tags,
    get_question_by_id,
    get_questions_by_tags,
    recommend_questions_with_similar_tags,
    remove_tags_from_question,
    search_questions_by_keyword,
)

router = APIRouter(prefix="/questions", tags=["Questions"])


def _to_question_read_schema(question: Question) -> QuestionReadSchema:
    return QuestionReadSchema(
        id=question.id,
        title=question.title,
        description=question.description,
        day_unlock=question.day_unlock,
        tags=[tag.name for tag in question.tags],
        created_at=question.created_at,
    )


@router.post("/", response_model=QuestionReadSchema, status_code=status.HTTP_201_CREATED)
def create_question_endpoint(payload: QuestionCreateSchema, db=Depends(get_session)):
    question = create_question(payload, db)
    db.refresh(question)
    return _to_question_read_schema(question)


@router.get("/{question_id}", response_model=QuestionReadSchema)
def get_question_endpoint(question_id: int, db=Depends(get_session)):
    question = get_question_by_id(question_id, db)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return _to_question_read_schema(question)


@router.post("/tags", response_model=TagReadSchema, status_code=status.HTTP_201_CREATED)
def create_tag_endpoint(payload: TagCreateSchema, db=Depends(get_session)):
    tag = create_tag(payload.name, db)
    return TagReadSchema.model_validate(tag)


@router.get("/tags/list", response_model=list[TagStatSchema])
def get_all_tags_endpoint(db=Depends(get_session)):
    rows = get_all_tags(db)
    return [
        TagStatSchema(
            tag=TagReadSchema.model_validate(tag),
            question_count=int(question_count),
        )
        for tag, question_count in rows
    ]


@router.post("/{question_id}/tags", response_model=QuestionReadSchema)
def add_tags_to_question_endpoint(
    question_id: int,
    payload: QuestionTagsUpdateSchema,
    db=Depends(get_session),
):
    question = get_question_by_id(question_id, db)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    create_tags_for_question(question, payload.tags, db)
    db.refresh(question)
    return _to_question_read_schema(question)


@router.delete("/{question_id}/tags", response_model=QuestionReadSchema)
def remove_tags_from_question_endpoint(
    question_id: int,
    payload: QuestionTagsUpdateSchema,
    db=Depends(get_session),
):
    question = get_question_by_id(question_id, db)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    remove_tags_from_question(question, payload.tags, db)
    db.refresh(question)
    return _to_question_read_schema(question)


@router.get("/by-tags/filter", response_model=list[QuestionWithCountSchema])
def get_questions_by_tags_endpoint(
    tags: list[str] = Query(default=[]),
    db=Depends(get_session),
):
    query_model = QuestionByTagsQuerySchema(tags=tags)
    rows = get_questions_by_tags(query_model.tags, db)
    return [
        QuestionWithCountSchema(
            question=_to_question_read_schema(question),
            count=int(count),
        )
        for question, count in rows
    ]


@router.get("/search", response_model=list[QuestionReadSchema])
def search_questions_endpoint(keyword: str = Query(..., min_length=1), db=Depends(get_session)):
    query_model = QuestionSearchQuerySchema(keyword=keyword)
    rows = search_questions_by_keyword(query_model.keyword, db)
    return [_to_question_read_schema(question) for question in rows]


@router.get("/{question_id}/recommendations", response_model=list[QuestionWithCountSchema])
def recommend_questions_endpoint(question_id: int, db=Depends(get_session)):
    rows = recommend_questions_with_similar_tags(question_id, db)
    return [
        QuestionWithCountSchema(
            question=_to_question_read_schema(question),
            count=int(count),
        )
        for question, count in rows
    ]
