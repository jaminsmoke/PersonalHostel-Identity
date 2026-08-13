# Personal Hostelería Server

Servidor de **identidad** de la familia Personal (Comander, Bar, Kitchen, TPV).  
No es el nodo de sala: eso es Personal Bar.

Mapa de intenciones para agentes: [`AGENTS.md`](AGENTS.md).

## Levantar en local (Docker)

```bash
cd PersonalHosteleriaServer
copy .env.example .env   # Windows; o: cp .env.example .env
docker compose up --build
```

- API: http://localhost:8080/health
- Meta: http://localhost:8080/v1/meta
- Postgres: `localhost:5432` (usuario `hosteleria`, base `identity`)

Parar: `Ctrl+C` o `docker compose down`. Datos de Postgres: volumen `pgdata`.

## Qué hay / qué no hay

Hay un proceso Docker que responde health. **No hay** registro de camareros, QR ni login: lo implementa el equipo de este repo.

Producción (VPS) no está en este scaffold.
