# AGENTS.md — Personal Hostelería Server

## Qué es esto

Servidor de **organización** para la familia Personal (Comander, Bar, Kitchen, TPV). **No es el nodo de sala LAN.** El host de mesas y comandas en el bar es **Personal Bar**. Este repo guarda la **identidad permanente del profesional** (camarero / barra / cocina) y, más adelante, establecimiento, altas y rankings.

- Carpeta local: `AndroidStudioProjects/PersonalHosteleriaServer` (hermana de `PersonalComander` y `PersonalBar`)
- Trabajo de **otro equipo / otro agente**. Commander y Bar solo consumen la API.
- Pruebas ahora: **Docker Compose en esta máquina**. Producción: VPS (aún no).

Si eres el agente que continúa aquí: lee este archivo entero antes de escribir código. No implementes rankings, marketplace ni sync de mesas.

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
| **PersonalHosteleriaServer** (este) | Identidad de profesionales (y luego org/establecimiento) | Internet / VPS |
| Personal Bar | Expo barra + **nodo LAN** (mapa, rondas, tickets) | LAN del local |
| Personal Comander | Puesto de sala: mapa, tomar comanda, recoger | Cliente LAN de Bar; login contra este servidor |
| Personal Kitchen (futuro) | Tickets de comida | Cliente del nodo; login aquí |
| Personal TPV (futuro) | Cobro / contabilidad; puede heredar el nodo LAN | Login aquí |

Kanban de producto (Commander): ítem Detectado *Sala LAN: Personal Bar como nodo…* (`PVTI_lAHOBM87Yc4BgJWOzg2ZsaU`). Este servidor responde a la decisión: **QR permanente en base de datos de la org, no clave transitoria de dispositivo.**

## Modelo de identidad (acordado)

1. El profesional **se registra** con nombre, apellidos, foto y otros datos.
2. El servidor emite una **clave / QR permanente** (equivalente a un DNI de oficio). Vive en **nuestra** base de datos, no solo en el móvil.
3. Desinstalar e instalar Commander o Bar + **login** recupera la misma identidad y el mismo QR.
4. **Revocación / renovación** posibles; si no, la clave no cambia.
5. En el local: el camarero enseña o pasa el QR a **Personal Bar** → Bar lo añade a la lista blanca de **esa** red. Sin alta, estar en el Wi‑Fi no basta para tomar pedidos.
6. Más adelante (otro ítem, no este scaffold): rankings por establecimiento, dueños que ven profesionales, contacto. La identidad fija es el cimiento; **no** diseñes UUIDs de usar-y-tirar.

PII: nombre, foto, identificador. GDPR, retención y borrado hay que pensarlo antes de producción. En Docker local no hay autenticación dura ni HTTPS.

## Qué hay ahora (scaffold)

```
PersonalHosteleriaServer/
├── AGENTS.md                 # este mapa (léelo primero)
├── README.md                 # cómo levantar Docker
├── docker-compose.yml
├── .env.example
├── .gitignore
└── services/identity/        # API mínima (health + meta)
    ├── Dockerfile
    ├── requirements.txt
    └── app/main.py
```

`docker compose up --build` debe levantar Postgres 16 + API en `:8080`.

- `GET /health` → `{ "ok": true }`
- `GET /v1/meta` → servicio, rol `identity`, `status: scaffold`

La API **no** registra camareros todavía. Eso lo implementa el equipo de este repo.

## Contrato API (intención, no implementado)

Prefijo `/v1`. JSON. Español en mensajes de error de cara a apps.

| Método | Ruta | Intención |
|---|---|---|
| POST | `/v1/camareros/registro` | Alta: nombre, apellidos, foto, datos. Devuelve `id` + representación del QR/clave |
| POST | `/v1/auth/login` | Recupera sesión (y el QR) tras reinstalar |
| GET | `/v1/camareros/me` | Perfil de la sesión |
| GET | `/v1/camareros/me/qr` | Payload para pintar el QR permanente |
| POST | `/v1/camareros/me/revocar` | Invalida la clave; emitir renovación |
| POST | `/v1/camareros/me/renovar` | Nueva clave; la anterior deja de valer |

Fuera de v1 de este scaffold: establecimientos, invitaciones a un Bar concreto, rankings.

El formato exacto del QR (UUID firmado, URL, etc.) lo decide este equipo; debe ser **estable** entre reinstalaciones.

Bar y Commander **no** copian usuarios a SQLite como fuente de verdad. Cachean la sesión. La verdad está aquí.

## Qué no hacer

- No implementar sync de mesas, rondas ni colas de barra (eso es Bar + Commander).
- No mezclar este proceso con el nodo LAN (no abrir puertos de sala aquí).
- No rankings / marketplace en el primer entregable.
- No exigir este servidor en Commander para un solo tablet offline (regla de oro: no recortar Commander hasta que el otro lado exista).
- No subir secretos ni fotos reales de prueba al git.

## Primeras tareas (para el agente de este repo)

1. Modelo persistente en Postgres (`camareros`, `credenciales` / QR, `revocaciones`).
2. Registro + login + emitir QR permanente + revocar/renovar.
3. Almacenamiento de foto (local en Docker; objeto en VPS después).
4. Documentar OpenAPI cuando las rutas dejen de ser scaffold.
5. Dejar `docker compose up` como único camino de desarrollo local.
6. Cuando haya remoto GitHub: equipo propio; Commander/Bar solo visibilidad.

## Stack de arranque (provisional)

El equipo puede cambiarlo, pero el scaffold usa:

- API: Python 3.12 + FastAPI + Uvicorn
- DB: PostgreSQL 16
- Orquestación: Docker Compose

Puerto API local: **8080**. Postgres: **5432** (solo máquina de desarrollo).

## Cómo probar

Ver `README.md`. Desde esta carpeta: `docker compose up --build`.
