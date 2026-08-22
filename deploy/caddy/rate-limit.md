# Rate limit en Caddy (borde)

El Caddyfile completo vive en el VPS (`/etc/caddy/Caddyfile`) junto a la
landing `siberia.solutions`. Este directorio versiona **solo** el recorte de
abuso de Identity. No sustituye el fichero del host.

La API ya aplica cuotas en Redis (email, cuenta JWT, token de mesa). Caddy es
la primera línea **por IP**: corta floods groseros antes de llegar a FastAPI.

## Módulo

El handler `rate_limit` no forma parte del Caddy vanilla. Comprobar:

```bash
caddy list-modules | grep rate_limit
```

Si falta, construir un binario con xcaddy y sustituir `/usr/bin/caddy` (o la
ruta del paquete) **sin** tocar el bloque de la landing:

```bash
xcaddy build --with github.com/mholt/caddy-ratelimit
```

Validar y recargar:

```bash
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
```

`deploy_staging.py --validate-only` **no** modifica Caddy. El snippet se aplica
en el deploy real (Changelog).

## Snippet

Ver `identity-rate-limit.caddy`. Pegarlo dentro de los site blocks de
`camareros.siberia.solutions` y `negocio.siberia.solutions` (APIs). No aplicarlo
a `web.mesa` con umbrales estrictos: el NAT de la terraza comparte IP.

Umbrales de borde (más holgados que la API):

| Matcher | Eventos | Ventana |
|---|---|---|
| login | 20 | 1 min |
| registro | 10 | 1 min |
| POST CFC | 60 | 1 min |

El cupo real de CFC es por token de mesa en Redis (30 / 10 min).
