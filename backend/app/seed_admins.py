"""Seed Super Admin and Admin users directly into the database.

Credentials are read from the environment so no password is ever hardcoded:

    SEED_SUPER_ADMIN_PASSWORD  (required when the super admin must be created)
    SEED_ADMIN_PASSWORD        (required when the admin must be created)

Emails/names can be overridden with SEED_SUPER_ADMIN_EMAIL /
SEED_SUPER_ADMIN_NAME / SEED_ADMIN_EMAIL / SEED_ADMIN_NAME.

Refuses to run when ENVIRONMENT=production.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from backend.app.models.user import User, UserRole
from backend.app.auth.security import hash_password

if os.getenv("ENVIRONMENT", "").strip().lower() == "production":
    print("ERROR: Refusing to run seed script with ENVIRONMENT=production.")
    raise SystemExit(1)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set"); raise SystemExit(1)

engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    # Check existing
    existing = session.execute(select(User.email)).scalars().all()

    users_to_create = [
        {
            "full_name": os.getenv("SEED_SUPER_ADMIN_NAME", "Super Admin"),
            "email": os.getenv(
                "SEED_SUPER_ADMIN_EMAIL", "superadmin@policygpt.gov"
            ),
            "password": os.getenv("SEED_SUPER_ADMIN_PASSWORD", ""),
            "role": UserRole.SUPER_ADMIN,
        },
        {
            "full_name": os.getenv("SEED_ADMIN_NAME", "Admin User"),
            "email": os.getenv("SEED_ADMIN_EMAIL", "admin@policygpt.gov"),
            "password": os.getenv("SEED_ADMIN_PASSWORD", ""),
            "role": UserRole.ADMINISTRATOR,
        },
    ]

    created = []

    for u in users_to_create:
        if u["email"] in existing:
            print(f"  ⚠  {u['email']} already exists — skipping")
            continue

        if not u["password"]:
            print(
                "ERROR: Set "
                f"SEED_{u['role'].value.upper()}_PASSWORD in the environment "
                "(or .env) before running this script."
            )
            raise SystemExit(1)

        user = User(
            full_name=u["full_name"],
            email=u["email"],
            password_hash=hash_password(u["password"]),
            role=u["role"],
            is_active=True,
            email_verified=True,
        )
        session.add(user)
        session.commit()
        created.append(u)
        print(f"  ✓  Created {u['role'].value}: {u['email']}")

    print("\nDone.")
    if created:
        print("Credentials (set via SEED_*_PASSWORD environment variables):")
        for u in created:
            print(f"  {u['role'].value:<14} {u['email']}")
