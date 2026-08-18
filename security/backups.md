# Política de backup y recuperación

## Objetivos y cobertura

- RPO inicial: 24 horas. RTO objetivo: 2 horas.
- Cada conjunto válido contiene `camareros.dump`, `negocio.dump`,
  `fotos.tar.gz` y `manifest.json` con checksums, tamaños, commit, versión de
  PostgreSQL, revisiones Alembic y ventana UTC.
- Los conjuntos se construyen en un directorio `.partial` con `umask 077` y
  solo se publican al completarse. Un fallo no cambia el puntero `latest`.
- Retención local: siete días, conservando siempre el último conjunto válido.
  Los dumps SQL históricos anteriores no se convierten ni eliminan en esta fase.

## Operación

El cron y los despliegues llaman a:

```sh
bash services/identity/scripts/backup_staging.sh
```

Verificación no destructiva del último conjunto:

```sh
python3 services/identity/scripts/backup_restore.py verify
```

Drill aislado (crea, valida y retira las dos bases temporales):

```sh
python services/identity/scripts/deploy_staging.py --ref main --backup-restore-drill
```

El restaurador rechaza las bases activas y cualquier nombre que no termine en
`_restore_test`. Nunca extrae fotos sobre el volumen activo. La salida solo
incluye conteos y duración: no muestra PII, hashes de contraseña, tokens, QR ni
rutas de fotos.

## Fallos y recuperación

1. Si `backup` falla, conservar el último conjunto señalado por `latest` y
   revisar el error sanitizado; no ejecutar retención manual.
2. Si un checksum falla, aislar el conjunto y usar el último válido anterior.
3. Si el drill falla, las bases temporales se intentan retirar en `finally`.
   Confirmar su ausencia antes de reintentar.
4. Para volver al mecanismo anterior, restaurar el script desde el commit
   previo y desactivar temporalmente el cron nuevo. No borrar conjuntos.

## Recuperación desde un VPS vacío

1. Recuperar acceso SSH y el repositorio; fijar el commit del manifiesto.
2. Recuperar `.env` desde el custodio cifrado separado y aplicar `0600`.
3. Instalar Docker/Compose, recrear red y volúmenes, sin publicar PostgreSQL.
4. Descargar y descifrar localmente un conjunto externo; verificar manifiesto.
5. Ejecutar primero un `restore-drill`; medir duración y revisar invariantes.
6. Con una ventana aprobada, restaurar las bases y fotos mediante un runbook de
   emergencia revisado por dos pasos. El CLI ordinario no permite producción.
7. Aplicar migraciones, arrancar servicios y comprobar health/meta y HTTPS.
8. Restaurar Caddy, cron, observabilidad y DNS; confirmar el RPO real.

## Puerta para copia externa

No hay proveedor ni credenciales configurados en este cambio. Antes de activar
el Hito B se compararán almacenamiento S3 compatible u otra copia externa por
región, coste, durabilidad, inmutabilidad, egress y recuperación. Requisitos no
negociables: cifrado en el VPS antes de transferir, clave fuera del proveedor,
credencial de mínimo privilegio, checksum tras descarga, 30 días de retención y
alerta de antigüedad superior a 26–30 horas. PITR/WAL queda como evolución.
