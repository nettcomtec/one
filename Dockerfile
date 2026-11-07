# syntax=docker/dockerfile:1
# Multi-stage: one image, runs api | worker | migrate (see docker-entrypoint.sh).

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# --- deps layer (cached unless pyproject changes) ---
# Install only the dependencies here: the package itself needs src/, which
# we deliberately keep out of this stage so the layer cache survives code edits.
FROM base AS deps
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    python -c "import tomllib;print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/req.txt && \
    pip install -r /tmp/req.txt

# --- runtime ---
FROM base AS runtime
# bring installed site-packages from deps
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY pyproject.toml docker-entrypoint.sh ./
COPY src/ ./src/
RUN chmod +x docker-entrypoint.sh && \
    pip install --no-deps . && \
    useradd --create-home --uid 10001 appuser
ENV PYTHONPATH=/app/src ONE_ROLE=api
USER appuser
EXPOSE 8000
# No image-level HEALTHCHECK: the same image runs as api (HTTP) and worker (no
# HTTP). The healthcheck is defined per-service in the stack, on the api only.
ENTRYPOINT ["./docker-entrypoint.sh"]
