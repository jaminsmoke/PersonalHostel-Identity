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

Los archivos huérfanos detectados no se borran directamente. Tras aprobación
explícita se usa `deploy_staging.py --ref <rama> --quarantine-orphan-photos`:
crea primero un archivo verificado y manifiesto dentro de
`backups/quarantine/photos`, lo publica atómicamente y solo entonces retira los
archivos exactos del volumen. La cuarentena permite recuperación manual.

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

## Copia externa aprobada: Cloudflare R2 + restic

R2 Standard aporta API S3, 10 GB-mes y egress gratuitos para el volumen inicial.
`restic` 0.19.1 se instala desde el artefacto oficial fijado y su SHA-256 se
comprueba con `install_restic.sh`. Restic cifra y autentica localmente antes de
transferir; Cloudflare solo recibe ciphertext.

Bootstrap, una única vez y después de crear el bucket/token:

1. Crear un bucket privado dedicado y un token limitado a lectura/escritura de
   ese bucket. No reutilizar el token global de Cloudflare.
2. Generar una contraseña restic aleatoria y larga. Guardar la copia maestra en
   el custodio personal cifrado, fuera de Cloudflare y del VPS.
3. Crear `/opt/identity/.restic-password` como `root:root 0600`; es la copia
   operacional necesaria para el cron.
4. Añadir las variables R2 al `.env` mediante edición atómica, manteniendo
   `OFFSITE_BACKUP_ENABLED=false`.
5. Ejecutar `install_restic.sh`, después `offsite_backup.py init`, subir el
   último conjunto y ejecutar `verify-download`.
6. Solo tras una descarga verificada cambiar `OFFSITE_BACKUP_ENABLED=true`.

Cada backup diario sube el último conjunto completo con la etiqueta
`personalhostel-daily`, conserva 30 copias diarias y actualiza un estado local
sanitizado. También publica únicamente el timestamp de éxito mediante el
textfile collector de `node_exporter`: Alertmanager avisa si falta o supera 30
horas. `freshness --max-hours 30` permite la misma comprobación manual. Nunca se
imprimen endpoint con credenciales, secretos, rutas de fotos ni filas.

La recuperación externa requiere la contraseña restic maestra y una credencial
R2 de lectura. Si se pierde la contraseña, los objetos son irrecuperables. PITR
y WAL continúan como evolución fuera de este alcance.
