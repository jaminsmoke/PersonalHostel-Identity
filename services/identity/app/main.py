from fastapi import FastAPI

app = FastAPI(
    title="Personal Hostelería — Identity",
    version="0.0.0",
    description="Scaffold. Registro, QR permanente y login: ver AGENTS.md.",
)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/v1/meta")
def meta() -> dict[str, str]:
    return {
        "service": "personal-hosteleria-identity",
        "role": "identity",
        "status": "scaffold",
    }
