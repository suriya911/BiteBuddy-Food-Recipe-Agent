from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.user_store import UserStore
from app.services.user_store_postgres import PostgresUserStore


def _get_store():
    use_pg = os.getenv("USE_POSTGRES_AUTH", "false").lower() == "true"
    if use_pg:
        dsn = os.getenv("POSTGRES_AUTH_DSN", "postgresql://bitebuddy:bitebuddy@localhost:5432/bitebuddy")
        return PostgresUserStore(dsn)

    db_path = Path(os.getenv("AUTH_DB_PATH", "backend/data/processed/auth.sqlite"))
    if not db_path.is_absolute():
        db_path = (BACKEND_ROOT.parent / db_path).resolve()
    return UserStore(db_path)


def _ensure_user(store, *, username: str, email: str, password: str) -> None:
    existing = store.get_user_by_email(email)
    if existing is None:
        user = store.create_user(username=username, email=email, password=password)
        store.mark_user_verified(user.user_id)
        print(f"Created user: {username} ({email})")
        return
    print(f"User exists: {existing.username} ({existing.email})")


def main() -> None:
    store = _get_store()
    _ensure_user(store, username="admin", email="admin@local", password="password")
    _ensure_user(store, username="suriya", email="suriya@local", password="password")
    print("Done.")


if __name__ == "__main__":
    main()
