# PersonalHostel Identity

Servidor de **identidad** de la familia **PersonalHostel**.  
Repo: https://github.com/jaminsmoke/PersonalHostel-Identity  
Carpeta local: `PersonalHosteleriaServer`

No es el nodo de sala: eso es [Personal Bar](https://github.com/jaminsmoke/PersonalBar).

Mapa de producto y **flujo kanban completo** (Detectado → Changelog, Debate, CLI): [`AGENTS.md`](AGENTS.md). Setup corto de la CLI: [`tools/README.md`](tools/README.md).

## Dos servicios, dos bases de datos

Desde el split de dominios, Identity se despliega como **dos servicios** con **bases de datos separadas**:

| Servicio | Puerto | BD | Dominio |
|---|---|---|---|
| `identity-camareros` | **8080** | `identity_camareros` | Identidad profesional: `camareros`, `credenciales`, `app_config` |
| `identity-negocio` | **8082** | `identity_negocio` | Negocio: `cuentas_negocio`, `establecimientos`, `layouts_establecimiento`, `membresias`, `invitaciones`, `email_outbox` |

Ambos comparten dos secretos inyectados por la orquestación (`SESSION_SECRET` y
`QR_SIGNING_KEY`) para que los JWT y el QR `phid1` funcionen entre servicios. Las
consultas que cruzan la frontera (buscar/verificar camarero, establecimientos de
un camarero) van por un **cliente interno** (`/internal/*`) con dos transportes:
`direct` (tests) y `http` (Compose/VPS).

- Camareros (identidad profesional): rutas `/v1/camareros/*`, `/v1/auth/login`, `/v1/keys/qr` → `:8080`.
- Negocio: rutas `/v1/auth/negocio/*`, `/v1/establecimientos/*`, `/v1/invitaciones/*` → `:8082`.
- `GET /health` y `GET /v1/meta` existen en ambos.

## Levantar en local (Docker)

```bash
cd PersonalHosteleriaServer
copy .env.example .env
docker compose up --build
```

- Camareros (API profesionales): http://localhost:8080/health
- Negocio (cuentas y establecimientos): http://localhost:8082/health
- Web de invitaciones: http://localhost:8081/invitaciones/<token> (llama al servicio de negocio)
- Postgres: `localhost:5432` (usuario `hosteleria`; bases `identity_camareros` y `identity_negocio`)
- Esquema: aplicado por Alembic al arrancar; una cadena por BD (`alembic` para camareros, `alembic_negocio` para negocio)

## API v1

### OpenAPI y contrato versionado

- Camareros: http://localhost:8080/docs · http://localhost:8080/openapi.json
- Negocio: http://localhost:8082/docs · http://localhost:8082/openapi.json
- `info.version` = `0.2.0` en ambos.
- Specs versionados en git: [`docs/openapi-camareros.json`](docs/openapi-camareros.json) y [`docs/openapi-negocio.json`](docs/openapi-negocio.json). Se regeneran con:

  ```bash
  python services/identity/scripts/export_openapi.py          # escribe docs/openapi-*.json
  python services/identity/scripts/export_openapi.py --check  # falla si difieren del vivo
  ```

- El workflow `.github/workflows/openapi-check.yml` falla si algún spec commiteado no coincide con el generado (anti-drift).

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

`POST /v1/camareros/registro` (servicio `:8080`)

```json
{
  "nombre": "Ana",
  "apellidos": "García",
  "email": "ana@example.com",
  "telefono": "+34600000000",
  "password": "contraseña-mín-8",
  "nick": "Anita"
}
```

`telefono` y `nick` son opcionales (`nick`: 1–40 caracteres; mote visible en barra/colas). Commander lo exige en el alta; Bar lo consume y no lo edita. `password` es obligatoria (mín. 8 caracteres); solo se guarda su hash argon2 con salt, nunca en claro ni en las respuestas. Respuesta `201`:

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

`POST /v1/auth/login` (servicio `:8080`)

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
    "telefono": "+34600000000",
    "nick": "Anita"
  },
  "qr": "phid1:<camarero_id>:<credencial_id>:<firma-ed25519>"
}
```

- El `qr` es el de la **credencial activa**: tras reinstalar (sin renovar), login → misma identidad y mismo QR.
- `401` con `Email o contraseña incorrectos` si el email no existe, la password no cuadra o el camarero aún no tiene password.
- `409` con `Clave revocada. Renueva la clave` si la cuenta no tiene credencial activa.
- JWT HS256, TTL 30 días por defecto (`SESSION_TTL_DAYS`); secreto `SESSION_SECRET` (env) o generado y persistido en `app_config` (local).

### Perfil y QR de la sesión

- `GET /v1/camareros/me` → perfil del camarero (`Authorization: Bearer <token>`). Incluye `nick` o `null`.
- `PATCH /v1/camareros/me` (`{ "nick": "Anita" }`) → actualiza el nick. Solo la sesión del profesional.
- `GET /v1/camareros/me/qr` → `{ "qr": "phid1:..." }` (QR de la credencial activa).
- `GET /v1/camareros/me/establecimientos` → establecimientos activos del profesional (el servicio de camareros consulta al de negocio internamente).
- `/me/qr` devuelve `409` si no hay credencial activa.

### Foto de perfil

La foto se guarda normalizada a un único avatar **256×256 WebP** en un volumen Docker (`fotos`), con la metadata en `camareros`.

- `POST /v1/camareros/me/foto` (multipart, campo `foto`) → sube/reemplaza. JPEG/PNG/WebP, máx. 2 MB. Respuesta `200`: `{ "foto_url": "/v1/camareros/me/foto" }`. `422 identity.foto_invalida` si no es válido.
- `GET /v1/camareros/me/foto` → sirve WebP con `Cache-Control: private` y `ETag`. `404 identity.foto_inexistente` si no hay.
- `DELETE /v1/camareros/me/foto` → borra. Idempotente.
- La foto **no** viaja en el QR.

### Renovar y revocar la clave/QR

- `POST /v1/camareros/me/renovar` → revoca las credenciales activas y crea una nueva. Respuesta `200`: `{ "qr": "phid1:..." }`.
- `POST /v1/camareros/me/revocar` (body opcional `{ "motivo": "..." }`) → revoca la credencial activa **sin** crear otra. Respuesta `200`: `{ "status": "revocada" }`.

### Borrar cuenta (derecho de supresión)

- `DELETE /v1/camareros/me` (body `{ "password": "..." }`) → borra la cuenta de forma **irreversible**: camarero + credenciales (cascada) + foto. Respuesta `200`: `{ "status": "borrada" }`.
- Requiere re-autenticación: `401 identity.password_incorrecta` si la password no cuadra.

### Cuentas de negocio y establecimientos (v0.2, servicio `:8082`)

- `cuentas_negocio`: credencial de acceso y titular de la ficha del negocio.
- `establecimientos`: UUID canónico estable para que Bar y Comander identifiquen el negocio.
- `membresias`: relación N:N entre camareros y establecimientos, con rol `dueno` o `staff`. El `camarero_id` es un **UUID plano** (la FK real vive en la otra BD).

Rutas principales:

- `POST /v1/auth/negocio/registro` y `POST /v1/auth/negocio/login` → alta y sesión de la cuenta de negocio. El registro acepta `tipo_establecimiento` opcional del catálogo `bar | restaurante | cafeteria | pub | copas` y `camarero_vinculado_id` (validado contra el servicio de camareros). El login devuelve `cuenta` con `tipo_establecimiento` y `logo_url`.
- `POST /v1/auth/negocio/me/logo` (multipart, campo `logo`) → sube/reemplaza el logo (256×256 WebP, máx. 2 MB). `GET`/`DELETE` lo sirven/borran.
- `DELETE /v1/auth/negocio/me` → supresión de cuenta y establecimientos, sin borrar camareros.
- `POST /v1/establecimientos` y `GET /v1/establecimientos/mios` → crear y listar establecimientos propios.
- `GET /v1/establecimientos/{id}` → consulta para la cuenta titular o un miembro activo.
- `POST/GET/DELETE /v1/establecimientos/{id}/miembros...` → gestionar membresías.
- `GET /v1/keys/qr` → clave pública Ed25519 (en el servicio de camareros, `:8080`).
- `POST /v1/establecimientos/{id}/miembros/qr` → valida un QR (delegado al servicio de camareros) y crea la membresía.
- `GET /v1/establecimientos/{id}/camareros/buscar?email=...` → búsqueda exacta autorizada.
- `POST /v1/establecimientos/{id}/invitaciones` → crea una invitación por email.
- `POST /v1/invitaciones/{token}/aceptar` → acepta con el JWT del camarero cuyo email coincide, **o** sin JWT (magic-link desde el email): token one-time + TTL 72h.
- `PUT/GET /v1/establecimientos/{id}/layout` → **copia de respaldo del layout** del mapa que Bar sube y restaura en un dispositivo nuevo. Solo la cuenta de negocio dueña.

El QR `phid1` no incorpora establecimientos. Las salas, el mapa y la lista blanca siguen siendo responsabilidad de Personal Bar.

### Identity Web (invitaciones por navegador)

`identity-web` sirve la página de aceptación en `:8081` y llama al **servicio de negocio** (`IDENTITY_API_URL`, default `http://localhost:8082`) para `POST /v1/invitaciones/{token}/aceptar` (magic-link, sin JWT).

## Tests

```bash
docker compose up --build -d
docker compose exec identity-camareros python -m pytest tests -v
```

Hay health, esquema Postgres (dos BD), registro/login de camarero, perfil/QR, foto de perfil, renovar, revocar, supresión GDPR, cuentas de negocio, establecimientos, membresías, clave pública QR, invitaciones (magic-link + CORS), espejo del layout, outbox y OpenAPI (dos specs).
