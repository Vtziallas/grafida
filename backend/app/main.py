from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.cases import router as cases_router
from app.api.clients import router as clients_router
from app.api.documents import router as documents_router
from app.api.style import router as style_router
from app.api.uploads import router as uploads_router
from app.auth.router import router as auth_router
from app.config import settings

app = FastAPI(title="Grafida API")
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


@app.get("/api/health")
def health():
    return {"status": "ok"}
