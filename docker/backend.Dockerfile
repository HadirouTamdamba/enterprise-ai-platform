# Multi-stage build — slim, non-root, healthcheck-ready
FROM python:3.12-slim AS builder
WORKDIR /build
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir --prefix=/install ".[providers,ml]"

FROM python:3.12-slim
RUN useradd --create-home --uid 1000 eap
WORKDIR /srv
COPY --from=builder /install /usr/local
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
RUN mkdir -p data/uploads && chown -R eap:eap /srv
USER eap
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/v1/health/live')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
