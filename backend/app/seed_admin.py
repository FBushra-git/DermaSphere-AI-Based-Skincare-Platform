"""Create the first platform administrator from environment variables."""

import os

from sqlalchemy import select

from app import models  # noqa: F401 — register metadata
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import Role, User


def main():
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    name = os.environ.get("ADMIN_NAME", "Platform Admin").strip()
    if not email or len(password) < 16:
        raise SystemExit(
            "Set ADMIN_EMAIL and ADMIN_PASSWORD (at least 16 characters) before seeding"
        )
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("An account with ADMIN_EMAIL already exists")
        db.add(
            User(
                name=name,
                email=email,
                password_hash=hash_password(password),
                role=Role.ADMIN,
            )
        )
    print(f"Created administrator account: {email}")


if __name__ == "__main__":
    main()
