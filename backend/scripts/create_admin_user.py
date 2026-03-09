from __future__ import annotations

import argparse
from pathlib import Path

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.user_store import UserStore
from app.services.user_store_postgres import PostgresUserStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a local admin user in auth.sqlite.")
    parser.add_argument("--db-path", default="backend/data/processed/auth.sqlite")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--email", default="admin@local")
    parser.add_argument("--password", default="password")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if os.getenv("USE_POSTGRES_AUTH", "false").lower() == "true":
        store = PostgresUserStore(os.getenv("POSTGRES_AUTH_DSN", "postgresql://bitebuddy:bitebuddy@localhost:5432/bitebuddy"))
    else:
        store = UserStore(Path(args.db_path))
    existing = store.get_user_by_email(args.email)
    if existing:
        print(f"Admin user already exists: {existing.email} (username={existing.username})")
        return
    user = store.create_user(username=args.username, email=args.email, password=args.password)
    store.mark_user_verified(user.user_id)
    print(f"Created admin user: {user.email} (username={user.username})")


if __name__ == "__main__":
    main()
