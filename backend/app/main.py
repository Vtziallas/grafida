import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.cases import router as cases_router
from app.api.clients import router as clients_router
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.style import router as style_router
from app.api.uploads import router as uploads_router
from app.auth.router import router as auth_router
from app.config import settings
from app.notify import alerts_configured, run_once


async def _alert_loop():
    while True:
        try:
            await asyncio.to_thread(run_once)
        except Exception:  # noqa: BLE001 — alerting must never crash the app
            pass
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_alert_loop()) if alerts_configured() else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Grafida API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=[settings.cors_origin],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(cases_router)
app.include_router(uploads_router)
app.include_router(style_router)
app.include_router(documents_router)
app.include_router(search_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
