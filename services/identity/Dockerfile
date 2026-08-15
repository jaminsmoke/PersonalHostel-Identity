FROM python:3.12-slim@sha256:dd29372629eeba2dd003fd9e9d35a5b8236c44727875a0364254b5127af88e65 AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY alembic ./alembic
COPY alembic_negocio ./alembic_negocio
COPY alembic_negocio.ini .
COPY scripts ./scripts
COPY alembic.ini .

FROM base AS runtime

RUN groupadd --gid 10001 identity \
    && useradd --uid 10001 --gid identity --no-create-home --shell /usr/sbin/nologin identity \
    && mkdir -p /app/data/fotos \
    && chown -R identity:identity /app/data

USER 10001:10001

EXPOSE 8080
CMD ["sh", "/app/scripts/entrypoint.sh"]

FROM runtime AS test

USER root
COPY requirements-dev.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests

USER 10001:10001

FROM runtime AS production
