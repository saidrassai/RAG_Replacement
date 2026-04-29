# ── Build Stage ──────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1

RUN pip install --no-cache-dir uv==0.10.12

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/ ./apps/
COPY packages/ ./packages/

RUN uv sync --all-packages --no-dev

# ── Runtime Stage ────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1

RUN groupadd --system lattice && useradd --system --gid lattice --no-create-home lattice

RUN pip install --no-cache-dir uv==0.10.12

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/pyproject.toml /app/uv.lock /app/
COPY --from=builder /app/apps/ /app/apps/
COPY --from=builder /app/packages/ /app/packages/
COPY ops/ /app/ops/
COPY tests/ /app/tests/

RUN chown -R lattice:lattice /app
USER lattice

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

EXPOSE 8000

STOPSIGNAL SIGTERM

CMD ["uv", "run", "--package", "lattice-jit-api", "lattice-jit-api"]
