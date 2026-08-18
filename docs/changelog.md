# Changelog

Todos los cambios notables de **PersonalHostel Server** (el servidor de identidad
de la familia PersonalHostel) se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado sigue [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Añadido

- **Política raíz de seguridad de CI y cadena de suministro**: CodeQL y
  Dependabot, auditoría Python/workflows/contenedores con `pip-audit`,
  `actionlint`, `zizmor` y Trivy, SBOM SPDX por imagen, pines inmutables y
  excepciones justificadas con caducidad. Los runtimes Identity y Web pasan a
  usuarios no privilegiados. ([#25](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/25), Build/CI)

- **Procedencia canónica de datos** `real|test|demo` para camareros y cuentas,
  heredada de forma inmutable por establecimientos y productos. Incluye política
  segura por entorno, auditor read-only con PII redactada, diagnóstico cross-DB y
  CI sobre PostgreSQL efímero. ([#21](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/21), Build/CI)

- **Catálogo canónico por establecimiento** con UUID estable, dinero en céntimos,
  destino `barra|cocina`, archivado lógico y lectura para miembros activos.
  Incluye protocolo reutilizable para mirrors offline: operaciones idempotentes,
  revisiones globales, deltas, conflictos con decisión humana y notificaciones
  durables. ([#19](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/19), Datos)
- Campo **`nick`** en `camareros` (migración `0008`): mote visible en barra/colas,
  distinto del nombre legal. Opcional en `POST /v1/camareros/registro` (compatibilidad);
  Commander lo exige en el alta. `PATCH /v1/camareros/me` lo actualiza. Login, `/me`
  y búsqueda por email lo exponen.

### Cambiado

- **Base de calidad CI** con contrato único en `pyproject.toml`, Ruff, cobertura
  de ramas mínima del 82%, runner Docker aislado y checks requeribles `quality`
  e `integration`. Las imágenes runtime ya no incluyen pytest ni los tests y CI
  cancela ejecuciones obsoletas, publica informes durante 14 días y conserva el
  anti-drift OpenAPI y la auditoría de procedencia. ([#23](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/23), Build/CI)

## [v0.1] - 2026-08-13

Primer entregable: identidad permanente del profesional — registro, QR firme,
login, revocación/renovación y foto de perfil — con contrato HTTP documentado.

### Añadido

- **Esquema Postgres** de `camareros`, `credenciales` y `app_config` con Alembic.
  ([#1](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/1), `66569f1`, Datos)
- **Registro de profesional** y emisión de **QR/clave permanente** firmado con
  Ed25519 (`phid1:<id>:<credencial>:<firma>`).
  ([#2](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/2), `f379f5f`, API)
- **Login** (email + password, JWT) que recupera la misma identidad y el mismo
  QR tras reinstalar.
  ([#3](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/3), `745920c`, API)
- **Revocar y renovar** la clave/QR: revocar invalida la credencial activa sin
  crear otra; renovar emite una credencial nueva y revoca las anteriores.
  ([#4](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/4), `5565b0c`, API)
- **Foto de perfil** autenticada (subir / servir / borrar), normalizada a un
  único avatar 256×256 WebP en volumen Docker, con abstracción `FotoStorage`
  lista para migrar a object storage.
  ([#6](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/6), `c6f177c`, Datos)

### Documentación

- **OpenAPI de /v1** versionado: spec enriquecida con ejemplos y códigos de error
  estables (`identity.*`), `docs/openapi.json` en git y gate de CI anti-drift.
  ([#5](https://github.com/jaminsmoke/PersonalHostel-Identity/issues/5), `9bf6681`, Docs)

[Unreleased]: https://github.com/jaminsmoke/PersonalHostel-Server/compare/v0.1...main
[v0.1]: https://github.com/jaminsmoke/PersonalHostel-Server/releases/tag/v0.1
