from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.db import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield


app = FastAPI(
    title="Personal Hostelería — Identity",
    version="0.0.0",
    description="Registro, QR permanente y login: ver AGENTS.md.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/v1/meta")
def meta() -> dict[str, str]:
    return {
        "service": "personal-hosteleria-identity",
        "role": "identity",
        "status": "schema",
    }
