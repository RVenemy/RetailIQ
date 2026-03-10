#!/usr/bin/env bash
# ============================================================================
# RetailIQ — Production Entrypoint
# Dispatches to API / Worker / Beat based on SERVICE_ROLE env var.
# Runs Alembic migrations (with distributed lock) for the API role only.
# ============================================================================
set -euo pipefail

SERVICE_ROLE="${SERVICE_ROLE:-api}"

# ── Logging helper ──────────────────────────────────────────────────────────
log() { echo "[entrypoint] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }

# ── Wait for database ──────────────────────────────────────────────────────
wait_for_db() {
    log "Waiting for PostgreSQL to become ready …"
    python scripts/wait_for_db.py
    log "PostgreSQL is ready."
}

# ── Normalize Redis URLs for SSL ──────────────────────────────────────────
# ElastiCache TLS requires ?ssl_cert_reqs=none in the URL for redis-py/celery
normalize_redis_urls() {
    if [[ "${REDIS_URL:-}" == rediss://* ]] && [[ "${REDIS_URL}" != *ssl_cert_reqs=* ]]; then
        log "Appending ssl_cert_reqs=none to REDIS_URL"
        if [[ "${REDIS_URL}" == *\?* ]]; then
            export REDIS_URL="${REDIS_URL}&ssl_cert_reqs=none"
        else
            export REDIS_URL="${REDIS_URL}?ssl_cert_reqs=none"
        fi
    fi

    if [[ "${CELERY_BROKER_URL:-}" == rediss://* ]] && [[ "${CELERY_BROKER_URL}" != *ssl_cert_reqs=* ]]; then
        log "Appending ssl_cert_reqs=none to CELERY_BROKER_URL"
        if [[ "${CELERY_BROKER_URL}" == *\?* ]]; then
            export CELERY_BROKER_URL="${CELERY_BROKER_URL}&ssl_cert_reqs=none"
        else
            export CELERY_BROKER_URL="${CELERY_BROKER_URL}?ssl_cert_reqs=none"
        fi
    fi
}

# ── Run Alembic migrations (with Redis distributed lock) ───────────────────
run_migrations() {
    log "Attempting to acquire migration lock …"

    # Use a simple Redis-based lock to prevent multiple API containers from
    # running migrations simultaneously during a rolling deployment.
    # NOTE: ElastiCache with TransitEncryption requires ssl_cert_reqs=none
    python -c "
import os, sys, time, redis as r

url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# ElastiCache TLS: skip cert verification for AWS-managed certs
kwargs = dict(decode_responses=True, socket_connect_timeout=10, socket_timeout=10)
if url.startswith('rediss://'):
    import ssl
    kwargs['ssl_cert_reqs'] = 'none'

client = r.Redis.from_url(url, **kwargs)
lock_key = 'lock:alembic_migration'
lock_ttl = 300  # 5 minutes

# Try to acquire the lock
if client.set(lock_key, '1', nx=True, ex=lock_ttl):
    print('[entrypoint] Migration lock acquired.')
    sys.exit(0)
else:
    # Another container is running migrations — wait for it to finish
    print('[entrypoint] Migration lock held by another process; waiting …')
    for _ in range(lock_ttl):
        time.sleep(1)
        if not client.exists(lock_key):
            print('[entrypoint] Lock released by leader; migrations complete.')
            sys.exit(10)
    print('[entrypoint] Timeout waiting for migration lock.', file=sys.stderr)
    sys.exit(10)
"
    LOCK_EXIT=$?

    if [ "$LOCK_EXIT" -eq 0 ]; then
        log "Running Alembic migrations …"
        alembic upgrade head
        MIGRATION_EXIT=$?

        # Release the lock regardless of migration outcome
        python -c "
import os, redis as r
url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
kwargs = dict(decode_responses=True, socket_connect_timeout=10, socket_timeout=10)
if url.startswith('rediss://'):
    kwargs['ssl_cert_reqs'] = 'none'
client = r.Redis.from_url(url, **kwargs)
client.delete('lock:alembic_migration')
print('[entrypoint] Migration lock released.')
"
        if [ "$MIGRATION_EXIT" -ne 0 ]; then
            log "ERROR: Alembic migrations failed (exit code $MIGRATION_EXIT)."
            exit 1
        fi
        log "Migrations completed successfully."
    else
        log "Skipping migrations (another container handled them)."
    fi
}

# ── Service dispatch ───────────────────────────────────────────────────────
case "$SERVICE_ROLE" in

    api)
        normalize_redis_urls
        wait_for_db
        run_migrations
        log "Starting Gunicorn API server …"
        exec gunicorn -c gunicorn.conf.py wsgi:app
        ;;

    worker)
        normalize_redis_urls
        wait_for_db
        CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-4}"
        CELERY_QUEUES="${CELERY_QUEUES:-celery}"
        log "Starting Celery worker (concurrency=$CELERY_CONCURRENCY, queues=$CELERY_QUEUES) …"
        exec celery -A celery_worker.celery_app worker \
            --loglevel=info \
            --concurrency="$CELERY_CONCURRENCY" \
            --queues="$CELERY_QUEUES" \
            --without-heartbeat \
            --without-mingle \
            --without-gossip \
            --max-tasks-per-child=1000
        ;;

    beat)
        normalize_redis_urls
        wait_for_db
        log "Starting Celery Beat scheduler (using /tmp for schedule) …"
        exec celery -A celery_worker.celery_app beat \
            --loglevel=info \
            --pidfile=/tmp/celerybeat.pid \
            --schedule=/tmp/celerybeat-schedule
        ;;

    *)
        log "ERROR: Unknown SERVICE_ROLE '$SERVICE_ROLE'. Expected: api | worker | beat"
        exit 1
        ;;
esac
