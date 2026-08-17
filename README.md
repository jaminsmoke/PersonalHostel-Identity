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
| `identity-negocio` | **8082** | `identity_negocio` | Negocio: cuentas, establecimientos, catálogo, sync/conflictos, membresías, invitaciones y outbox |

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

## Despliegue en staging (VPS)

El staging es producción en configuración (HTTPS, secretos reales, datos borrables). Corre en el VPS de Hostinger (la IP vive en `.env`, no en este README), detrás del **Caddy** ya instalado (que también sirve la landing `siberia.solutions`).

- Subdominios: `camareros.siberia.solutions` (:8080), `negocio.siberia.solutions` (:8082), `invitaciones.siberia.solutions` (:8081), `ficha.siberia.solutions` (:8081, ficha del camarero) y `carta.siberia.solutions` (:8081, carta pública del negocio).
- `docker-compose.prod.yml` es un override que publica las APIs/web solo en `127.0.0.1` y deja Postgres sin puerto externo (Caddy expone 80/443; UFW solo abre 22/80/443).
- El `.env` de producción vive en `/opt/identity/.env` (gitignored): secretos reales + `ALLOW_NON_REAL_DATA=false` + URLs públicas.

```bash
# Deploy (igual que dev, pero en el VPS): pull + up --build
python services/identity/scripts/deploy_staging.py
```

- Backup diario: `services/identity/scripts/backup_staging.sh` (cron en el VPS; dumps de ambas BD a `/opt/identity/backups`, retención 7 días).
- Caddyfile: bloques `reverse_proxy 127.0.0.1:8080` (camareros), `:8082` (negocio) y `:8081` (web — invitaciones, ficha y carta) añadidos a `/etc/caddy/Caddyfile` (la landing queda intacta).

### Observabilidad en el VPS (staging/producción)

Las APIs exponen `/metrics` (formato Prometheus, no público: Prometheus lo raspa por la red interna) y un access log JSON por request. El stack de observabilidad se levanta **solo** en el VPS, apilando un tercer fichero:

```bash
# En el VPS (/opt/identity)
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  -f docker-compose.observability.yml up -d
```

- Piezas: **Prometheus** (métricas + reglas de alerta), **Grafana** (dashboards), **Loki + Promtail** (logs de contenedores), **node_exporter** (host), **postgres_exporter** (BD) y **Alertmanager** (email).
- Acceso: Grafana en `https://grafana.siberia.solutions` con `basic_auth` de Caddy + login propio. `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` viven en `.env`.
- Alertas: `up == 0`, 5xx, Postgres caído, CPU alta y disco bajo → email a `ALERTMANAGER_ROUTE_TO` (usa el SMTP de `EMAIL_*`).
- Smoke sintético (no load test):
  ```bash
  CAMAREROS_API_URL=https://camareros.siberia.solutions \
  NEGOCIO_API_URL=https://negocio.siberia.solutions \
  k6 run services/identity/scripts/k6/smoke.js
  ```
- Fuera de alcance por ahora: cadvisor (evita montar `/var/run/docker.sock`) y tracing distribuido OTel.

## Cuentas de prueba canónicas (seed)

Para probar login y flujos cross de la familia se usan dos cuentas canónicas con `data_origin=real` (staging rechaza test/demo):

- Camarero: `camarero.test@example.com` (nick `camarero_test`)
- Negocio: `negocio.test@example.com` (`Negocio Test`, tipo `bar`)

```bash
# Dev (localhost): alta idempotente de las dos cuentas
python services/identity/scripts/seed_test_accounts.py

# Staging: apuntando a los subdominios HTTPS
CAMAREROS_API_URL=https://camareros.siberia.solutions \
NEGOCIO_API_URL=https://negocio.siberia.solutions \
python services/identity/scripts/seed_test_accounts.py
```

Las contraseñas viven en `.env` (gitignored); re-ejecutar el seed es seguro (409 → se omite).

## Seguridad de CI y cadena de suministro

Los PR y `main` ejecutan tres checks requeridos: `quality`, `integration` y
`security`. El tercero audita dependencias Python, workflows, Dockerfiles,
configuración e imágenes; genera SARIF y un SBOM SPDX por runtime Identity,
Identity Web y PostgreSQL. Las acciones se fijan por SHA, las bases Docker por
digest y los servicios de aplicación se ejecutan sin root.

