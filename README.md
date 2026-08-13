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
  "telefono": "+34600000000",
  "password": "contraseña-mín-8"
}
```

`telefono` es opcional. `password` es obligatoria (mín. 8 caracteres); solo se guarda su hash argon2 con salt, nunca en claro ni en las respuestas. Respuesta `201`:

```json
{
  "id": "<uuid del camarero>",
  "qr": "phid1:<uuid>:<firma-ed25519>"
}
```

- `409` si el email ya está registrado; `422` con mensajes en español si hay campos inválidos.
- El `qr` es el payload permanente para pintar el QR: formato `phid1` (versionado), firmado con Ed25519. El servidor verifica offline (Bar) usando la clave pública; el secreto real de la credencial vive en Postgres (`credenciales.secreto`), no en el QR.
- Clave de firma: `QR_SIGNING_KEY` (base64) si existe; si no, se genera y persiste en `app_config` (local).

### Login (recupera la misma identidad y el mismo QR)

`POST /v1/auth/login`

```json
{
  "email": "ana@example.com",
  "password": "contraseña-mín-8"
}
```

Respuesta `200`:

```json
{
  "token": "<jwt>",
  "camarero": {
    "id": "<uuid>",
    "nombre": "Ana",
    "apellidos": "García",
    "email": "ana@example.com",
    "telefono": "+34600000000"
  },
  "qr": "phid1:<uuid>:<firma-ed25519>"
}
```

- El `qr` es **idéntico** al del registro: tras reinstalar, login → misma identidad y mismo QR.
- `401` con `Email o contraseña incorrectos` si el email no existe, la password no cuadra o el camarero aún no tiene password (creados antes de la migración `0003`).
- JWT HS256, TTL 30 días por defecto (`SESSION_TTL_DAYS`); secreto `SESSION_SECRET` (env) o generado y persistido en `app_config` (local).

### Perfil y QR de la sesión

- `GET /v1/camareros/me` → perfil del camarero (`Authorization: Bearer <token>`).
- `GET /v1/camareros/me/qr` → `{ "qr": "phid1:<uuid>:<firma-ed25519>" }` (mismo QR permanente).
- Ambos devuelven `401` en español si falta el token o es inválido/caducado.

## Tests

```bash
docker cp services/identity/requirements-dev.txt personalhosteleriaserver-identity-1:/app/
docker cp services/identity/tests personalhosteleriaserver-identity-1:/app/tests
docker compose exec identity pip install -r /app/requirements-dev.txt
docker compose exec identity python -m pytest /app/tests -v
```

Hay health, esquema Postgres (camareros + credenciales + app_config), registro (`POST /v1/camareros/registro`), login (`POST /v1/auth/login`) y perfil/QR (`/me`, `/me/qr`).
