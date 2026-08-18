# Política de seguridad de CI y cadena de suministro

El job requerido `security` aplica una única política versionada a dependencias,
workflows, imágenes y configuración. Sus herramientas y superficies son:

- `pip-audit`: dependencias Python de ejecución y desarrollo.
- `actionlint` y `zizmor`: sintaxis y seguridad de GitHub Actions.
- Trivy: runtime Identity, PostgreSQL 16 y configuración del repo.
- SPDX JSON: un SBOM por cada una de las imágenes desplegables.
- CodeQL default setup: análisis estático Python administrado por GitHub.
- Dependabot: pip, Dockerfiles, Compose y GitHub Actions.

## Umbrales

- `pip-audit`: cualquier vulnerabilidad bloquea salvo excepción vigente.
- Trivy: HIGH/CRITICAL con versión corregida bloquea. Un hallazgo sin corrección
  permanece visible en el resumen y los artefactos, pero no fuerza una falsa
  actualización imposible.
- Trivy config: toda mala configuración HIGH/CRITICAL bloquea.
- `actionlint` y `zizmor --persona=auditor`: salida no válida/bloqueante falla.

Los artefactos duran 30 días e incluyen JSON, SARIF, SBOM SPDX y el resumen de
política. Los TAR usados para escanear se eliminan y no se publican. Los
contenedores de análisis reciben montajes mínimos y nunca el socket Docker.

## Excepciones

`exceptions.json` es la única vía para exceptuar un hallazgo. Cada entrada debe
ser estrecha y contener exactamente el origen que se quiere gobernar:

```json
{
  "tool": "pip-audit",
  "ids": ["CVE-YYYY-NNNN"],
  "component": "report-target:package-name",
  "reason": "No existe versión corregida; mitigación aplicada ...",
  "owner": "jaminsmoke",
  "expires": "2026-09-15"
}
```

`ids` admite varios identificadores exactos cuando todos comparten componente,
motivo y caducidad; no admite patrones. El validador rechaza campos vacíos,
fechas inválidas o vencidas, duplicados y
hallazgos bloqueantes no exceptuados. No se permiten comodines ni excepciones
globales. Al vencer, el CI obliga a renovar la justificación o remediar.

## Procedencia futura

Los SBOM locales son inventarios verificables del contenido construido, pero no
son todavía attestations persistentes. Cuando exista un registry de producción,
la publicación deberá usar BuildKit/buildx con `--sbom=true` y
`--provenance=mode=max`, conservar las attestations OCI junto a la imagen y
verificarlas antes del despliegue en VPS. Hasta entonces no se afirma procedencia
SLSA ni firma de imágenes.
