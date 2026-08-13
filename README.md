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

### OpenAPI y contrato versionado

- Documentación interactiva: http://localhost:8080/docs (Swagger UI) y http://localhost:8080/redoc.
- Spec vivo: http://localhost:8080/openapi.json (`info.version` = `0.1.0`).
- Spec versionado en git: [`docs/openapi.json`](docs/openapi.json). Se regenera con:

  ```bash
  python services/identity/scripts/export_openapi.py          # escribe docs/openapi.json
  python services/identity/scripts/export_openapi.py --check  # falla si difiere del vivo
  ```

- El workflow `.github/workflows/openapi-check.yml` falla si el spec commiteado no coincide con el generado (anti-drift).

### Errores y códigos estables

Toda respuesta de error lleva `detail` (mensaje en español) y `code` (código estable para que los clientes ramifiquen sin parsear el mensaje):

```json
{ "detail": "Clave revocada. Renueva la clave", "code": "identity.credential_revoked" }
```

| HTTP | `code` | Cuándo |
|---|---|---|
| 401 | `identity.credenciales_invalidas` | Login con email/password incorrectos |
| 401 | `identity.token_invalido` | Bearer faltante, inválido o caducado |
| 409 | `identity.email_ya_registrado` | Registro con email ya existente |
| 409 | `identity.credential_revoked` | Cuenta sin credencial activa |
| 422 | `identity.validation_error` | Cuerpo inválido (`detail` es lista de mensajes) |

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
  "qr": "phid1:<camarero_id>:<credencial_id>:<firma-ed25519>"
}
```

- `409` si el email ya está registrado; `422` con mensajes en español si hay campos inválidos.
- El `qr` se liga a la **credencial activa**: formato `phid1` (versionado), firmado con Ed25519 sobre `phid1:<camarero_id>:<credencial_id>`. Bar verifica offline con la clave pública; el secreto real de la credencial vive en Postgres (`credenciales.secreto`), no en el QR.
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
  "qr": "phid1:<camarero_id>:<credencial_id>:<firma-ed25519>"
}
```

- El `qr` es el de la **credencial activa**: tras reinstalar (sin renovar), login → misma identidad y mismo QR.
- `401` con `Email o contraseña incorrectos` si el email no existe, la password no cuadra o el camarero aún no tiene password (creados antes de la migración `0003`).
- `409` con `Clave revocada. Renueva la clave` si la cuenta no tiene credencial activa (hay que renovar desde una sesión con Bearer válido).
- JWT HS256, TTL 30 días por defecto (`SESSION_TTL_DAYS`); secreto `SESSION_SECRET` (env) o generado y persistido en `app_config` (local).

### Perfil y QR de la sesión

- `GET /v1/camareros/me` → perfil del camarero (`Authorization: Bearer <token>`).
- `GET /v1/camareros/me/qr` → `{ "qr": "phid1:<camarero_id>:<credencial_id>:<firma-ed25519>" }` (QR de la credencial activa).
- Ambos devuelven `401` en español si falta el token o es inválido/caducado.
- `/me/qr` devuelve `409` si no hay credencial activa.

### Renovar y revocar la clave/QR

- `POST /v1/camareros/me/renovar` (`Authorization: Bearer <token>`) → revoca las credenciales activas y crea una nueva. Respuesta `200`: `{ "qr": "phid1:..." }` (payload **nuevo**; el `id` del camarero no cambia). Tras renovar, Bar debe volver a dar de alta el QR.
- `POST /v1/camareros/me/revocar` (`Authorization: Bearer <token>`, body opcional `{ "motivo": "..." }`) → revoca la credencial activa **sin** crear otra. Respuesta `200`: `{ "status": "revocada" }`. La cuenta queda viva; login y `/me/qr` devuelven `409` hasta que se renueve.
- Ambos requieren Bearer. Si no hay credencial activa, `revocar` devuelve `409`. La sesión JWT sigue válida tras revocar, así se puede llamar a `renovar` sin deadlock.
- Recuperación sin sesión (reset por admin) queda fuera de v0.1.

## Tests

```bash
docker cp services/identity/requirements-dev.txt personalhosteleriaserver-identity-1:/app/
docker cp services/identity/tests personalhosteleriaserver-identity-1:/app/tests
docker compose exec identity pip install -r /app/requirements-dev.txt
docker compose exec identity python -m pytest /app/tests -v
```

Hay health, esquema Postgres (camareros + credenciales + app_config), registro, login, perfil/QR (`/me`, `/me/qr`), renovar, revocar y OpenAPI.
