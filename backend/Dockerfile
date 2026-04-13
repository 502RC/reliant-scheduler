FROM python:3.12-slim AS base

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv pip install --system -e ".[dev]"

COPY . .

ENV PYTHONPATH=/app/src
FROM base AS dev
CMD ["uvicorn", "reliant_scheduler.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS prod
CMD ["uvicorn", "reliant_scheduler.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
