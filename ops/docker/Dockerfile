FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1

RUN pip install --no-cache-dir uv==0.10.12

WORKDIR /app

COPY . /app

RUN uv sync --all-packages

CMD ["uv", "run", "--package", "lattice-jit-api", "lattice-jit-api"]
