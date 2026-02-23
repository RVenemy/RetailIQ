# Backend End-to-End File Audit (Redundant / Trash / Orphan Candidates)

## Scope and method
- Scanned backend-relevant Python modules under `app/`, `scripts/`, `migrations/`, plus root entrypoints and support scripts.
- Performed textual reference checks using `rg` to identify files with zero inbound references.
- Reviewed runtime wiring in `docker-compose.yml`, `wsgi.py`, `celery_worker.py`, and `app/__init__.py` blueprint/task registration.
- Reviewed root-level non-code artifacts (`*.txt`, `celerybeat-schedule`) for repository hygiene.

## What is clearly part of the active backend runtime
These are wired into startup/runtime paths and **should not** be treated as orphan files:
- `wsgi.py` (Flask app entrypoint used by Docker/Gunicorn).
- `celery_worker.py` (Celery app/task loader used by worker/beat services).
- `app/__init__.py` (app factory + blueprint registration).
- Feature modules under `app/` (`auth`, `store`, `inventory`, `transactions`, `customers`, `analytics`, `forecasting`, `decisions`, `nlp`, `team`, `tasks`, `models`).
- Alembic migration environment and version files under `migrations/`.
- Startup scripts in `scripts/`.

## Likely redundant/orphan files (code)

### 1) `measure.py` — likely local one-off perf script (high confidence)
Why flagged:
- Not referenced by runtime entrypoints, tests, Docker services, or app factory wiring.
- Contains hardcoded localhost calls + seed logic typical of ad-hoc/manual benchmarking.

Recommendation:
- Move to `scripts/dev/` (or `tools/`) if still useful; otherwise remove from main repo root.

### 2) `run_test_capture.py` — Windows-local helper script (high confidence)
Why flagged:
- Uses `venv\Scripts\python.exe` path and writes `test_failures.txt`; this is local troubleshooting glue.
- Not referenced by CI/runtime wiring.

Recommendation:
- Move to `scripts/dev/` and mark as developer-local, or remove.

### 3) `app/transactions/tasks.py` — compatibility shim (medium confidence)
Why flagged:
- File is only a re-export wrapper around canonical tasks in `app/tasks/tasks.py`.
- No in-repo textual imports of `app.transactions.tasks` were found.

Recommendation:
- If external callers do not depend on this import path, delete file and import directly from `app.tasks.tasks`.
- If backward compatibility is required, keep but document as an intentional compatibility surface.

## Trash/debug artifacts in repo root (very high confidence)
The following appear to be generated logs/debug captures and are not used by runtime wiring:

`celerybeat-schedule`,
`cmdstan_check.txt`, `cmdstan_install.txt`,
`debug_prophet.txt`, `docker_full_test.txt`, `docker_test_fix.txt`, `docker_test_out.txt`, `docker_test_out2.txt`,
`fail_debug.txt`, `fail_docker2.txt`, `fix_prophet.txt`, `forecast_integration.txt`,
`lf.txt`, `lf2.txt`, `measure_out.txt`,
`prophet_test.txt`, `prophet_test2.txt`, `prophet_test3.txt`, `prophet_version.txt`,
`psql.txt`, `psql_out.txt`,
`pytest_full_out.txt`, `pytest_lf.txt`, `pytest_lf_utf8.txt`, `pytest_out.txt`,
`test_failures.txt`, `test_final.txt`, `test_out.txt`, `test_out_utf8.txt`, `test_rec1.txt`, `test_results.txt`, `test_results_utf8.txt`, `test_run_output.txt`, `test_step2.txt`, `test_step3.txt`, `test_step4.txt`,
`worker_logs.txt`, `worker_logs_utf8.txt`.

Recommendation:
- Remove these from source control and add a `.gitignore` pattern strategy for generated diagnostics (for example: `*.out.txt`, `*_logs*.txt`, `pytest_*.txt`, `docker_*_out*.txt`, and `celerybeat-schedule`).

## Risk notes before deleting
- `app/transactions/tasks.py` could still be used by external scripts not committed in this repository.
- `measure.py` / `run_test_capture.py` may be relied upon by individual developers; relocate before deletion if uncertain.


## Cleanup status
- Implemented cleanup: removed identified orphan/trash files and updated `.gitignore` to prevent re-committing generated artifacts.
- Updated `app/transactions/services.py` to import Celery tasks from canonical `app.tasks.tasks` after removing compatibility shim `app/transactions/tasks.py`.

## Suggested cleanup sequence
1. Remove root debug artifacts.
2. Add stronger ignore rules for generated artifacts.
3. Relocate or remove one-off helper scripts (`measure.py`, `run_test_capture.py`).
4. Remove `app/transactions/tasks.py` only after confirming no external dependency on that import path.
