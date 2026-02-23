# RetailIQ — Retail Data Platform

RetailIQ is a modular backend platform for retail operations intelligence. It combines:
- transactional APIs (auth, store, inventory, transactions, customers),
- analytics APIs backed by aggregate tables,
- forecasting (store + SKU),
- decision recommendations from deterministic rules,
- NLP-style deterministic query responses,
- asynchronous background processing with Celery.

The platform is designed to run locally and in containerized environments with PostgreSQL + Redis.

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture End-to-End](#architecture-end-to-end)
3. [Repository Map](#repository-map)
4. [Request Lifecycle](#request-lifecycle)
5. [Data Model Overview](#data-model-overview)
6. [Asynchronous Tasking Model](#asynchronous-tasking-model)
7. [Forecasting + Decisions + NLP](#forecasting--decisions--nlp)
8. [Configuration and Environment Variables](#configuration-and-environment-variables)
9. [Running the System](#running-the-system)
10. [Testing Strategy](#testing-strategy)
11. [CI/CD](#cicd)
12. [Operations and Troubleshooting](#operations-and-troubleshooting)
13. [How to Modify the System Safely](#how-to-modify-the-system-safely)
14. [Production Readiness Checklist](#production-readiness-checklist)

---

## System Overview

RetailIQ is built as a Flask app using SQLAlchemy models and blueprint modules. It exposes versioned APIs under `/api/v1/...`, persists operational data in PostgreSQL, and offloads compute-heavy/periodic workflows to Celery workers.

### Core Capabilities
- **Auth + access control**: JWT-based auth with role gating (`owner`, `staff`).
- **Operational APIs**: inventory, transactions, customers, store configuration.
- **Analytics**: revenue/profit/category/payment/contribution views, mostly from aggregate tables.
- **Forecasting**: forecast cache for store-level and SKU-level projections.
- **Decision engine**: deterministic recommendations using rules over computed context.
- **NLP endpoint**: deterministic intent routing + template-based responses (not generative).

---

## Architecture End-to-End

### High-level Components
- **Flask API (Gunicorn)**: serves REST endpoints.
- **PostgreSQL**: transactional + aggregate + forecast storage.
- **Redis**:
  - Celery broker,
  - rate limiter storage,
  - short-lived auth artifacts (OTP, reset, refresh token lookup),
  - lightweight distributed locks for task idempotency.
- **Celery Worker**: executes async jobs.
- **Celery Beat**: schedules periodic jobs.

### Runtime Topology (`docker-compose.yml`)
- `app`: API server container.
- `postgres`: database.
- `redis`: cache/broker.
- `worker`: Celery worker process.
- `beat`: Celery scheduler.

Startup behavior:
1. `app` runs `scripts/start-app.sh`.
2. Startup script ensures `.env` exists (copies from `.env.example` if missing).
3. Waits for DB readiness (`scripts/wait_for_db.py`).
4. Applies migrations (`alembic upgrade head`).
5. Starts Gunicorn.

This enables reliable first-run startup in Dockerized environments.

---

## Repository Map

```text
app/
  __init__.py                # Flask app factory, extension init, blueprint registration
  models/                    # SQLAlchemy schema (core tables + aggregate tables)
  auth/                      # registration/login/otp/refresh/logout/password reset
  store/                     # store profile + categories + tax config
  inventory/                 # product and stock workflows
  transactions/              # transaction ingest/list/return and service layer
  customers/                 # customer CRUD + customer analytics
  analytics/                 # analytics endpoints + helper utilities/cache wrapper
  forecasting/               # forecast engine + forecast API serving from cache
  decisions/                 # context builder + deterministic recommendation rules
  nlp/                       # deterministic intent router + templates + query endpoint
  tasks/                     # canonical Celery tasks + task DB session

migrations/
  env.py                     # Alembic environment (reads DATABASE_URL)
  versions/                  # migration scripts

scripts/
  start-app.sh               # bootstrapping app startup script
  wait_for_db.py             # DB readiness probe

tests/
  conftest.py                # shared fixtures (in-memory SQLite test app)
  test_*.py                  # module-level tests

.github/workflows/
  test-on-commit.yml         # CI test workflow
```

---

## Request Lifecycle

1. Request enters Flask via Gunicorn.
2. Blueprint route validates payload via Marshmallow schemas.
3. `require_auth` decodes JWT and attaches identity (`g.current_user`).
4. Business logic executes via service layer and SQLAlchemy session.
5. Data is committed/rolled back.
6. Response is wrapped in standard response envelope in most modules.
7. Non-critical background follow-ups (aggregates/alerts/etc.) are queued asynchronously.

### Auth + Role Model
- Authenticated identity includes `user_id`, `store_id`, `role`.
- Role checks use decorators for owner-only operations.
- Refresh token lifecycle uses Redis token-keyed records with TTL.

---

## Data Model Overview

### Core transactional entities
- `users`, `stores`, `categories`, `products`, `customers`, `transactions`, `transaction_items`.
- Inventory/ops: `stock_adjustments`, `stock_audits`, `stock_audit_items`.

### Intelligence entities
- `alerts`
- `forecast_cache`
- Aggregate tables:
  - `daily_store_summary`
  - `daily_category_summary`
  - `daily_sku_summary`

### Circular FK note (`users` ↔ `stores`)
The schema intentionally has a circular relationship:
- `stores.owner_user_id -> users.user_id`
- `users.store_id -> stores.store_id`

This is handled safely via migration ordering (create users without FK, create stores, then add FK) and explicit FK naming on model side.

---

## Asynchronous Tasking Model

Canonical tasks live in `app/tasks/tasks.py`.

### Major jobs
- `rebuild_daily_aggregates` / `rebuild_daily_aggregates_all_stores`
- `evaluate_alerts` / `evaluate_alerts_all_stores`
- `run_batch_forecasting`
- `forecast_store`
- `detect_slow_movers`
- `send_weekly_digest`

### Task Reliability Patterns
- Redis lock keys to avoid duplicate concurrent runs.
- Retries/backoff on selected tasks.
- DB writes via task-specific session manager (`app/tasks/db_session.py`).
- Transaction APIs fail-open for async dispatch (core writes succeed even if broker dispatch fails).

---

## Forecasting + Decisions + NLP

## Forecasting
- Engine (`app/forecasting/engine.py`) chooses model based on history size.
- Writes forecast points to `forecast_cache`.
- API endpoints serve from cache (no expensive compute in request path).

## Decisions
- Builds per-product context using stock, history, forecast, and store-level signals.
- Applies deterministic rule registry with confidence/priority/time-sensitive metadata.
- Returns sorted, de-duplicated recommendations.

## NLP Endpoint
- Keyword intent routing (`forecast`, `inventory`, `revenue`, `profit`, `top_products`, default).
- SQL-backed metrics + deterministic templates.
- Stable machine-readable output for frontend consumption.

---

## Configuration and Environment Variables

Create `.env` for local overrides; in Docker, defaults from `.env.example` are loaded.

Common variables:
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `JWT_PRIVATE_KEY`
- `JWT_PUBLIC_KEY`
- `SECRET_KEY`

### Notes
- In non-test environments, provide stable JWT keys (do not rely on ephemeral generated keys).
- For production, use a secret manager and avoid committing real secrets.

---

## Running the System

## Option A: Docker (recommended)

```bash
docker-compose up --build
```

Services:
- API on `http://localhost:5000`
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`

## Option B: Local Python runtime

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=wsgi.py
flask run
```

For local DB migrations:
```bash
alembic upgrade head
```

---

## Testing Strategy

## Test discovery
`pytest.ini` scopes discovery to:
- `tests/`
- files matching `test_*.py`

## Running tests
```bash
pytest -q
```

### Test Environment Behavior
- Uses in-memory SQLite with shared `StaticPool` for fast isolated tests.
- Compilers map PG-specific `JSONB`/`UUID` for SQLite compatibility.
- Test fixture injects ephemeral JWT keys.

### Recommended test commands
```bash
pytest -q
pytest -q tests/test_transactions.py tests/test_audit.py tests/test_auth_flow.py
```

---

## CI/CD

GitHub Actions workflow `.github/workflows/test-on-commit.yml`:
- triggers on push + pull request,
- installs dependencies,
- runs `pytest -v`.

Recommended branch protection:
- require passing CI before merge,
- disallow direct pushes to default branch.

---

## Operations and Troubleshooting

## Health endpoint
- `GET /api/v1/health` returns app-level status payload.

## Common startup issues
1. **DB unavailable**
   - check Postgres container health.
   - inspect logs for `wait_for_db.py` timeout.
2. **Migration failure**
   - run `alembic upgrade head` manually.
   - verify `DATABASE_URL` points to expected DB.
3. **Redis broker errors**
   - confirm `REDIS_URL` / `CELERY_BROKER_URL`.
   - verify Redis service up.

## Useful commands
```bash
docker-compose logs -f app
docker-compose logs -f worker
docker-compose logs -f beat
```

---

## How to Modify the System Safely

## 1) Adding a new endpoint
- Create/extend module blueprint route.
- Add schema validation and auth decorators.
- Add/extend service logic.
- Add tests under `tests/`.

## 2) Adding new background task
- Implement in `app/tasks/tasks.py`.
- Use `task_session` and idempotent lock when appropriate.
- Add unit/integration tests.
- If scheduled, register in `celery_worker.py` beat schedule.

## 3) Changing DB schema
- Update model.
- Create Alembic migration.
- Validate migration from empty DB + upgrade path from existing DB.
- Add/adjust tests.

## 4) Changing auth behavior
- Keep token and Redis key strategy consistent across login/refresh/logout.
- Add lifecycle tests (rotation/replay/revocation).

---

## Production Readiness Checklist

Before deployment, ensure all are true:
- [ ] `pytest -q` passes fully.
- [ ] migrations apply cleanly on fresh DB and existing env.
- [ ] secrets managed externally (no plaintext secrets in repo).
- [ ] stable JWT key management strategy in place.
- [ ] log aggregation and monitoring configured.
- [ ] backup/restore validated for PostgreSQL.
- [ ] rate limits and auth policies reviewed.
- [ ] worker + beat autoscaling and queue policies defined.
- [ ] rollback strategy documented.

---

## Contributing

1. Create a branch.
2. Implement code + tests.
3. Run `pytest -q`.
4. Open PR with:
   - summary,
   - migration impact,
   - test evidence,
   - rollout notes.

---

## License

This project is open source under the MIT License (see `LICENSE` if present).
