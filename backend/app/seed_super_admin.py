"""
Seed script to create the initial Super Admin user.

Usage:
    cd <project root>
    python -m backend.app.seed_super_admin

Requires DATABASE_URL and JWT_SECRET_KEY in .env or environment.
"""

import os
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Load .env if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from backend.app.db.database import Base
from backend.app.models.user import User, UserRole
from backend.app.auth.security import hash_password


def get_or_create_super_admin(session: Session) -> User:
    """Find existing Super Admin or create one."""
    existing = session.execute(
        select(User).where(User.role == UserRole.SUPER_ADMIN)
    ).scalar_one_or_none()

    if existing:
        print(f"  Super Admin already exists: {existing.email} (id={existing.id})")
        return existing

    # Prompt for details
    full_name = input("Super Admin full name [Admin]: ").strip() or "Admin"
    email = input("Super Admin email [admin@policygpt.gov]: ").strip() or "admin@policygpt.gov"
    password = input("Super Admin password: ").strip()

    if not password:
        print("ERROR: Password cannot be empty.")
        sys.exit(1)

    admin = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        email_verified=True,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)

    print(f"  Super Admin created: {admin.email} (id={admin.id})")
    return admin


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        print("Set it in .env or export it before running.")
        sys.exit(1)

    print("Creating database engine...")
    engine = create_engine(database_url)

    print("Creating tables (if not exists)...")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        print("\nSetting up Super Admin...")
        get_or_create_super_admin(session)

    print("\nDone.")


if __name__ == "__main__":
    main()
