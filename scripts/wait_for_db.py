import os
import sys
import time

from sqlalchemy import create_engine, text


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "postgresql://retailiq:retailiq@postgres:5432/retailiq")
    timeout_seconds = int(os.environ.get("DB_WAIT_TIMEOUT", "60"))
    interval_seconds = float(os.environ.get("DB_WAIT_INTERVAL", "2"))

    connect_args = {}
    if "sslmode=require" in database_url.lower():
        # Remove from URL as create_engine doesn't like it in the query string sometimes
        database_url = database_url.replace("?sslmode=require", "").replace("&sslmode=require", "")
        connect_args = {"sslmode": "require"}

    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Database is ready")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Waiting for database: {exc}")
            time.sleep(interval_seconds)

    print("Timed out waiting for the database", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
