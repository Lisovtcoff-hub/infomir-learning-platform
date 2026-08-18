from __future__ import annotations

import argparse
from getpass import getpass

from sqlalchemy import func, select

from backend.app.core.security import hash_password
from backend.app.db.session import SessionLocal
from backend.app.models.user import User, UserProfile


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote an Infomir administrator")
    parser.add_argument("email", help="Administrator email")
    parser.add_argument("--name", default="Administrator", help="Display name")
    args = parser.parse_args()

    password = getpass("New administrator password: ")
    repeated = getpass("Repeat password: ")
    if password != repeated:
        raise SystemExit("Passwords do not match")
    if len(password) < 12:
        raise SystemExit("Administrator password must contain at least 12 characters")

    email = args.email.strip().lower()
    with SessionLocal() as db:
        user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
        if user:
            user.name = args.name.strip() or user.name
            user.password_hash = hash_password(password)
            user.role = "admin"
            user.is_active = True
        else:
            user = User(
                name=args.name.strip() or "Administrator",
                email=email,
                password_hash=hash_password(password),
                role="admin",
                grade=None,
                is_active=True,
            )
            db.add(user)
            db.flush()
            db.add(UserProfile(user_id=user.id))
        db.commit()
        print(f"Administrator ready: {email}")


if __name__ == "__main__":
    main()
