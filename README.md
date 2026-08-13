# PersonalHostel Identity

Servidor de **identidad** de la familia **PersonalHostel**.  
Repo: https://github.com/jaminsmoke/PersonalHostel-Identity  
Carpeta local: `PersonalHosteleriaServer`

No es el nodo de sala: eso es [Personal Bar](https://github.com/jaminsmoke/PersonalBar).

Mapa de producto y **flujo kanban completo** (Detectado → Changelog, Debate, CLI): [`AGENTS.md`](AGENTS.md). Setup corto de la CLI: [`tools/README.md`](tools/README.md).

## Levantar en local (Docker)

```bash
cd PersonalHosteleriaServer
copy .env.example .env
docker compose up --build
```

- API: http://localhost:8080/health
- Meta: http://localhost:8080/v1/meta
- Postgres: `localhost:5432` (usuario `hosteleria`, base `identity`)
- Esquema: aplicado por Alembic al arrancar (`alembic upgrade head`), tablas `camareros` y `credenciales`

## Tests

```bash
docker cp services/identity/requirements-dev.txt personalhosteleriaserver-identity-1:/app/
docker cp services/identity/tests personalhosteleriaserver-identity-1:/app/tests
docker compose exec identity pip install -r /app/requirements-dev.txt
docker compose exec identity python -m pytest /app/tests -v
```

Hay health y esquema Postgres (camareros + credenciales/QR). **No hay** registro/QR/login todavía.
