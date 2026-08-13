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
- Esquema: aplicado por Alembic al arrancar (`alembic upgrade head`), tablas `camareros`, `credenciales` y `app_config`

## API v1

### Registro de profesional

`POST /v1/camareros/registro`

```json
{
  "nombre": "Ana",
  "apellidos": "García",
  "email": "ana@example.com",
  "telefono": "+34600000000"
}
```

`telefono` es opcional. Respuesta `201`:

```json
{
  "id": "<uuid del camarero>",
  "qr": "phid1:<uuid>:<firma-ed25519>"
}
```

- `409` si el email ya está registrado; `422` con mensajes en español si hay campos inválidos.
- El `qr` es el payload permanente para pintar el QR: formato `phid1` (versionado), firmado con Ed25519. El servidor verifica offline (Bar) usando la clave pública; el secreto real de la credencial vive en Postgres (`credenciales.secreto`), no en el QR.
- Clave de firma: `QR_SIGNING_KEY` (base64) si existe; si no, se genera y persiste en `app_config` (local).

## Tests

```bash
docker cp services/identity/requirements-dev.txt personalhosteleriaserver-identity-1:/app/
docker cp services/identity/tests personalhosteleriaserver-identity-1:/app/tests
docker compose exec identity pip install -r /app/requirements-dev.txt
docker compose exec identity python -m pytest /app/tests -v
```

Hay health, esquema Postgres (camareros + credenciales + app_config) y registro (`POST /v1/camareros/registro`). **No hay** login todavía.
