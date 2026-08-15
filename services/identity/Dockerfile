FROM python:3.12-slim AS runtime

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY alembic ./alembic
COPY alembic_negocio ./alembic_negocio
COPY alembic_negocio.ini .
COPY scripts ./scripts
COPY alembic.ini .

EXPOSE 8080
CMD ["sh", "/app/scripts/entrypoint.sh"]

FROM runtime AS test

COPY requirements-dev.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests

FROM runtime AS production