La política, los umbrales y el formato de excepciones con caducidad están en
[`security/README.md`](security/README.md). Dependabot cubre pip, Docker, Compose
y GitHub Actions. CodeQL usa el default setup de GitHub para Python. En local,
la ruta soportada sigue siendo `docker compose up --build`.

Para migrar volúmenes `fotos` creados por versiones antiguas, Compose ejecuta
una tarea efímera `fotos-permissions` como root que solo ajusta ownership y
termina. Las APIs nunca heredan ese usuario: arrancan después como UID/GID 10001.

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

- El job requerido `quality` de `.github/workflows/quality-check.yml` falla si
  algún spec commiteado no coincide con el generado (anti-drift).

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
| 422 | `identity.procedencia_no_permitida` | El entorno bloquea altas `test/demo` |
| 422 | `identity.procedencia_incompatible` | Un vínculo mezclaría raíces de distinta procedencia |

### Registro de profesional

`POST /v1/camareros/registro` (servicio `:8080`)

```json
{
  "nombre": "Ana",
  "apellidos": "García",
  "email": "ana@example.com",
  "telefono": "+34600000000",
  "password": "contraseña-mín-8",
  "nick": "Anita",
  "data_origin": "real"
}
```

`telefono` y `nick` son opcionales (`nick`: 1–40 caracteres; mote visible en barra/colas). Commander lo exige en el alta; Bar lo consume y no lo edita. `password` es obligatoria (mín. 8 caracteres); solo se guarda su hash argon2 con salt, nunca en claro ni en las respuestas. Respuesta `201`:

```json
{
  "id": "<uuid del camarero>",
  "data_origin": "real",
  "qr": "phid1:<camarero_id>:<credencial_id>:<firma-ed25519>",
  "ficha_url": "https://ficha.example/ficha?qr=phid1:..."
}
```

- `ficha_url` es la URL pública de la ficha (configurable con `FICHA_URL_BASE`);
  los clientes pueden emitir el QR como esta URL para que escanearlo abra la web.
- La verificación del QR acepta tanto `phid1:...` como `https://...?qr=phid1:...`.
- `data_origin` es opcional y vale `real` por defecto. `test` y `demo` solo se
  admiten cuando el servidor tiene `ALLOW_NON_REAL_DATA=true`; en el VPS debe
  permanecer `false`. Es linaje inmutable, no un rol ni una autorización.
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
    "nick": "Anita",
    "data_origin": "real"
  },
  "qr": "phid1:<camarero_id>:<credencial_id>:<firma-ed25519>",
  "ficha_url": "https://ficha.example/ficha?qr=phid1:..."
}
```

- El `qr` es el de la **credencial activa**: tras reinstalar (sin renovar), login → misma identidad y mismo QR. `ficha_url` acompaña siempre al `qr`.
- `401` con `Email o contraseña incorrectos` si el email no existe, la password no cuadra o el camarero aún no tiene password.
- `409` con `Clave revocada. Renueva la clave` si la cuenta no tiene credencial activa.
- JWT HS256, TTL 30 días por defecto (`SESSION_TTL_DAYS`); secreto `SESSION_SECRET` (env) o generado y persistido en `app_config` (local).

### Perfil y QR de la sesión

- `GET /v1/camareros/me` → perfil del camarero (`Authorization: Bearer <token>`). Incluye `nick` o `null`.
- `PATCH /v1/camareros/me` (`{ "nick": "Anita" }`) → actualiza el nick. Solo la sesión del profesional.
- `GET /v1/camareros/me/qr` → `{ "qr": "phid1:..." }` (QR de la credencial activa).
- `GET /v1/camareros/me/establecimientos` → establecimientos activos del profesional (el servicio de camareros consulta al de negocio internamente).
- `/me/qr` devuelve `409` si no hay credencial activa.

### Visibilidad y ficha pública por QR

Cada camarero controla qué campos de su ficha son **públicos**. Por defecto solo
`nombre`, `apellidos` y `nick` son visibles; `email`, `telefono` y `foto` son
privados (opt-in).

- `GET /v1/camareros/me/visibilidad` (`Authorization: Bearer <token>`) →
  `{ "nombre": true, "apellidos": true, "nick": true, "email": false, "telefono": false, "foto": false }`.
- `PUT /v1/camareros/me/visibilidad` (body parcial, p. ej. `{ "email": true }`) →
  actualiza solo los campos enviados; el resto queda igual.
- `PUT /v1/camareros/me/visibilidad-establecimientos` (body `{ "visible": "..." }`)
  → preferencia del camarero sobre **aparecer en el directorio de otros
  establecimientos** (para invitación): `siempre | solo_libre | nunca` (default
  `nunca`, privacidad segura). Se gestiona desde Commander.
- `GET /v1/camareros/ficha?qr=<phid1>` → ficha **pública, sin token**: el QR
  verificado (firma Ed25519 + credencial activa) es la llave. Devuelve solo los
  campos visibles. `422 identity.qr_invalido` si el QR no es válido; `409
  identity.credencial_inactiva` si la credencial está revocada. Incluye
  `foto_url` (relativa) solo si `foto=true` y existe foto.
- `GET /v1/camareros/ficha/foto?qr=<phid1>` → sirve la foto **pública** (WebP)
  solo si `foto=true` y existe, con `Cache-Control: public` + `ETag`. Sin token;
  el QR es la llave. `404 identity.foto_inexistente` si no hay foto o no es
  visible; `422`/`409` igual que la ficha.
- La verificación del QR acepta tanto `phid1:...` como la URL
  `https://...?qr=phid1:...` (extrae el parámetro `qr`).

