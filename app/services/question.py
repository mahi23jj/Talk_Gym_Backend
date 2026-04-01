from app.db.postgran import SessionType
from app.models.speaking import Question
from app.schemas.speaking import QuestionCreateSchema


def create_question(question_data: QuestionCreateSchema, session: SessionType):
    new_question = Question(
        title=question_data.title,
        description=question_data.description,
    )
    session.add(new_question)
    session.commit()
    session.refresh(new_question)
    return new_question

def get_question_by_id(question_id: int, session: SessionType):
    question = session.get(Question, question_id)
    return question