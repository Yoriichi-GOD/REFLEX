FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    REFLEX_DATA_DIR=/app/data \
    MODEL_DIR=/app/data/model
ARG BUILD_COMMIT=working-tree
ENV BUILD_COMMIT=${BUILD_COMMIT}

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: -r /app/backend/requirements.txt
COPY backend /app/backend
COPY frontend /app/frontend
COPY demo /app/demo
COPY configs /app/configs
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN useradd --create-home --uid 10001 reflex \
    && mkdir -p /app/data \
    && chown -R reflex:reflex /app
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