### Web de ficha pública

`identity-web` (SPA vanilla, nginx) sirve, además de `/invitaciones/<token>`,
las páginas públicas:

- `/ficha?qr=<phid1>` — ficha del camarero (nombre, nick y foto opt-in).
  Staging: `https://ficha.siberia.solutions`. Origen autorizado por CORS en el
  servicio de camareros (`IDENTITY_WEB_ORIGIN`); base configurada con `FICHA_URL_BASE`.
- `/negocio?slug=<slug>` — ficha pública del establecimiento enlazado (logo,
  nombre, tipo y nombre de su organización; nunca otros locales). Staging:
  `https://ficha.siberia.solutions/negocio?slug=`.
- `/carta?slug=<slug>` — carta pública del establecimiento (categorías y
  productos con precio). Staging: `https://carta.siberia.solutions/carta?slug=`.

Ficha de negocio y carta llaman al servicio de negocio (`NEGOCIO_API_URL`);
el origen web se autoriza por CORS (`IDENTITY_WEB_ORIGIN`).

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

- `cuentas_negocio`: identidad y credencial de la organización propietaria.
- `establecimientos`: UUID canónico y perfil operativo/público de cada local.
  Nombre, tipo y logo pueden ser distintos entre locales del mismo titular; sin
  logo propio se hereda el logo corporativo.
- `membresias`: relación N:N entre camareros y establecimientos, con rol `dueno` o `staff`. El `camarero_id` es un **UUID plano** (la FK real vive en la otra BD).

Rutas principales:

- `POST /v1/auth/negocio/registro` y `POST /v1/auth/negocio/login` → alta y sesión de la cuenta de negocio. El registro acepta `tipo_establecimiento` opcional del catálogo `bar | restaurante | cafeteria | pub | copas`, `camarero_vinculado_id` (validado contra el servicio de camareros) y `data_origin` opcional (`real` por defecto). El login devuelve `cuenta` con `tipo_establecimiento`, `logo_url` y procedencia.
- `GET/PATCH /v1/auth/negocio/me` → consulta/edita el nombre de la organización.
  El tipo legado de la cuenta se conserva como default compatible; Bar edita el
  tipo real en el establecimiento.
- `POST /v1/auth/negocio/me/logo` (multipart, campo `logo`) → sube/reemplaza el logo (256×256 WebP, máx. 2 MB). `GET`/`DELETE` lo sirven/borran.
- `DELETE /v1/auth/negocio/me` → supresión de cuenta y establecimientos, sin borrar camareros.
- `POST /v1/establecimientos` y `GET /v1/establecimientos/mios` → crear y listar establecimientos propios; el alta acepta `tipo_establecimiento` y usa el default legado de la cuenta si se omite.
- `GET /v1/establecimientos/{id}` → consulta para la cuenta titular o un miembro activo. `PATCH` (solo titular) edita nombre/tipo.
- `POST/GET/DELETE /v1/establecimientos/{id}/logo` → sobrescritura de logo por local. Al borrarla vuelve a heredarse el logo corporativo.
- `POST/GET/DELETE /v1/establecimientos/{id}/miembros...` → gestionar membresías.
- `GET /v1/keys/qr` → clave pública Ed25519 (en el servicio de camareros, `:8080`).
- `POST /v1/establecimientos/{id}/miembros/qr` → valida un QR (delegado al servicio de camareros) y crea la membresía.
- `GET /v1/establecimientos/{id}/camareros/buscar?email=...` → búsqueda exacta autorizada.
- `GET /v1/establecimientos/{id}/camareros/directorio?q=&limit=` → **directorio de
  camareros visibles para invitar**, **sin email** (privacidad). Solo camareros
  que han optado por ser vistos (`siempre` o `solo_libre`); **los dueños de
  establecimiento nunca aparecen** (pertenecen al dominio de establecimientos),
  y se excluyen los miembros del propio establecimiento y los de distinta
  `data_origin`. `libre` indica si el camarero no tiene membresía activa en
  ningún establecimiento; `foto_url` solo si la foto es pública (opt-in).
