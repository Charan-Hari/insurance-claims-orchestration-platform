from fastapi import FastAPI

from orchestrator.api.routes import router

app = FastAPI(title="Orchestrator Service", version="0.1.0")
app.include_router(router)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readiness", include_in_schema=False)
async def readiness() -> dict[str, str]:
    return {"status": "ready"}
