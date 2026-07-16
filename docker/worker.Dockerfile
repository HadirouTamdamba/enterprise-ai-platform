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
RUN mkdir -p data/uploads && chown -R eap:eap /srv
USER eap
CMD ["celery", "-A", "app.workers.celery_app:celery_app", "worker", "--loglevel=info", "--concurrency=2"]