- `POST /v1/establecimientos/{id}/invitaciones` → crea una invitación. Acepta
  `email` (flujo clásico) **o** `camarero_id` (flujo por directorio: el email se
  resuelve en servidor y nunca se expone).
- `POST /v1/invitaciones/{token}/aceptar` → acepta con el JWT del camarero cuyo email coincide, **o** sin JWT (magic-link desde el email): token one-time + TTL 72h.
- `PUT/GET /v1/establecimientos/{id}/layout` → **copia de respaldo del layout** del mapa que Bar sube y restaura en un dispositivo nuevo. Solo la cuenta de negocio dueña.
- `POST/GET /v1/establecimientos/{id}/enlaces` y `POST .../enlaces/{enlace_id}/revocar|rotar` → enlaces públicos del establecimiento (solo la cuenta titular): `tipo` (`ficha_negocio | carta`) y `slug` opcional. Solo puede existir uno activo por tipo; crear es idempotente y rotar revoca el anterior. La respuesta incluye `url_publica`, construida con `FICHA_NEGOCIO_URL_BASE`/`CARTA_URL_BASE` para que Bar no hardcodee dominios.
- `GET /v1/enlaces/{slug}` → resolución pública **sin token**: devuelve `{ tipo, establecimiento_id }` con cache pública (`max-age=300`). Slug inexistente → `404`, revocado → `410`.
- `GET /v1/negocio/ficha?slug=<enlace>` → ficha pública **sin token** del único establecimiento enlazado: `establecimiento_id`, `nombre`, `tipo_establecimiento`, `logo_url` y `organizacion_nombre`. No filtra otros locales. Enlace `carta` o inexistente → `404`, revocado → `410`.
- `GET /v1/negocio/ficha/logo?slug=<enlace>` → logo público (WebP) con cache pública (`max-age=86400` + `ETag`).
- `GET /v1/negocio/carta?slug=<enlace>` → carta pública **sin token**: productos disponibles agrupados por categoría, con `precio_centimos` + `moneda`. Solo lectura; no expone `destino`/`revision`. Enlace `ficha_negocio` o inexistente → `404`, revocado → `410`.

El QR `phid1` no incorpora establecimientos. Las salas, el mapa y la lista blanca siguen siendo responsabilidad de Personal Bar.

### Catálogo canónico y mirrors offline

Identity es la fuente de verdad del catálogo. Room/SQLite en Bar, Commander y
clientes futuros son mirrors: sirven la última revisión confirmada cuando no hay
Internet y mantienen un outbox local para las intenciones creadas offline. Una
operación no puede aparecer en Identity hasta que el dispositivo recupere la red.

- `GET /v1/establecimientos/{id}/catalogo` → snapshot de productos activos +
  revisión global. La cuenta titular y los miembros activos pueden leerlo.
- `GET /v1/establecimientos/{id}/sync/cambios?desde=N` → change feed ordenado
  con snapshots y tombstones para actualizar el mirror.
- `POST /v1/establecimientos/{id}/sync/operaciones` → entrega una intención
  idempotente (`operation_id`, `device_id`, `base_revision`, timestamp cliente).
  En v0.2 implementa `producto` con `crear | actualizar | archivar`; solo la
  cuenta titular puede escribir.
- `GET /v1/establecimientos/{id}/sync/conflictos` y `POST .../{id}/resolver` →
  muestran estado base, estado canónico y propuesta; aceptar/rechazar vuelve a
  comprobar la revisión para no pisar cambios posteriores.
- `GET /v1/establecimientos/{id}/notificaciones` y `POST .../{id}/leer` → inbox
  durable para modal/bandeja de negocio. El payload incluye un deep-link lógico;
  FCM/APNs y la UI Android pertenecen a los repos de las apps.

