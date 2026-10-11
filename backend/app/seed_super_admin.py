"""
Seed script to create the initial Super Admin user.

Usage:
    cd <project root>
    SEED_SUPER_ADMIN_PASSWORD=<password> python -m backend.app.seed_super_admin

Requires DATABASE_URL and JWT_SECRET_KEY in .env or environment.
Credentials are read from SEED_SUPER_ADMIN_NAME / SEED_SUPER_ADMIN_EMAIL /
SEED_SUPER_ADMIN_PASSWORD. The script refuses to run when ENVIRONMENT=production.
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

    full_name = os.getenv("SEED_SUPER_ADMIN_NAME", "Admin").strip() or "Admin"
    email = (
        os.getenv("SEED_SUPER_ADMIN_EMAIL", "admin@policygpt.gov").strip().lower()
    )
    password = os.getenv("SEED_SUPER_ADMIN_PASSWORD", "").strip()

    if not password:
        print(
            "ERROR: Set SEED_SUPER_ADMIN_PASSWORD in the environment "
            "(or .env) before running this script."
        )
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
    if os.getenv("ENVIRONMENT", "").strip().lower() == "production":
        print(
            "ERROR: Refusing to run seed script with ENVIRONMENT=production."
        )
        sys.exit(1)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        print("Set it in .env or export it before running.")
        sys.exit(1)

    print("Creating database engine...")
    engine = create_engine(database_url)

    with Session(engine) as session:
        print("\nSetting up Super Admin...")
        get_or_create_super_admin(session)

    print("\nDone.")


if __name__ == "__main__":
    main()
