FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DASHBOARD_EVENT_STORE_PATH=/data/dashboard.db

WORKDIR /app

COPY pyproject.toml README.md ./
COPY dashboard_service ./dashboard_service

RUN pip install --no-cache-dir .

RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /data \
    && chown app:app /data
USER app

EXPOSE 8090
VOLUME ["/data"]

CMD ["uvicorn", "dashboard_service.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090"]
