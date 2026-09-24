#!/usr/bin/env python
"""
Seeds roles and demo users (section 43). Idempotent — safe to re-run
(upserts roles by name, skips users that already exist by email).

Demo credentials (LOCAL DEVELOPMENT ONLY — never use these in production):
    admin@supplychain-demo.com             / DemoPass123!   (admin)
    ops@supplychain-demo.com                / DemoPass123!   (operations_manager)
    analyst@supplychain-demo.com            / DemoPass123!   (analyst)
    viewer@supplychain-demo.com             / DemoPass123!   (viewer)

Usage:
    python scripts/seed_database.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from app.auth.permissions import Role  # noqa: E402
from app.auth.security import hash_password  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.user import Role as RoleModel  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from scripts.pipeline_common import print_metrics  # noqa: E402

DEMO_PASSWORD = "DemoPass123!"

DEMO_USERS = [
    ("admin@supplychain-demo.com", "Demo Admin", Role.ADMIN),
    ("ops@supplychain-demo.com", "Demo Ops Manager", Role.OPERATIONS_MANAGER),
    ("analyst@supplychain-demo.com", "Demo Analyst", Role.ANALYST),
    ("viewer@supplychain-demo.com", "Demo Viewer", Role.VIEWER),
]

ROLE_DESCRIPTIONS = {
    Role.ADMIN: "Full platform access, including user management.",
    Role.OPERATIONS_MANAGER: "Manages shipments, suppliers, alerts, analytics, and AI copilot.",
    Role.ANALYST: "Read-only analytics/shipments access, plus AI copilot and model analytics.",
    Role.VIEWER: "Read-only dashboard/shipments/suppliers access.",
}


def seed_roles(db) -> dict[str, RoleModel]:
    role_map = {}
    for role in Role:
        existing = db.query(RoleModel).filter(RoleModel.name == role.value).first()
        if existing is None:
            existing = RoleModel(name=role.value, description=ROLE_DESCRIPTIONS[role])
            db.add(existing)
            db.flush()
        role_map[role.value] = existing
    db.commit()
    return role_map


def seed_users(db, role_map: dict[str, RoleModel]) -> int:
    created = 0
    for email, full_name, role in DEMO_USERS:
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None:
            continue
        user = User(email=email, hashed_password=hash_password(DEMO_PASSWORD), full_name=full_name, is_active=True)
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role_map[role.value].id))
        created += 1
    db.commit()
    return created


def main():
    db = SessionLocal()
    try:
        role_map = seed_roles(db)
        created_users = seed_users(db, role_map)
    finally:
        db.close()

    print_metrics(
        "Database seed",
        {
            "roles_ensured": len(role_map),
            "users_created": created_users,
            "demo_password": DEMO_PASSWORD,
            "demo_accounts": [u[0] for u in DEMO_USERS],
        },
    )


if __name__ == "__main__":
    main()
