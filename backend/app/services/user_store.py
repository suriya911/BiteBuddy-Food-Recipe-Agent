from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


PBKDF2_ITERATIONS = 200_000
SESSION_TTL_DAYS = 30
MAX_OTP_ATTEMPTS = 6


@dataclass
class UserRecord:
    user_id: int
    username: str
    email: str
    email_verified: bool


class UserStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    username_lc TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS favorites (
                    user_id INTEGER NOT NULL,
                    recipe_id TEXT NOT NULL,
                    recipe_json TEXT NOT NULL,
                    saved_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, recipe_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS history (
                    entry_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    result_count INTEGER NOT NULL,
                    top_recipe_titles_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_history_user_id_created_at ON history(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_favorites_user_id_saved_at ON favorites(user_id, saved_at DESC);

                CREATE TABLE IF NOT EXISTS email_otps (
                    otp_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    code_hash TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_email_otps_user_id ON email_otps(user_id);
                """
            )
            # Lightweight migration for old databases.
            user_columns = {row['name'] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
            if 'email_verified' not in user_columns:
                conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")

    def create_user(self, *, username: str, email: str, password: str) -> UserRecord:
        now = self._now_iso()
        normalized_email = email.strip().lower()
        normalized_username = username.strip()
        username_lc = normalized_username.lower()
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password=password, salt=salt)

        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO users (username, username_lc, email, password_hash, salt, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (normalized_username, username_lc, normalized_email, password_hash, salt, now),
                )
            except sqlite3.IntegrityError as exc:
                message = str(exc).lower()
                if "users.email" in message:
                    raise ValueError("Email is already registered.") from exc
                if "users.username_lc" in message:
                    raise ValueError("Username is already taken.") from exc
                raise ValueError("Unable to create account.") from exc
        return UserRecord(
            user_id=int(cursor.lastrowid),
            username=normalized_username,
            email=normalized_email,
            email_verified=False,
        )

    def authenticate(self, *, identifier: str, password: str) -> UserRecord | None:
        lookup = identifier.strip().lower()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, username, email, email_verified, password_hash, salt
                FROM users
                WHERE email = ? OR username_lc = ?
                LIMIT 1
                """,
                (lookup, lookup),
            ).fetchone()
        if row is None:
            return None
        expected = row["password_hash"]
        actual = self._hash_password(password=password, salt=row["salt"])
        if not hmac.compare_digest(expected, actual):
            return None
        return UserRecord(
            user_id=int(row["user_id"]),
            username=str(row["username"]),
            email=str(row["email"]),
            email_verified=bool(row["email_verified"]),
        )

    def create_session(self, user_id: int) -> str:
        raw_token = secrets.token_urlsafe(48)
        token_hash = self._hash_token(raw_token)
        now = datetime.now(UTC)
        expires_at = (now + timedelta(days=SESSION_TTL_DAYS)).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (token_hash, user_id, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (token_hash, user_id, expires_at, now.isoformat()),
            )
        return raw_token

    def get_user_by_token(self, token: str) -> UserRecord | None:
        token_hash = self._hash_token(token)
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT u.user_id, u.username, u.email, u.email_verified, s.expires_at
                FROM sessions s
                JOIN users u ON u.user_id = s.user_id
                WHERE s.token_hash = ?
                LIMIT 1
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            if str(row["expires_at"]) <= now:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
                return None
        return UserRecord(
            user_id=int(row["user_id"]),
            username=str(row["username"]),
            email=str(row["email"]),
            email_verified=bool(row["email_verified"]),
        )

    def get_user_by_email(self, email: str) -> UserRecord | None:
        normalized = email.strip().lower()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, username, email, email_verified FROM users WHERE email = ? LIMIT 1",
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        return UserRecord(
            user_id=int(row["user_id"]),
            username=str(row["username"]),
            email=str(row["email"]),
            email_verified=bool(row["email_verified"]),
        )

    def create_email_otp(self, *, user_id: int, expiry_minutes: int) -> str:
        code = f"{secrets.randbelow(1_000_000):06d}"
        code_hash = self._hash_token(code)
        now = datetime.now(UTC)
        expires_at = (now + timedelta(minutes=expiry_minutes)).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO email_otps (user_id, code_hash, expires_at, consumed, attempts, created_at)
                VALUES (?, ?, ?, 0, 0, ?)
                """,
                (user_id, code_hash, expires_at, now.isoformat()),
            )
        return code

    def verify_email_otp(self, *, email: str, otp_code: str) -> UserRecord | None:
        user = self.get_user_by_email(email)
        if user is None:
            return None
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT otp_id, code_hash, attempts, expires_at
                FROM email_otps
                WHERE user_id = ? AND consumed = 0
                ORDER BY otp_id DESC
                LIMIT 1
                """,
                (user.user_id,),
            ).fetchone()
            if row is None:
                return None
            if str(row["expires_at"]) <= now or int(row["attempts"]) >= MAX_OTP_ATTEMPTS:
                conn.execute("UPDATE email_otps SET consumed = 1 WHERE otp_id = ?", (row["otp_id"],))
                return None

            is_valid = hmac.compare_digest(str(row["code_hash"]), self._hash_token(otp_code.strip()))
            if not is_valid:
                conn.execute(
                    "UPDATE email_otps SET attempts = attempts + 1 WHERE otp_id = ?",
                    (row["otp_id"],),
                )
                return None

            conn.execute("UPDATE email_otps SET consumed = 1 WHERE otp_id = ?", (row["otp_id"],))
            conn.execute("UPDATE users SET email_verified = 1 WHERE user_id = ?", (user.user_id,))

        return UserRecord(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            email_verified=True,
        )

    def revoke_session(self, token: str) -> None:
        token_hash = self._hash_token(token)
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    def list_favorites(self, user_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT recipe_id, recipe_json, saved_at
                FROM favorites
                WHERE user_id = ?
                ORDER BY saved_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            {
                "recipe_id": str(row["recipe_id"]),
                "recipe": json.loads(str(row["recipe_json"])),
                "saved_at": str(row["saved_at"]),
            }
            for row in rows
        ]

    def save_favorite(self, *, user_id: int, recipe: dict) -> dict:
        recipe_id = str(recipe.get("id") or recipe.get("recipe_id") or "").strip()
        if not recipe_id:
            raise ValueError("Recipe payload is missing id.")
        saved_at = self._now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO favorites (user_id, recipe_id, recipe_json, saved_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, recipe_id, json.dumps(recipe), saved_at),
            )
        return {
            "recipe_id": recipe_id,
            "recipe": recipe,
            "saved_at": saved_at,
        }

    def remove_favorite(self, *, user_id: int, recipe_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM favorites WHERE user_id = ? AND recipe_id = ?",
                (user_id, recipe_id),
            )

    def list_history(self, user_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT entry_id, query, result_count, top_recipe_titles_json, created_at
                FROM history
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 200
                """,
                (user_id,),
            ).fetchall()
        return [
            {
                "entry_id": str(row["entry_id"]),
                "query": str(row["query"]),
                "result_count": int(row["result_count"]),
                "top_recipe_titles": json.loads(str(row["top_recipe_titles_json"])),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def add_history(
        self,
        *,
        user_id: int,
        query: str,
        result_count: int,
        top_recipe_titles: list[str],
    ) -> dict:
        entry_id = secrets.token_hex(8)
        created_at = self._now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO history (entry_id, user_id, query, result_count, top_recipe_titles_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (entry_id, user_id, query, result_count, json.dumps(top_recipe_titles[:10]), created_at),
            )
        return {
            "entry_id": entry_id,
            "query": query,
            "result_count": result_count,
            "top_recipe_titles": top_recipe_titles[:10],
            "created_at": created_at,
        }

    def mark_user_verified(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE users SET email_verified = 1 WHERE user_id = ?", (user_id,))

    def _hash_password(self, *, password: str, salt: str) -> str:
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            PBKDF2_ITERATIONS,
        )
        return key.hex()

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _now_iso(self) -> str:
        return datetime.now(UTC).isoformat()
