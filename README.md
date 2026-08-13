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
- Esquema: aplicado por Alembic al arrancar (`alembic upgrade head`), tablas de profesionales y organización (`camareros`, `credenciales`, `cuentas_negocio`, `establecimientos`, `membresias` y `app_config`)

## API v1

### OpenAPI y contrato versionado

- Documentación interactiva: http://localhost:8080/docs (Swagger UI) y http://localhost:8080/redoc.
- Spec vivo: http://localhost:8080/openapi.json (`info.version` = `0.2.0`).
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

### Foto de perfil

La foto se guarda normalizada a un único avatar **256×256 WebP** (se descarta el original) en un volumen Docker (`fotos`), con la metadata (clave, mimetype, tamaño, fecha) en `camareros`.

- `POST /v1/camareros/me/foto` (`Authorization: Bearer <token>`, `multipart/form-data`, campo `foto`) → sube/reemplaza la foto. Acepta JPEG/PNG/WebP, máx. 2 MB. Respuesta `200`: `{ "foto_url": "/v1/camareros/me/foto" }`. `422` con `identity.foto_invalida` si el formato/tamaño no es válido.
- `GET /v1/camareros/me/foto` (`Authorization: Bearer <token>`) → sirve la imagen WebP con `Content-Type: image/webp`, `Cache-Control: private` y `ETag`. `404` con `identity.foto_inexistente` si no hay foto.
- `DELETE /v1/camareros/me/foto` (`Authorization: Bearer <token>`) → borra la foto (fichero + metadata). Respuesta `200`: `{ "foto_url": null }`. Idempotente.
- `GET /v1/camareros/me` y el login incluyen ahora `foto_url` (o `null`).
- Reemplazar o borrar elimina el fichero anterior. **Revocar el QR no borra la foto**; el borrado real es `DELETE` (y el futuro derecho de supresión GDPR).
- La foto **no** viaja en el QR.

### Renovar y revocar la clave/QR

- `POST /v1/camareros/me/renovar` (`Authorization: Bearer <token>`) → revoca las credenciales activas y crea una nueva. Respuesta `200`: `{ "qr": "phid1:..." }` (payload **nuevo**; el `id` del camarero no cambia). Tras renovar, Bar debe volver a dar de alta el QR.
- `POST /v1/camareros/me/revocar` (`Authorization: Bearer <token>`, body opcional `{ "motivo": "..." }`) → revoca la credencial activa **sin** crear otra. Respuesta `200`: `{ "status": "revocada" }`. La cuenta queda viva; login y `/me/qr` devuelven `409` hasta que se renueve.
- Ambos requieren Bearer. Si no hay credencial activa, `revocar` devuelve `409`. La sesión JWT sigue válida tras revocar, así se puede llamar a `renovar` sin deadlock.
- Recuperación sin sesión (reset por admin) queda fuera de v0.1.

### Borrar cuenta (derecho de supresión)

- `DELETE /v1/camareros/me` (`Authorization: Bearer <token>`, body `{ "password": "..." }`) → borra la cuenta de forma **irreversible**: camarero + credenciales (cascada) + foto del volumen + hash de password. Respuesta `200`: `{ "status": "borrada" }`.
- Requiere re-autenticación: `401` con `identity.password_incorrecta` si la password no cuadra (la cuenta queda intacta).
- Tras borrar, el JWT viejo queda inútil (el `sub` ya no resuelve → `401 identity.token_invalido`) y el login deja de funcionar.
- Las claves globales (`app_config`) no se tocan: el QR de los demás camareros sigue válido.

### Cuentas de negocio y establecimientos (v0.2)

Identity mantiene separadas tres entidades:

- `cuentas_negocio`: credencial de acceso y titular de la ficha del negocio.
- `establecimientos`: UUID canónico estable para que Bar y Comander identifiquen el negocio.
- `membresias`: relación N:N entre camareros y establecimientos, con rol `dueno` o `staff`.

La cuenta de negocio usa JWT con tipo `negocio`, independiente del JWT de camarero. Una cuenta puede vincularse opcionalmente a un camarero; al crear un establecimiento se genera automáticamente su membresía `dueno`.

Rutas principales:

- `POST /v1/auth/negocio/registro` y `POST /v1/auth/negocio/login` → alta y sesión de la cuenta de negocio.
- `DELETE /v1/auth/negocio/me` → supresión de cuenta y establecimientos, sin borrar camareros.
- `POST /v1/establecimientos` y `GET /v1/establecimientos/mios` → crear y listar establecimientos propios.
- `GET /v1/establecimientos/{id}` → consulta para la cuenta titular o un miembro activo.
- `POST/GET/DELETE /v1/establecimientos/{id}/miembros...` → gestionar membresías.
- `GET /v1/camareros/me/establecimientos` → establecimientos activos del profesional.

El QR `phid1` no incorpora establecimientos. Las salas, el mapa y la lista blanca siguen siendo responsabilidad de Personal Bar; las invitaciones y rankings quedan fuera de este incremento.

## Tests

```bash
docker compose up --build -d
docker compose exec identity python -m pytest /app/tests -v
```

Hay health, esquema Postgres, registro/login de camarero, perfil/QR (`/me`, `/me/qr`), foto de perfil, renovar, revocar, supresión GDPR, cuentas de negocio, establecimientos, membresías y OpenAPI.
