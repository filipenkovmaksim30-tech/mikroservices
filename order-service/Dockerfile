FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml .
COPY messaging_lab ./messaging_lab
COPY alembic.ini .
COPY alembic ./alembic

RUN pip install --no-cache-dir .

CMD [ "python", "-m", "uvicorn", "messaging_lab.api:app", "--host", "0.0.0.0", "--port", "8000"]