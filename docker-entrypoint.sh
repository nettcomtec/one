#!/usr/bin/env bash
# One image, three roles. ONE_ROLE selects what this container does.
set -euo pipefail

ROLE="${ONE_ROLE:-api}"

case "$ROLE" in
  api)
    exec uvicorn one.main:app --host 0.0.0.0 --port 8000 --proxy-headers
    ;;
  worker)
    exec arq one.jobs.worker.WorkerSettings
    ;;
  migrate)
    exec python -m one.db.migrate
    ;;
  *)
    echo "Unknown ONE_ROLE=$ROLE (expected api|worker|migrate)" >&2
    exit 64
    ;;
esac
