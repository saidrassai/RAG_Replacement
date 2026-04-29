FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.10.12

RUN useradd --system --create-home --home-dir /home/lattice lattice

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/ ./apps/
COPY packages/ ./packages/
COPY ops/ ./ops/

RUN uv sync --all-packages --no-dev
RUN chown -R lattice:lattice /app /home/lattice

USER lattice

EXPOSE 8000

STOPSIGNAL SIGTERM

CMD ["uv", "run", "--package", "lattice-jit-api", "lattice-jit-api"]
