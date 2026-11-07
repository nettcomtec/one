# syntax=docker/dockerfile:1
# Multi-stage: one image, runs api | worker | migrate (see docker-entrypoint.sh).

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# --- deps layer (cached unless pyproject changes) ---
FROM base AS deps
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# --- runtime ---
FROM base AS runtime
# bring installed site-packages from deps
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY src/ ./src/
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh && \
    pip install --no-deps -e . && \
    useradd --create-home --uid 10001 appuser
ENV PYTHONPATH=/app/src ONE_ROLE=api
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)" || exit 1
ENTRYPOINT ["./docker-entrypoint.sh"]
