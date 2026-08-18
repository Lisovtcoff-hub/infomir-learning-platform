from sqlalchemy import exists, func, select

from backend.app.db.session import SessionLocal
import backend.app.db.model_registry  # noqa: F401
from backend.app.models.attempt import Attempt, AttemptAnswer
from backend.app.models.user import User


def run_audit() -> None:
    db = SessionLocal()
    try:
        has_answers = exists(select(1).where(AttemptAnswer.attempt_id == Attempt.id))
        rows = db.execute(
            select(
                Attempt.user_id,
                User.name,
                User.email,
                func.count(Attempt.id).label("legacy_count"),
            )
            .join(User, User.id == Attempt.user_id)
            .where(
                Attempt.finished_at.is_not(None),
                Attempt.max_score > 0,
                ~has_answers,
            )
            .group_by(Attempt.user_id, User.name, User.email)
            .order_by(func.count(Attempt.id).desc(), Attempt.user_id.asc())
        ).all()

        total = sum(int(row.legacy_count or 0) for row in rows)
        print(f"Legacy finished attempts without answers: {total}")
        if not rows:
            return

        for row in rows:
            print(
                f"user_id={int(row.user_id)} | name={row.name} | email={row.email} | legacy_attempts={int(row.legacy_count)}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    run_audit()
