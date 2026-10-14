"""Seed Super Admin and Admin users directly into the database."""
import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from backend.app.db.database import Base
from backend.app.models.user import User, UserRole
from backend.app.auth.security import hash_password

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set"); exit(1)

engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    # Check existing
    existing = session.execute(select(User.email)).scalars().all()

    users_to_create = [
        {
            "full_name": "Super Admin",
            "email": "superadmin@policygpt.gov",
            "password": "SuperAdmin@123",
            "role": UserRole.SUPER_ADMIN,
        },
        {
            "full_name": "Admin User",
            "email": "admin@policygpt.gov",
            "password": "Admin@12345",
            "role": UserRole.ADMINISTRATOR,
        },
    ]

    for u in users_to_create:
        if u["email"] in existing:
            print(f"  ⚠  {u['email']} already exists — skipping")
            continue
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
        print(f"  ✓  Created {u['role'].value}: {u['email']} / {u['password']}")

    print("\nDone. Login credentials:")
    print("  Super Admin : superadmin@policygpt.gov / SuperAdmin@123")
    print("  Admin       : admin@policygpt.gov / Admin@12345")
