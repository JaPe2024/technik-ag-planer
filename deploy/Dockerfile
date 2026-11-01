# Build-Kontext ist das Hauptverzeichnis des Repositorys:
#   docker build -f deploy/Dockerfile .

FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH
# Systembibliotheken für die PDF-Erzeugung (WeasyPrint) und eine Schrift
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# ---------- Abhängigkeiten für den Betrieb ----------
FROM base AS build
COPY app/pyproject.toml app/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev
COPY app/ ./
RUN DJANGO_SECRET_KEY=nur-fuer-collectstatic DJANGO_ALLOWED_HOSTS=localhost DJANGO_READ_ENV_FILE=false \
    python manage.py collectstatic --noinput --settings=config.settings.prod

# ---------- Entwicklung (docker-compose.dev.yml) ----------
FROM base AS dev
COPY app/pyproject.toml app/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked
ENV DJANGO_SETTINGS_MODULE=config.settings.dev
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---------- Betrieb ----------
FROM python:3.13-slim AS prod
# Version für „Über die App“ – setzt release.yml aus dem Git-Tag
ARG APP_VERSION=Entwicklung
ENV APP_VERSION=${APP_VERSION} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/tmp/.cache \
    PATH=/opt/venv/bin:$PATH \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    DJANGO_READ_ENV_FILE=false
# Systembibliotheken für die PDF-Erzeugung (WeasyPrint) und eine Schrift
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build --chown=app:app /app /app
COPY --chmod=755 deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
USER app
EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
# Längere Zeitgrenze: Datei-Uploads gehen während der Anfrage weiter ins Google Drive
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-"]
