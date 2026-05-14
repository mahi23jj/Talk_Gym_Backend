from sqlmodel import select
from sqlalchemy.orm import selectinload
from app.models import (
    User,
    Attempt,
    InterviewSession,
    InterviewAnalysis,
)
from app.schemas.profile import (
    ProfileResponse,
    TrialStatus,
    ProgressSummary,
    CategoryProgress,
    QuestionHistoryItem,
    ContinueSession,
)


FREE_TRIAL_LIMIT = 5


class ProfileService:

    @staticmethod
    async def get_profile(db, user_id: int):

        user = db.exec(
            select(User).where(User.id == user_id)
        ).first()

        sessions = db.exec(
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .options(
                selectinload(InterviewSession.attempts)
                .selectinload(Attempt.analysis)
            )
        ).all()

        completed_sessions = 0
        history = []
        improvements = []
        continue_session = None

        category_map = {}

        for session in sessions:

            initial = None
            final = None

            for attempt in session.attempts:
                if attempt.analysis:

                    if attempt.stage.name == "INITIAL":
                        initial = attempt.analysis.score

                    elif attempt.stage.name == "FINAL":
                        final = attempt.analysis.score

            completed = final is not None

            if completed:
                completed_sessions += 1

            improvement = None
            if initial is not None and final is not None:
                improvement = final - initial
                improvements.append(improvement)

            history.append(
                QuestionHistoryItem(
                    session_id=session.id,
                    question_id=session.question_id,
                    initial_score=initial,
                    final_score=final,
                    improvement=improvement,
                    recommendation_type=None,
                    completed=completed,
                )
            )

            if not completed and continue_session is None:
                continue_session = ContinueSession(
                    session_id=session.id,
                    question_id=session.question_id,
                    next_stage="continue_training"
                )

        avg_improvement = (
            sum(improvements) / len(improvements)
            if improvements else 0
        )

        interviews_used = len(sessions)

        return ProfileResponse(
            username=user.username,
            email=user.email,

            trial_status=TrialStatus(
                interviews_used=interviews_used,
                interviews_limit=FREE_TRIAL_LIMIT,
                remaining=max(
                    0,
                    FREE_TRIAL_LIMIT - interviews_used
                )
            ),

            progress=ProgressSummary(
                total_questions_attempted=len(history),
                completed_sessions=completed_sessions,
                avg_improvement=avg_improvement,
            ),

            categories=[],

            history=history,

            continue_session=continue_session,
        )