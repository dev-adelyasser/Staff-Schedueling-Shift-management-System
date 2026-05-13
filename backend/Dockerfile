# ─────────────────────────────────────────────────────────────
#  Staff Scheduling System – Backend Dockerfile
#  Base  : python:3.11-slim  (minimal attack surface)
#  Pattern: multi-stage for lean production image
# ─────────────────────────────────────────────────────────────

# ── Stage 1: dependency builder ───────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed only to compile wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install into a prefix so we can copy it cleanly
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: production runtime ───────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN addgroup --system appgroup \
 && adduser  --system --ingroup appgroup appuser

WORKDIR /app

# Runtime-only system lib (libpq for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=appuser:appgroup . .

USER appuser

# ── Environment hygiene ───────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 8000

# CMD is overridden by docker-compose in dev (adds --reload)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
