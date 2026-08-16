# AGENTS.md — PersonalHostel Identity

## Project

**PersonalHostel Identity** is the **organization identity** server of the **PersonalHostel** family (Comander, Bar, Kitchen, TPV, this server). It stores the **permanent professional identity** (waiter / bar / kitchen): name, photo, QR/key. **It is not the LAN room node.** The host for tables and rounds is **Personal Bar**.

- GitHub repo: `jaminsmoke/PersonalHostel-Identity`
- Local folder: `AndroidStudioProjects/PersonalHosteleriaServer` (sibling of `PersonalComander` and `PersonalBar`)
- Version target: **v0.1** (no releases yet — `gh release list`; next version must be > latest)
- Local tests: **Docker Compose on this machine**. Staging/producción: VPS de Hostinger (Caddy + subdominios `siberia.solutions`).

If you are the agent continuing here: read this **entire** file before writing code. Do not implement rankings, marketplace, or table/round sync.

## Familia PersonalHostel

Familia de producto de hostelería. Owner GitHub: [`jaminsmoke`](https://github.com/jaminsmoke) (cuenta personal). **No** es [SiberIA-Solutions](https://github.com/SiberIA-Solutions) (empresa de desarrollo). No hay organización GitHub de producto: los repos se agrupan con **esta tabla**.

**Al nacer un miembro nuevo** (Kitchen, TPV, …) se añade una fila aquí **en todos** los `AGENTS.md` de la familia.

| App | Repo | Oficio | Kanban |
|---|---|---|---|
| **Personal Comander** | [`jaminsmoke/PersonalComander`](https://github.com/jaminsmoke/PersonalComander) | App del camarero (móvil vertical): mesas, comanda, cuenta profesional | [Project 9](https://github.com/users/jaminsmoke/projects/9) |
| **Personal Bar** | [`jaminsmoke/PersonalBar`](https://github.com/jaminsmoke/PersonalBar) | Puesto del negocio (tablet apaisada): nodo LAN `:8787`, colas, lista blanca, mapa | [Project 11](https://github.com/users/jaminsmoke/projects/11) |
| **PersonalHostel Identity** (este) | [`jaminsmoke/PersonalHostel-Identity`](https://github.com/jaminsmoke/PersonalHostel-Identity) | Registro canónico (Docker/VPS): camareros `:8080`, negocio `:8082` | [Project 10](https://github.com/users/jaminsmoke/projects/10) |

Kanban: cada app tiene el suyo. Cambio que necesite al otro lado → Detectado en **su** Project. Commander no llama a `:8082`.

## Stack (scaffold; the team may change it in Debate)

| Layer | Technology |
|---|---|
| API | Python 3.14 + FastAPI + Uvicorn |
| DB | PostgreSQL 16 |
| Orchestration | Docker Compose |
| API ports | **8080** (camareros) · **8082** (negocio) — dos servicios, dos BD |
| Postgres port | **5432** (dev machine only) |

`docker compose up --build` is the only supported local path.

## Relación con el resto

```
[Identidad — este repo]          cuentas, QR permanente, foto, revocación
        ▲
        │ HTTPS (login / alta)
        │
[Personal Bar]  ◄──LAN──►  [Personal Comander…]
  nodo de sala                 clientes de mapa + comandas
  lista blanca del local       (hace falta QR dado de alta en Bar)
```

| Repo | Oficio | Red |
|---|---|---|
| **PersonalHostel-Identity** (este) | Identidad de profesionales (y luego org/establecimiento) | Internet / VPS |
| Personal Bar | Expo barra + **nodo LAN** (mapa, rondas, tickets) | LAN del local |
| Personal Comander | Puesto de sala: mapa, tomar comanda, recoger | Cliente LAN de Bar; login contra este servidor |
| Personal Kitchen (futuro) | Tickets de comida | Cliente del nodo; login aquí |
| Personal TPV (futuro) | Cobro / contabilidad; puede heredar el nodo LAN | Login aquí |

Kanban de producto (Commander): ítem Detectado *Sala LAN: Personal Bar como nodo…* (`PVTI_lAHOBM87Yc4BgJWOzg2ZsaU`). Este servidor responde a la decisión: **QR permanente en base de datos de la org, no clave transitoria de dispositivo.** No reabrir ese ítem desde aquí.

## Modelo de identidad (acordado)

1. El profesional **se registra** con nombre, apellidos, **nick** (mote visible en barra/colas), foto y otros datos. El nick lo gestiona Commander; Bar lo consume en referencias coloquiales y puede mostrar el resto de la ficha en la gestión del negocio.
2. El servidor emite una **clave / QR permanente** (equivalente a un DNI de oficio). Vive en **nuestra** base de datos, no solo en el móvil.
3. Desinstalar e instalar Commander o Bar + **login** recupera la misma identidad y el mismo QR.
4. **Revocación / renovación** posibles; si no, la clave no cambia.
5. En el local: el camarero enseña o pasa el QR a **Personal Bar** → Bar lo añade a la lista blanca de **esa** red. Sin alta, estar en el Wi‑Fi no basta para tomar pedidos.
6. Más adelante (otro ítem, no este scaffold): rankings por establecimiento, dueños que ven profesionales, contacto. La identidad fija es el cimiento; **no** diseñes UUIDs de usar-y-tirar.

PII: nombre, foto, identificador. GDPR, retención y borrado hay que pensarlo antes de producción. En Docker local no hay autenticación dura ni HTTPS.

## Qué hay ahora (v0.1)

```
PersonalHosteleriaServer/
├── AGENTS.md                 # este archivo (léelo primero)
├── README.md                 # cómo levantar Docker y contrato /v1
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .kanbanrc.json.template
├── docs/
│   ├── changelog.md          # changelog v0.1
│   ├── openapi-camareros.json
│   └── openapi-negocio.json  # contratos OpenAPI versionados
├── .github/workflows/        # checks requeridos quality + integration + security
├── security/                 # política, excepciones caducables y documentación SBOM
├── services/identity/        # API FastAPI (identidad, QR, foto, OpenAPI)
│   ├── Dockerfile            # etapas runtime/test; producción sin tooling dev
│   ├── requirements.txt      # dependencias de ejecución
│   ├── requirements-dev.txt  # pytest, cobertura y Ruff
│   ├── pyproject.toml        # contrato Python 3.14, lint, formato y cobertura
│   ├── alembic/              # migraciones BD profesionales (incluye procedencia real/test/demo)
│   ├── alembic_negocio/      # migraciones BD negocio (incluye procedencia heredada y catálogo/sync)
│   ├── app/                  # main, auth, models, schemas, routes, storage, images
│   ├── scripts/              # export_openapi.py
│   └── tests/
├── services/identity-web/    # página de invitaciones (nginx + SPA vanilla, :8081)
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── 20-identity-web.sh    # genera config.js en runtime (IDENTITY_API_URL)
│   └── static/               # index.html, style.css, app.js
└── tools/
    ├── README.md
    ├── kanban-cli/
    └── agent-skills/
```

`docker compose up --build` levanta Postgres 16 + APIs en `:8080` y `:8082` +
Identity Web (página de invitaciones) en `:8081` + worker de email.

CI fija acciones por SHA e imágenes base por digest. El job `security` aplica
`pip-audit`, `actionlint`, `zizmor` y Trivy, y publica SARIF + SBOM SPDX durante
30 días. Sus umbrales y excepciones caducables viven en `security/`; no se deben
suprimir hallazgos directamente en el workflow. CodeQL usa default setup para
Python y Dependabot mantiene pip, Docker, Compose y Actions.

Los servicios de API usan UID/GID 10001 y Identity Web usa `nginx` (101). La
tarea Compose `fotos-permissions` es la única excepción root: es efímera,
idempotente, solo hace `chown` del volumen heredado y debe completar antes de
arrancar las APIs.

- `GET /health` → `{ "ok": true }`
- `GET /v1/meta` → servicio, rol `identity`, `status: schema`
- `GET /openapi.json` y `/docs` → spec del contrato `/v1`
- La API registra camareros, emite QR, hace login y gestiona la foto de perfil (ver `README.md`).

## Contrato API (implementado en v0.1)

Prefijo `/v1`. JSON. Español en mensajes de error de cara a apps. Los errores llevan además un `code` estable (`identity.*`).

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/v1/camareros/registro` | Alta: nombre, apellidos, email, password. Devuelve `id` + `qr` (payload firmado `phid1:...`) |
| POST | `/v1/auth/login` | Recupera sesión (JWT), perfil y el QR tras reinstalar |
| GET | `/v1/camareros/me` | Perfil de la sesión (incluye `foto_url`) |
| GET | `/v1/camareros/me/qr` | Payload del QR permanente |
| POST | `/v1/camareros/me/renovar` | Nueva credencial; la anterior deja de valer |
| POST | `/v1/camareros/me/revocar` | Invalida la credencial activa |
| GET | `/v1/camareros/me/visibilidad` | Visibilidad pública por campo (default: sensibles privados) |
| PUT | `/v1/camareros/me/visibilidad` | Actualiza la visibilidad (body parcial) |
| GET | `/v1/camareros/ficha` | Ficha pública por `?qr=` verificado (sin token; solo campos visibles) |
| POST | `/v1/camareros/me/foto` | Sube/reemplaza la foto de perfil (multipart) |
| GET | `/v1/camareros/me/foto` | Sirve la foto (WebP) |
| DELETE | `/v1/camareros/me/foto` | Borra la foto |

El QR es un payload firmado Ed25519 `phid1:<camarero_id>:<credencial_id>:<firma>`, **estable** entre reinstalaciones. La foto no viaja en el QR.

Fuera de v1: rankings. En v0.2, Identity incorpora la entidad de establecimiento, cuenta de negocio, membresías e invitaciones (con Identity Web `:8081` para aceptar por magic-link sin JWT); el mapa, las salas y la lista blanca LAN siguen siendo responsabilidad de Bar. Identity solo guarda un **espejo de respaldo** del layout de Bar (`PUT/GET /v1/establecimientos/{id}/layout`, tabla `layouts_establecimiento`) para restaurar el mapa en un dispositivo nuevo; no lo interpreta ni lo sirve a Commander.

Bar y Commander **no** copian usuarios a SQLite como fuente de verdad. Cachean la sesión. La verdad está aquí.

La procedencia de datos también es canónica aquí: camareros y cuentas aceptan
`data_origin = real|test|demo` al registrarse (`real` por defecto); establecimiento
y producto la heredan en servidor. `test/demo` requieren `ALLOW_NON_REAL_DATA=true`
(solo desarrollo); producción/VPS usa el default seguro `false`. El auditor
`python -m app.data_audit` es read-only y redacta PII por defecto.

### Catálogo y sincronización offline (v0.2)

Identity es también la fuente canónica del catálogo por establecimiento. Bar y
Commander mantienen mirrors Room/SQLite. Las escrituras offline nacen en un
outbox local y, al reconectar, se entregan mediante
`POST /v1/establecimientos/{id}/sync/operaciones` con UUID idempotente y revisión
base. PostgreSQL asigna la revisión global; el timestamp del cliente se audita
pero no decide conflictos.

La primera vertical soportada es `producto`: UUID estable, precio en céntimos,
categoría visible, destino explícito `barra|cocina`, disponibilidad y tombstone.
`GET .../catalogo` entrega snapshot, `GET .../sync/cambios` entrega deltas,
`GET/POST .../sync/conflictos` permite revisar y resolver, y
`GET/POST .../notificaciones` mantiene el aviso durable. La cuenta titular
escribe/resuelve; miembros activos solo leen catálogo y cambios. FCM/APNs, los
modales y el outbox Room se implementan en los repos Android sin cambiar este
contrato. No extender este mecanismo a salas, mesas, rondas o colas dentro del
ítem de catálogo.

## Qué no hacer

- No implementar sync de mesas, rondas ni colas de barra (eso es Bar + Commander).
- No mezclar este proceso con el nodo LAN (no abrir puertos de sala aquí).
- No rankings / marketplace en el primer entregable.
- No exigir este servidor en Commander para un solo tablet offline (regla de oro: no recortar Commander hasta que el otro lado exista).
- No subir secretos ni fotos reales de prueba al git.
- No saltarse Debate ni convertir draft→issue antes de Ejecutando.

## 🎯 Kanban workflow — GitHub Project

El trabajo se rastrea **solo** en el Project de este repo: [github.com/users/jaminsmoke/projects/10](https://github.com/users/jaminsmoke/projects/10) (`PVT_kwHOBM87Yc4BgQqZ`). **No** uses el kanban de Commander ni el de Bar.

Antes de crear, mover o cerrar ítems, lee:

- `tools/agent-skills/jarvis-github-kanban/SKILL.md`
- `tools/agent-skills/jarvis-github-agentuse/SKILL.md`

### Lifecycle

```
Detectado → Debate → Roadmap → Ejecutando → Verificando → Changelog
  Draft      Draft     Draft     Issue OPEN    Issue OPEN    Issue CLOSED
```

**Drafts** until `Ejecutando` — NEVER convert to issue before that.

**No skipping**: every item advances in order. Exception: `Cancelado` → Changelog.

**Version always > latest release**: consult `gh release list`, pick the next one (currently **v0.1**).

Bodies in UTF-8. On Windows do **not** pipe PowerShell `Get-Content` into the CLI (mojibake). Prefer Python or `--body-file` / `gh issue edit --body-file`.

#### 1. Detectado — Describir el problema a fondo

El body debe contener una descripción **muy completa** del item y del problema detectado. No perder contexto: cuanta más información se documente aquí, más fácil será retomarlo en el futuro.

- Rellenar TODAS las secciones de la plantilla con contenido específico, no placeholders.
- Incluir: archivos exactos, líneas de código, trazas, versiones, métricas, capturas si aplica.
- Describir el impacto real en el usuario/producto, no solo el síntoma técnico.

#### 2. Debate — Preguntar al usuario, NO decidir solo

**Regla de oro**: NUNCA pasar de Debate a Roadmap sin preguntar al usuario y recibir su aprobación explícita.

**Investigación previa (obligatoria al entrar en Debate, antes de listar opciones)**:

Al pasar a Debate — y **antes** de redactar `Alternativas` — investigar a fondo la causa y el espacio de soluciones. Documentar en el body la sección `Investigación previa`:

- Archivos, flujos y dependencias leídos (con rutas concretas: `docker-compose.yml`, `services/identity/app/main.py`, `requirements.txt`).
- Hipótesis de causa(s): los ítems suelen ser **multicausales**; no quedarse en el síntoma superficial.
- Patrones del proyecto / ecosistema relevantes (FastAPI, Postgres, Alembic, PII/GDPR, OpenAPI).
- Restricciones reales (Docker local sin HTTPS, PII, alcance de versión, contrato con Bar/Commander).
- Qué se descartó y por qué (aunque sea breve).
- **Estrategia de rama / integración**: ¿el cambio justifica rama dedicada (`feature/...`) vs trabajo en `main`? Anotar propuesta (nombre de rama, merge a `main` al Changelog, PRs si aplica). En cambios grandes (esquema, auth, migraciones, features transversales) la rama dedicada es la opción por defecto a contemplar.

Sin esta sección no se presentan las opciones. La investigación vive en Debate (no hincha Detectado); Detectado aporta el problema, Debate aporta el mapa de soluciones.

**Formato fijo de alternativas** — siempre presentar exactamente estas **4** opciones (en este orden):

1. **Solución raíz** 🌳 — va al origen del problema (modelo, arquitectura, contrato de datos, identidad de producto…). No se limita a “hacerlo bien dentro de lo que hay”; puede proponer rediseño o cambio de enfoque. Exige basarse en la `Investigación previa`. Si el problema es genuinamente superficial y no hay causa estructural, indicar **"no aplica"** con una frase de justificación (casi siempre sí conviene explorarla: un bug “simple” puede esconder una solución más robusta).
2. **Opción sólida** 🏗️ — la más correcta y robusta **dentro del diseño actual** (o con cambios acotados). Mejor arquitectura/mantenibilidad/escalabilidad sin replantear el sistema entero.
3. **Opción rápida** ⚡ — la más rápida de implementar. Puede coincidir o no con la sólida/raíz. Prioriza velocidad sobre perfección.
4. **Opción intermedia** ⚖️ — equilibrio entre profundidad y velocidad. Solo cuando exista un punto medio real; si no hay, indicar "no aplica".

Cada opción debe llevar:
- Descripción clara de la solución
- Número estimado de líneas/cambios
- Pros (✅) y contras (⚠️)

**Recomendación situacional (revisar por ítem)**: al final, recomendar una opción **según el contexto concreto de ese ítem**, no por regla mecánica. Orientaciones de partida (siempre contrastarlas con lo hallado en la investigación):

- Bug crítico en producción → suele favorecer la **rápida** (mitigar ya), sin ocultar si la raíz merece un follow-up.
- Mejora sin urgencia → suele favorecer la **sólida** o la **raíz**, según si el diseño actual basta o hay que replantear.
- Deuda técnica acumulada → suele favorecer la **intermedia** o la **raíz** si la deuda es estructural.
- Rediseño / identidad de producto / problema multicausal profundo → valorar explícitamente la **raíz**.

La recomendación debe citar **por qué** encaja este ítem (1–3 frases), no solo etiquetar el tipo.

**Proceso**:
- Añadir secciones `Investigación previa`, `Análisis`, `Alternativas` (con las 4 opciones) y `Recomendación` al body.
- **Parar y preguntar** al usuario. Solo cuando él decida, marcar `Decision: Aprobado` y mover a Roadmap.
- Si `Decision: Cancelado` → documentar motivo, convertir a issue, cerrar, mover a Changelog.
- Si `Decision: Diferido` → documentar motivo y condición, devolver a Detectado.

#### 3. Roadmap — Planificar en profundidad antes de tocar código

Con la decisión ya tomada y acordada en la fase anterior, detallar **mucho más** el plan de implementación.

- Investigar a fondo: leer archivos relacionados, dependencias, migraciones, efectos colaterales en Bar/Commander (solo contrato; no implementes esas apps aquí).
- Revisar si el plan acordado en Debate se queda corto — añadir lo que falte.
- Documentar: `Decisión acordada`, `Plan aprobado` (paso a paso), `Criterios de aceptación`, `Plan de verificación`, `Riesgos y recuperación`.
- Solo cuando el plan sea sólido y completo, mover a Ejecutando.

#### 4. Ejecutando — Implementar el plan

- Al entrar: convertir draft → issue, añadir labels (1 Tipo + 1 Área). **Aquí empieza el código.**
- Implementar siguiendo el plan detallado de Roadmap.
- Si algo difiere del plan original, **documentarlo** en el body (sección `Implementación`) explicando el porqué del cambio.
- Hacer commits locales con mensajes descriptivos.

#### 5. Verificando — Tests y comprobaciones exhaustivas

**No es solo levantar Docker.** Es verificar que el cambio funciona, no rompe nada y cumple estándares de calidad.

**Checklist obligatorio** (siempre ejecutar TODO lo aplicable):

1. **Compose**: `docker compose up --build` — API en `:8080`, Postgres healthy
2. **Health**: `GET /health` → `{"ok": true}`; `GET /v1/meta` → `status: schema` coherente
3. **Tests**: `docker compose run --rm identity-tests` — todos deben pasar y la cobertura de ramas no puede bajar del 82%. Crear tests para rutas nuevas (registro, login, QR, revocar)
4. **Contrato**: las rutas nuevas responden JSON documentado; errores de cara a apps en español
5. **Secretos**: `.env` no está en git; no hay fotos reales ni dumps con PII

**Validaciones adicionales según el área**:

- API → requests a `/v1/...`, códigos de error estables, OpenAPI si el ítem lo pide
- Datos → esquema aplicado, migraciones reversibles o documentadas, ping a Postgres
- Infra → Compose, volúmenes, puertos; no mezclar con el puerto de sala de Bar
- Docs → README y este archivo siguen siendo verdad
- Build/CI → imagen Docker construye en limpio; `quality` (Ruff + OpenAPI) e
  `integration` (tests + cobertura + auditoría) pasan

**Antes de pasar a Changelog**:
- Documentar TODO en el body: sección `Verificación` con checklist de lo ejecutado y resultados
- Si se encontraron y corrigieron errores preexistentes, documentarlos
- Hacer commit con los fixes de verificación
- Solo cuando todo esté verificado, pasar a Changelog

No aplica `./gradlew` (eso es Bar/Commander).

#### 6. Changelog — Cerrar, fechar y publicar

1. **Commit final** con mensaje descriptivo (si no se hizo ya en Verificando).
2. Anotar el **SHA del commit** en el body (sección `Commit`).
3. Mover status a `Changelog`.
4. Setear `Completado` (fecha) y `Completado exacto` (ISO-8601).
5. Añadir ✅ al título del issue.
6. Cerrar el issue (`gh issue close -r completed`).
7. **Push** a la rama de trabajo (normalmente `main`).

### CLI (all commands from this folder: PersonalHosteleriaServer)

```bash
KANBAN="bun run tools/kanban-cli/cli.ts"

# Primera vez en la máquina
cd tools/kanban-cli && bun install && cd ../..
copy .kanbanrc.json.template .kanbanrc.json   # Windows
# cp .kanbanrc.json.template .kanbanrc.json
$KANBAN config validate

# Create item
$KANBAN create --title "..." --tipo Feature --area API --priority Alta --version "v0.1"

# List
$KANBAN list

# Show item
$KANBAN show <itemId>

# Read/set body
$KANBAN body <itemId>              # read
$KANBAN body <itemId> --set "..."  # replace
$KANBAN body <itemId> --append "Investigación previa" --content "..."

# Change status (use set-field, NOT move)
$KANBAN set-field <itemId> --field "Status" --option "Debate"

# Convert draft → issue (only at Ejecutando)
$KANBAN convert-draft <itemId>
gh issue edit <N> --repo jaminsmoke/PersonalHostel-Identity --add-label "tipo:feature,area:api"

# Verificando
docker compose up --build
# curl http://localhost:8080/health
# curl http://localhost:8080/v1/meta
docker compose run --rm identity-tests

# Changelog: commit con SHA referenciable, cerrar, push
git add <files> && git commit -m "..."
$KANBAN body <itemId> --append "Commit" --content "SHA: \`$(git rev-parse --short HEAD)\`"
$KANBAN set-field <itemId> --field "Status" --option "Changelog"
$KANBAN set-field <itemId> --field "Completado" --date "YYYY-MM-DD"
$KANBAN set-field <itemId> --field "Completado exacto" --text "YYYY-MM-DDTHH:MM:SSZ"
gh issue edit <N> --repo jaminsmoke/PersonalHostel-Identity --title "✅ ..."
gh issue close <N> --repo jaminsmoke/PersonalHostel-Identity -r completed
git push

# Delete (IRREVERSIBLE, requires --yes)
$KANBAN delete <itemId> --yes
```

Áreas válidas en `--area` de **este** Project: `API`, `Datos`, `Build/CI`, `Docs`, `Infra`.

### Body sections by phase

Each item's body evolves through the lifecycle. The CLI generates a template at creation — **always fill it with specific content**, never leave the placeholders.

| Phase | Body sections | Reglas |
|---|---|---|
| **Detectado** | Contexto, Hallazgo y evidencia, Impacto, Alcance a debatir, Preguntas para Debate, Criterio para avanzar, Clasificación preliminar | Descripción MUY completa. No perder contexto. |
| **Debate** | + Investigación previa, Análisis, Alternativas (4: raíz / sólida / rápida / intermedia), Recomendación | Investigar antes de opciones. **PARAR y preguntar.** No avanzar sin aprobación explícita. |
| **Roadmap** | + Decisión acordada, Plan aprobado, Criterios de aceptación, Plan de verificación, Riesgos y recuperación | Investigar a fondo. Añadir lo que falte al plan. |
| **Ejecutando** | + Implementación (qué se hizo realmente, diferencias con el plan si las hay) | Convertir draft→issue al ENTRAR. Documentar cambios sobre el plan. |
| **Verificando** | + Verificación (Compose, health, tests, PII, comprobaciones específicas) | Ejecutar TODO lo aplicable. Arreglar errores preexistentes si se encuentran. |
| **Changelog** | + Commit (SHA). Setear `Completado`, `Completado exacto`. ✅ en título. | Commit → SHA al body → cerrar issue → push a main. |

### Fields reference

| Field | Type | Purpose |
|---|---|---|
| Status | SingleSelect | Detectado → ... → Changelog |
| Prioridad | SingleSelect | Alta, Media, Baja |
| Tipo | SingleSelect | Bug, Feature, Mejora, Tarea |
| Área principal | SingleSelect | API, Datos, Build/CI, Docs, Infra |
| Versión | SingleSelect | Sin asignar, v0.1, … |
| Decision | SingleSelect | Pendiente, Aprobado, Diferido, Cancelado |
| HighLighted | SingleSelect | Yes, No (for changelog highlights) |
| Inicio exacto | Text | ISO-8601 UTC timestamp |
| Inicio | Date | YYYY-MM-DD |
| Completado exacto | Text | ISO-8601 UTC (set on Changelog) |
| Completado | Date | YYYY-MM-DD (set on Changelog) |

### Labels canónicas

Cada Issue debe tener exactamente **1 label de Tipo + 1 label de Área**. Status,
Prioridad y Versión viven exclusivamente en campos del Project y no se duplican
como labels.

| Campo Tipo | Label | Uso |
|---|---|---|
| Bug | `tipo:bug` | Comportamiento incorrecto o regresión verificable |
| Feature | `tipo:feature` | Capacidad nueva observable para usuario o producto |
| Mejora | `tipo:mejora` | Calidad, rendimiento o mantenibilidad |
| Tarea | `tipo:tarea` | Trabajo operativo o técnico acotado |

| Área principal | Label | Incluye |
|---|---|---|
| API | `area:api` | HTTP, FastAPI, contratos `/v1`, OpenAPI |
| Datos | `area:datos` | Postgres, migraciones, fotos, integridad |
| Build/CI | `area:build-ci` | Docker, CI, deploys |
| Docs | `area:docs` | Documentación y contratos para agentes |
| Infra | `area:infra` | VPS, red, secretos, HTTPS |

Labels auxiliares permitidas cuando correspondan: `security`, `dependencies`,
`duplicate`, `invalid`, `wontfix`, `question`, `good first issue` y `help wanted`.
No usar los aliases antiguos `bug`, `enhancement` o `documentation`.

### Configuración local del Kanban

`.kanbanrc.json` contiene IDs específicos del Project y permanece gitignored.
`.kanbanrc.json.template` se versiona como referencia reproducible.

Tras crear, borrar o modificar opciones de un campo SingleSelect, todos sus IDs
pueden cambiar. Regenerar y validar inmediatamente:

```bash
$KANBAN config generate --project PVT_kwHOBM87Yc4BgQqZ
# El generador deja estos valores como REPLACE_ME; restaurarlos antes de continuar:
# repoId: R_kgDOT3ZYEg
# repo: jaminsmoke/PersonalHostel-Identity
$KANBAN config validate
```

Después, comprobar que ningún ítem perdió el valor del campo modificado, reponerlo
por nombre si fuera necesario y actualizar `.kanbanrc.json.template` con los IDs
nuevos. Nunca ejecutar `convert-draft` mientras `repoId` sea `REPLACE_ME`.

## Backlog (deriva de arranque — completado en v0.1)

El backlog de arranque quedó **completo y cerrado** en la release **v0.1** (2026-08-13). Los 6 ítems recorrieron el ciclo completo (Detectado → … → Changelog) y sus issues están cerrados:

| Pri | Área | Título | Issue |
|---|---|---|---|
| Alta | Datos | Esquema Postgres: camareros, credenciales/QR y revocaciones | [#1](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/1) |
| Alta | API | Registro de profesional y emisión de QR/clave permanente | [#2](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/2) |
| Alta | API | Login que recupera la misma identidad y el mismo QR tras reinstalar | [#3](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/3) |
| Media | API | Revocar y renovar la clave/QR permanente | [#4](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/4) |
| Media | Docs | OpenAPI de /v1: spec versionada y códigos de error estables | [#5](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/5) |
| Media | Datos | Foto de perfil del profesional (almacenamiento Docker local) | [#6](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/6) |

Detalle en [`docs/changelog.md`](docs/changelog.md). Los ítems nuevos entran por `Detectado` en el Project #10, con la misma regla: investigar, presentar las 4 alternativas y **parar a preguntar**.

## Code conventions

- **Language**: Spanish for user-facing API error messages; English for code symbols
- JSON `/v1`; do not invent a second prefix
- Persist identity in Postgres, not in app Room as source of truth
- Do not commit `.env`, real photos, or DB dumps with PII

## Keys & security

- `.env` gitignored; start from `.env.example`
- Docker local: HTTP. Production: HTTPS on VPS (Infra item, not the first Detectado)
- GraphQL token for kanban CLI: `GH_TOKEN` / `GITHUB_TOKEN` from `gh auth`

## License & business model

Same family as Commander: public MIT. Do not put paid premium code in this public repo.

## Cómo probar

Ver `README.md`. Desde esta carpeta: `docker compose up --build` para el stack y
`docker compose run --rm identity-tests` para la suite aislada.

## Dev tools

```
tools/kanban-cli/          # bun install; CLI = bun run tools/kanban-cli/cli.ts
tools/agent-skills/        # jarvis-github-kanban + jarvis-github-agentuse
.kanbanrc.json             # local Project IDs (gitignored)
.kanbanrc.json.template    # versioned reproducible reference
services/identity/pyproject.toml  # Ruff + pytest + cobertura de ramas (mínimo 82%)
```
