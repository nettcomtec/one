#!/usr/bin/env bash
# One image, three roles. ONE_ROLE selects what this container does.
set -euo pipefail

ROLE="${ONE_ROLE:-api}"

case "$ROLE" in
  api)
    exec uvicorn one.main:app --host 0.0.0.0 --port 8000 --proxy-headers
    ;;
  gateway)
    # WebSocket edge: many long-lived sockets, kept off the api request pool.
    exec uvicorn one.gateway:app --host 0.0.0.0 --port 8000 --proxy-headers --ws websockets
    ;;
  worker)
    # Drains each tenant's inbound Redis stream into Postgres + realtime events.
    exec python -m one.comms.runner
    ;;
  migrate)
    exec python -m one.db.migrate
    ;;
  *)
    echo "Unknown ONE_ROLE=$ROLE (expected api|gateway|worker|migrate)" >&2
    exit 64
    ;;
esac
