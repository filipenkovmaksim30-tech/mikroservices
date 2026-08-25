FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_NO_DEV=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-editable

COPY auth_service ./auth_service
COPY alembic.ini .
COPY alembic ./alembic

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

CMD [ "python", "-m", "uvicorn", "auth_service.api:app", "--host", "0.0.0.0", "--port", "8000"]