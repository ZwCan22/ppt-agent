FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies change less often than source code, so install them first.
COPY requirements.lock.txt ./
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements.lock.txt \
    && python -m pip check

# Copy runtime code explicitly; local credentials and generated files stay out.
COPY app ./app
COPY worker.py alembic.ini ./
COPY migrations ./migrations

RUN groupadd --gid 10001 ppt \
    && useradd --uid 10001 --gid 10001 --no-log-init --no-create-home \
        --home-dir /app --shell /usr/sbin/nologin ppt \
    && mkdir -p /app/storage /app/logs \
    && chown 10001:10001 /app/storage /app/logs

USER 10001:10001

EXPOSE 8001

# Compose can override this default to run: python worker.py
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
