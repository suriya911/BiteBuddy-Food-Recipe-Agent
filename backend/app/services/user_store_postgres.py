from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import psycopg

PBKDF2_ITERATIONS = 200_000
SESSION_TTL_DAYS = 30
MAX_OTP_ATTEMPTS = 6


@dataclass
class UserRecord:
    user_id: int
    username: str
    email: str
    email_verified: bool


class PostgresUserStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._init_db()

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id SERIAL PRIMARY KEY,
                        username TEXT NOT NULL,
                        username_lc TEXT NOT NULL UNIQUE,
                        email TEXT NOT NULL UNIQUE,
                        email_verified BOOLEAN NOT NULL DEFAULT FALSE,
                        password_hash TEXT NOT NULL,
                        salt TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        token_hash TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(user_id),
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP NOT NULL
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS favorites (
                        user_id INTEGER NOT NULL REFERENCES users(user_id),
                        recipe_id TEXT NOT NULL,
                        recipe_json TEXT NOT NULL,
                        saved_at TIMESTAMP NOT NULL,
                        PRIMARY KEY (user_id, recipe_id)
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS history (
                        entry_id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(user_id),
                        query TEXT NOT NULL,
                        result_count INTEGER NOT NULL,
                        top_recipe_titles_json TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS email_otps (
                        otp_id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(user_id),
                        code_hash TEXT NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        consumed BOOLEAN NOT NULL DEFAULT FALSE,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP NOT NULL
                    );
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_history_user_id_created_at ON history(user_id, created_at DESC);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user_id_saved_at ON favorites(user_id, saved_at DESC);")
            conn.commit()

    def create_user(self, *, username: str, email: str, password: str) -> UserRecord:
        now = self._now()
        normalized_email = email.strip().lower()
        normalized_username = username.strip()
        username_lc = normalized_username.lower()
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password=password, salt=salt)

        with self._connect() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        INSERT INTO users (username, username_lc, email, password_hash, salt, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING user_id
                        """,
                        (normalized_username, username_lc, normalized_email, password_hash, salt, now),
                    )
                    user_id = int(cur.fetchone()[0])
                except psycopg.errors.UniqueViolation as exc:
                    conn.rollback()
                    message = str(exc).lower()
                    if "users.email" in message:
                        raise ValueError("Email is already registered.") from exc
                    if "users.username_lc" in message:
                        raise ValueError("Username is already taken.") from exc
                    raise ValueError("Unable to create account.") from exc
            conn.commit()

        return UserRecord(
            user_id=user_id,
            username=normalized_username,
            email=normalized_email,
            email_verified=False,
        )

    def authenticate(self, *, identifier: str, password: str) -> UserRecord | None:
        lookup = identifier.strip().lower()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, username, email, email_verified, password_hash, salt
                    FROM users
                    WHERE email = %s OR username_lc = %s
                    LIMIT 1
                    """,
                    (lookup, lookup),
                )
                row = cur.fetchone()
        if row is None:
            return None
        expected = row[4]
        actual = self._hash_password(password=password, salt=row[5])
        if not hmac.compare_digest(expected, actual):
            return None
        return UserRecord(
            user_id=int(row[0]),
            username=str(row[1]),
            email=str(row[2]),
            email_verified=bool(row[3]),
        )

    def create_session(self, user_id: int) -> str:
        raw_token = secrets.token_urlsafe(48)
        token_hash = self._hash_token(raw_token)
        now = self._now()
        expires_at = now + timedelta(days=SESSION_TTL_DAYS)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sessions (token_hash, user_id, expires_at, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (token_hash) DO UPDATE SET user_id = EXCLUDED.user_id, expires_at = EXCLUDED.expires_at
                    """,
                    (token_hash, user_id, expires_at, now),
                )
            conn.commit()
        return raw_token

    def get_user_by_token(self, token: str) -> UserRecord | None:
        token_hash = self._hash_token(token)
        now = self._now()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.user_id, u.username, u.email, u.email_verified, s.expires_at
                    FROM sessions s
                    JOIN users u ON u.user_id = s.user_id
                    WHERE s.token_hash = %s
                    LIMIT 1
                    """,
                    (token_hash,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                expires_at = row[4]
                if self._is_expired(expires_at, now):
                    cur.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))
                    conn.commit()
                    return None
        return UserRecord(
            user_id=int(row[0]),
            username=str(row[1]),
            email=str(row[2]),
            email_verified=bool(row[3]),
        )

    def get_user_by_email(self, email: str) -> UserRecord | None:
        normalized = email.strip().lower()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id, username, email, email_verified FROM users WHERE email = %s LIMIT 1",
                    (normalized,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return UserRecord(
            user_id=int(row[0]),
            username=str(row[1]),
            email=str(row[2]),
            email_verified=bool(row[3]),
        )

    def create_email_otp(self, *, user_id: int, expiry_minutes: int) -> str:
        code = f"{secrets.randbelow(1_000_000):06d}"
        code_hash = self._hash_token(code)
        now = self._now()
        expires_at = now + timedelta(minutes=expiry_minutes)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO email_otps (user_id, code_hash, expires_at, consumed, attempts, created_at)
                    VALUES (%s, %s, %s, FALSE, 0, %s)
                    """,
                    (user_id, code_hash, expires_at, now),
                )
            conn.commit()
        return code

    def verify_email_otp(self, *, email: str, otp_code: str) -> UserRecord | None:
        user = self.get_user_by_email(email)
        if user is None:
            return None
        now = self._now()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT otp_id, code_hash, attempts, expires_at
                    FROM email_otps
                    WHERE user_id = %s AND consumed = FALSE
                    ORDER BY otp_id DESC
                    LIMIT 1
                    """,
                    (user.user_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                expires_at = row[3]
                if self._is_expired(expires_at, now) or int(row[2]) >= MAX_OTP_ATTEMPTS:
                    cur.execute("UPDATE email_otps SET consumed = TRUE WHERE otp_id = %s", (row[0],))
                    conn.commit()
                    return None
                is_valid = hmac.compare_digest(str(row[1]), self._hash_token(otp_code.strip()))
                if not is_valid:
                    cur.execute(
                        "UPDATE email_otps SET attempts = attempts + 1 WHERE otp_id = %s",
                        (row[0],),
                    )
                    conn.commit()
                    return None
                cur.execute("UPDATE email_otps SET consumed = TRUE WHERE otp_id = %s", (row[0],))
                cur.execute("UPDATE users SET email_verified = TRUE WHERE user_id = %s", (user.user_id,))
            conn.commit()
        return UserRecord(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            email_verified=True,
        )

    def revoke_session(self, token: str) -> None:
        token_hash = self._hash_token(token)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))
            conn.commit()

    def list_favorites(self, user_id: int) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT recipe_id, recipe_json, saved_at
                    FROM favorites
                    WHERE user_id = %s
                    ORDER BY saved_at DESC
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
        return [
            {
                "recipe_id": str(row[0]),
                "recipe": json.loads(str(row[1])),
                "saved_at": row[2].isoformat(),
            }
            for row in rows
        ]

    def save_favorite(self, *, user_id: int, recipe: dict) -> dict:
        recipe_id = str(recipe.get("id") or recipe.get("recipe_id") or "").strip()
        if not recipe_id:
            raise ValueError("Recipe payload is missing id.")
        saved_at = self._now()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO favorites (user_id, recipe_id, recipe_json, saved_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, recipe_id) DO UPDATE SET recipe_json = EXCLUDED.recipe_json, saved_at = EXCLUDED.saved_at
                    """,
                    (user_id, recipe_id, json.dumps(recipe), saved_at),
                )
            conn.commit()
        return {
            "recipe_id": recipe_id,
            "recipe": recipe,
            "saved_at": saved_at.isoformat(),
        }

    def remove_favorite(self, *, user_id: int, recipe_id: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM favorites WHERE user_id = %s AND recipe_id = %s", (user_id, recipe_id))
            conn.commit()

    def list_history(self, user_id: int) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT entry_id, query, result_count, top_recipe_titles_json, created_at
                    FROM history
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 200
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
        return [
            {
                "entry_id": str(row[0]),
                "query": str(row[1]),
                "result_count": int(row[2]),
                "top_recipe_titles": json.loads(str(row[3])),
                "created_at": row[4].isoformat(),
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
        created_at = self._now()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO history (entry_id, user_id, query, result_count, top_recipe_titles_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (entry_id, user_id, query, result_count, json.dumps(top_recipe_titles[:10]), created_at),
                )
            conn.commit()
        return {
            "entry_id": entry_id,
            "query": query,
            "result_count": result_count,
            "top_recipe_titles": top_recipe_titles[:10],
            "created_at": created_at.isoformat(),
        }

    def mark_user_verified(self, user_id: int) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET email_verified = TRUE WHERE user_id = %s", (user_id,))
            conn.commit()

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

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _is_expired(self, expires_at: datetime, now: datetime) -> bool:
        if expires_at.tzinfo is None:
            return expires_at <= now.replace(tzinfo=None)
        return expires_at <= now
