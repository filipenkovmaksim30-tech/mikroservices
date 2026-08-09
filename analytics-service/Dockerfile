FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml .
COPY analytics_service ./analytics_service
COPY alembic.ini .
COPY alembic ./alembic

RUN pip install --no-cache-dir .

CMD ["python", "-m", "analytics_service.workers.kafka_consumer"]
