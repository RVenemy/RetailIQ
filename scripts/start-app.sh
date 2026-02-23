#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=".env"
if [[ ! -f "$ENV_FILE" && -f ".env.example" ]]; then
  echo "No .env found; creating .env from .env.example"
  cp .env.example .env
fi

python scripts/wait_for_db.py
alembic upgrade head
exec gunicorn --bind 0.0.0.0:5000 wsgi:app