El orden canónico se basa en revisiones asignadas por PostgreSQL y en el tiempo
de recepción del servidor. `client_created_at` se conserva para auditoría, pero
no gana conflictos por sí solo porque el reloj del dispositivo puede estar
desfasado. Los productos usan UUID estable, precio entero en céntimos, destino
explícito `barra | cocina` y archivado lógico.

La procedencia del establecimiento se hereda de su cuenta y la del producto se
hereda del establecimiento. Los clientes no pueden contradecirla ni cambiarla:
Bar/Commander solo declaran procedencia al crear la entidad raíz correspondiente.

### Identity Web (invitaciones por navegador)

`identity-web` sirve la página de aceptación en `:8081` y llama al **servicio de negocio** (`IDENTITY_API_URL`, default `http://localhost:8082`) para `POST /v1/invitaciones/{token}/aceptar` (magic-link, sin JWT).

## Tests

Los tests corren contra **bases de datos de prueba separadas** (`identity_camareros_test` y `identity_negocio_test`, creadas por `db-init`), no contra las de desarrollo.

```bash
docker compose run --rm identity-tests
```

El runner usa la etapa Docker `test`; las imágenes de ejecución usan `runtime` y
no contienen pytest, Ruff, informes ni el árbol `tests/`. Genera JUnit, cobertura
de ramas XML/HTML y un resumen Markdown en `build/reports/`. El umbral base es
**82%** y la cobertura actual es **82,71%**.

Hay health, esquema Postgres (dos BD), registro/login de camarero, perfil/QR,
foto de perfil, renovar, revocar, supresión GDPR, cuentas de negocio,
establecimientos, catálogo canónico, sync/conflictos, notificaciones,
membresías, clave pública QR, invitaciones (magic-link + CORS), espejo del
layout, outbox y OpenAPI (dos specs).

## Calidad y CI

El contrato común vive en `services/identity/pyproject.toml` y fija Python 3.14,
Ruff, pytest y cobertura. Para reproducir el job rápido localmente:

```bash
docker compose run --rm identity-tests ruff check app tests scripts
docker compose run --rm identity-tests ruff format --check app tests scripts
docker compose run --rm identity-tests python scripts/export_openapi.py --check
```

GitHub Actions ejecuta los checks tanto en pull requests como en `main`, cancela
ejecuciones obsoletas de la misma rama y usa permisos de solo lectura:

- `quality`: Ruff (lint y formato) + anti-drift OpenAPI.
- `integration`: Compose con PostgreSQL 16 + tests + cobertura de ramas +
  auditoría de procedencia. Conserva los informes 14 días.
- `family-contracts`: comprueba que los clientes de la familia (Bar,
  Commander e identity-web) no piden rutas que Identity ya no expone. Sparse-
  checkout de los repos públicos Bar y Commander, barrido de `app.js`, e
  informe en el summary del job con las rutas usadas por cada cliente y las
  públicas sin consumidor (aviso, no rojo). El job solo falla si un cliente
  llama una ruta que el OpenAPI ya no tiene. Local:

  ```bash
  docker compose run --rm identity-tests python scripts/check_family_contracts.py --selftest
  ```
- `migrations-check`: valida la reversibilidad de ambas cadenas Alembic con
  el ciclo `upgrade head → downgrade base → upgrade head` sobre Postgres
  efímero. Local:

  ```bash
  docker compose run --rm --entrypoint python identity-tests scripts/check_migrations.py
  ```

## Auditoría de procedencia (solo lectura)

Identity conserva `data_origin = real|test|demo` en camareros, cuentas,
establecimientos y productos. Las filas existentes se migran a `real`; el
sufijo histórico `Test` se usa solo para avisar de posibles incoherencias.

```bash
docker compose exec identity-camareros python -m app.data_audit
docker compose exec identity-camareros python -m app.data_audit --format json --fail-on-detected
```

El auditor consulta ambas BDs en transacciones read-only, redacta nombres y
emails, cuenta datos por procedencia y detecta linaje inconsistente o referencias
cross-DB huérfanas. Sale con `1` ante error y, con `--fail-on-detected`, con `2`
si encuentra datos no reales o incoherencias. `--show-pii` queda reservado para
revisión manual consciente y no se usa en CI. GitHub Actions valida el auditor
sobre PostgreSQL efímero; no tiene acceso al volumen local ni al futuro VPS.

## Reset de datos de desarrollo

```bash
sh services/identity/scripts/reset-dev.sh
```

Trunca las dos BD de desarrollo y elimina la BD legacy `identity` (huérfana tras el split). No toca las BD de prueba.
