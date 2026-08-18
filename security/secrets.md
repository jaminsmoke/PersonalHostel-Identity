# Gestión de secretos de producción

PersonalHostel-Server mantiene temporalmente los secretos del VPS en
`/opt/identity/.env`. Este modelo está endurecido para un único servidor y deja
una frontera clara para migrar más adelante a SOPS/age o un gestor dedicado.

## Invariantes

- `.env` y cualquier temporal: `root:root`, modo `0600`.
- Directorios de backup: `0700`; dumps y logs sensibles: `0600`.
- Producción usa `docker-compose.prod.yml`: los secretos no tienen fallback.
- `check_production_secrets.py` se ejecuta antes de fetch, reset, build o
  migración y nunca imprime valores.
- No crear `.env.bak*` en el checkout. `.gitignore` bloquea `.env*` salvo
  `.env.example`.
- No rotar secretos durante un hardening de permisos o configuración.

Validación manual, sin mostrar valores:

```bash
python services/identity/scripts/deploy_staging.py --preflight-only
```

## Inventario y rotación

| Secreto | Consumidores | Impacto de rotación | Recuperación / orden |
|---|---|---|---|
| `SESSION_SECRET` | APIs y worker | Cierra sesiones e invalida tokens protegidos pendientes | Programar ventana, resolver invitaciones pendientes, cambiar todos los consumidores a la vez y comprobar login |
| `QR_SIGNING_KEY` | APIs, QR permanentes | Una sustitución simple invalida todos los QR emitidos | **No rotar** hasta implementar anillo multiclave con `key_id`, clave activa y claves anteriores de verificación |
| `POSTGRES_PASSWORD` | PostgreSQL, APIs, worker, exporter y tests remotos | Una rotación descoordinada corta toda persistencia | Añadir credencial nueva/ventana, actualizar consumidores, comprobar health y retirar la anterior |
| `EMAIL_PASSWORD` | Worker y Alertmanager | Detiene invitaciones y alertas por correo | Rotar en proveedor, actualizar ambos consumidores y enviar pruebas sintéticas |
| `GRAFANA_ADMIN_PASSWORD` | Grafana | Afecta acceso administrativo | Confirmar segundo acceso/basic auth, cambiar y verificar login antes de cerrar sesión |
| Clave SSH de deploy | Operador y `sshd` | Puede bloquear administración del VPS | Instalar clave nueva, probar una segunda sesión y solo después retirar la anterior |
| `HOSTINGER_API_KEY` | Herramientas locales | Afecta operaciones del proveedor | Mantener fuera del VPS, crear/restringir nueva, probar y revocar anterior |

Revisar trimestralmente propietarios, consumidores y necesidad de rotación. Una
incidencia o sospecha de exposición prevalece sobre el calendario.

## Edición y recuperación

1. Mantener abierta una sesión SSH de recuperación.
2. Crear el temporal fuera del checkout con `umask 077` y modo `0600`.
3. Ejecutar el preflight contra el temporal.
4. Instalarlo atómicamente como `/opt/identity/.env` con propietario `root` y
   modo `0600`; ejecutar `docker compose ... config --quiet`.
5. Comprobar health antes de cerrar la sesión.

No conservar copias históricas en claro. Antes de retirar las actuales debe
existir una copia de recuperación cifrada y probada fuera del checkout; su
ubicación y clave no se documentan en el repositorio. La eliminación o rotación
real requiere aprobación operativa separada.

## Evolución a la solución raíz

El contrato futuro debe entregar los mismos nombres de variables a Compose sin
acoplar la aplicación al proveedor. SOPS/age o un gestor dedicado sustituirá la
fuente del material, no los nombres consumidos. La migración deberá demostrar
bootstrap desde VPS vacío, recuperación de claves y rollback antes de retirar
el `.env` endurecido.
