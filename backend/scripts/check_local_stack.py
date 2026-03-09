from __future__ import annotations

import argparse
import json

import psycopg
import redis
from qdrant_client import QdrantClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local Postgres/Redis/Qdrant connectivity.")
    parser.add_argument("--postgres-dsn", default="postgresql://bitebuddy:bitebuddy@localhost:5432/bitebuddy")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = {}

    try:
        with psycopg.connect(args.postgres_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        result["postgres"] = "ok"
    except Exception as exc:
        result["postgres"] = f"error: {exc}"

    try:
        client = redis.Redis.from_url(args.redis_url, decode_responses=True)
        client.ping()
        result["redis"] = "ok"
    except Exception as exc:
        result["redis"] = f"error: {exc}"

    try:
        qdrant = QdrantClient(url=args.qdrant_url)
        qdrant.get_collections()
        result["qdrant"] = "ok"
    except Exception as exc:
        result["qdrant"] = f"error: {exc}"

    print(json.dumps(result, indent=2))
    if any(not str(v).startswith("ok") for v in result.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
