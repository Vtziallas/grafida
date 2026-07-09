# Grafida MVP Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One end-to-end flow for a solo Greek lawyer: login → client → case → style samples → facts/evidence → AI extraction review → in-style draft → checklist → attested approval → DOCX export → search.

**Architecture:** Monorepo. Next.js 15 (TS/Tailwind) frontend talks to a FastAPI (Python 3.12, Docker) backend over cookie-JWT REST. Postgres+pgvector stores everything incl. embeddings and a Greek FTS index. AI is provider-agnostic: OllamaProvider (self-hosted, `host.docker.internal:11434`) for real runs, MockProvider for all tests. Agents are a sequential, logged pipeline — not autonomous.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, psycopg3, pgvector, PyJWT, bcrypt, python-docx, pypdf, rapidfuzz, httpx, pytest · Next.js 15 App Router, TypeScript, Tailwind · Docker Compose, pgvector/pgvector:pg16.

## Global Constraints

- UI language: **Greek**. All user-facing strings in Greek.
- No external AI APIs anywhere. `AI_PROVIDER` ∈ {`ollama`, `mock`}. Default chat model `qwen2.5:7b`, embed model `bge-m3` (dim **1024**), both env-overridable (`AI_CHAT_MODEL`, `AI_EMBED_MODEL`).
- Every DB query for user data filters by `owner_user_id` server-side.
- Export endpoint returns **403 unless document status is `approved`**.
- Extraction never invents values: any field whose `source_quote` doesn't fuzzy-match (≥90) the source text is nulled and flagged.
- Style analysis runs **only on scrubbed text**; original sample text never enters style prompts.
- AuditLog written for: login, uploads, extraction confirm, draft generation, checklist override, approval, export.
- All backend tests run inside Docker: `docker compose run --rm backend pytest -q` (local Python is 3.9; container is 3.12).
- Commit after every task with the trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **Deviation from spec, accepted:** Alembic deferred; schema created via `Base.metadata.create_all` (`app/create_db.py`) until the first post-slice migration is needed.

---

### Task 1: Repo scaffold — docker-compose, env, db init

**Files:**
- Create: `docker-compose.yml`, `.env.example`, `.env` (copy), `.gitignore`, `db/init.sql`, `README.md`

**Interfaces:**
- Produces: services `db` (5432), `backend` (8000), `frontend` (3000); volume `uploads` at `/data/uploads`; Postgres creds `grafida/grafida`, DBs `grafida` (+ `grafida_test` created by tests); `vector` extension available in all DBs via template1.

- [ ] **Step 1: Write the files**

`docker-compose.yml`:
```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: grafida
      POSTGRES_PASSWORD: grafida
      POSTGRES_DB: grafida
    ports: ["5432:5432"]
    volumes:
      - dbdata:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
  backend:
    build: ./backend
    env_file: .env
    ports: ["8000:8000"]
    depends_on: [db]
    volumes:
      - ./backend:/app
      - uploads:/data/uploads
    extra_hosts:
      - "host.docker.internal:host-gateway"
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on: [backend]
volumes:
  dbdata:
  uploads:
```

`db/init.sql`:
```sql
\c template1
CREATE EXTENSION IF NOT EXISTS vector;
\c grafida
CREATE EXTENSION IF NOT EXISTS vector;
```

`.env.example` (copy to `.env`):
```
DATABASE_URL=postgresql+psycopg://grafida:grafida@db:5432/grafida
JWT_SECRET=change-me-to-a-long-random-string
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
AI_CHAT_MODEL=qwen2.5:7b
AI_EMBED_MODEL=bge-m3
SEED_EMAIL=vtziallas02@gmail.com
SEED_PASSWORD=grafida123
CORS_ORIGIN=http://localhost:3000
STORAGE_DIR=/data/uploads
```

`.gitignore`:
```
.env
node_modules/
.next/
__pycache__/
*.pyc
.pytest_cache/
```

`README.md`: title "Grafida — AI βοηθός για Έλληνες δικηγόρους (MVP slice)", prerequisites (Docker Desktop, Ollama on Windows host with `ollama pull qwen2.5:7b` and `ollama pull bge-m3`), run: `docker compose up --build`, login with SEED_EMAIL/SEED_PASSWORD, tests: `docker compose run --rm backend pytest -q`.

- [ ] **Step 2: Verify compose config and db boots**

Run: `docker compose config --quiet && docker compose up -d db && docker compose exec db psql -U grafida -c "SELECT extname FROM pg_extension"`
Expected: no config errors; extension list includes `vector`.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore: scaffold compose, env, db init"
```

---

### Task 2: Backend skeleton — config, db, health, pytest harness

**Files:**
- Create: `backend/Dockerfile`, `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/main.py`, `backend/app/create_db.py`, `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces: `settings` (pydantic-settings, fields: `database_url, jwt_secret, jwt_expires_minutes=480, storage_dir, ai_provider, ollama_base_url, ai_chat_model, ai_embed_model, cors_origin, seed_email, seed_password`); `Base`, `engine`, `SessionLocal`, `get_db()` in `app/db.py`; FastAPI `app` in `app/main.py` with CORS (origin=`settings.cors_origin`, credentials=True); fixtures `client`, `auth_client` (registered+logged-in TestClient), session-scoped schema create, per-test TRUNCATE.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_health.py`:
```python
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: Write skeleton files**

`backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[test]" || true
COPY . .
RUN pip install --no-cache-dir -e ".[test]"
CMD ["sh", "-c", "python -m app.create_db && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
```

`backend/pyproject.toml`:
```toml
[project]
name = "grafida-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115", "uvicorn[standard]>=0.30", "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2", "pgvector>=0.3", "pydantic-settings>=2.4",
  "bcrypt>=4.2", "pyjwt>=2.9", "python-multipart>=0.0.9",
  "python-docx>=1.1", "pypdf>=4.3", "httpx>=0.27", "rapidfuzz>=3.9",
]
[project.optional-dependencies]
test = ["pytest>=8.3"]
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
[tool.setuptools.packages.find]
include = ["app*"]
```

`backend/app/config.py`:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://grafida:grafida@db:5432/grafida"
    jwt_secret: str = "dev-secret"
    jwt_expires_minutes: int = 480
    storage_dir: str = "/data/uploads"
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ai_chat_model: str = "qwen2.5:7b"
    ai_embed_model: str = "bge-m3"
    cors_origin: str = "http://localhost:3000"
    seed_email: str = "owner@example.com"
    seed_password: str = "grafida123"

settings = Settings()
```

`backend/app/db.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(title="Grafida API")
app.add_middleware(
    CORSMiddleware, allow_origins=[settings.cors_origin],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}
```

`backend/app/create_db.py`:
```python
from app.db import Base, engine
import app.models  # noqa: F401  (register tables; module exists from Task 3)

if __name__ == "__main__" or True:
    Base.metadata.create_all(engine)
```
(Until Task 3 exists, create `backend/app/models.py` as an empty file with just `# populated in Task 3`.)

`backend/tests/conftest.py`:
```python
import os
os.environ["AI_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = "postgresql+psycopg://grafida:grafida@db:5432/grafida_test"
os.environ["STORAGE_DIR"] = "/tmp/grafida_test_uploads"
import pytest
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient

@pytest.fixture(scope="session", autouse=True)
def _schema():
    admin = create_engine(
        "postgresql+psycopg://grafida:grafida@db:5432/postgres",
        isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        if not c.execute(text(
            "SELECT 1 FROM pg_database WHERE datname='grafida_test'")).scalar():
            c.execute(text("CREATE DATABASE grafida_test"))
    from app.db import Base, engine
    import app.models  # noqa: F401
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield

@pytest.fixture(autouse=True)
def _clean(_schema):
    yield
    from app.db import Base, engine
    from sqlalchemy import text as _t
    with engine.begin() as c:
        for t in reversed(Base.metadata.sorted_tables):
            c.execute(_t(f'TRUNCATE "{t.name}" RESTART IDENTITY CASCADE'))

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)

@pytest.fixture
def auth_client(client):
    client.post("/api/auth/register",
                json={"email": "t@t.gr", "password": "secret123", "full_name": "Test"})
    client.post("/api/auth/login",
                json={"email": "t@t.gr", "password": "secret123"})
    return client
```

- [ ] **Step 3: Run test to verify it passes**

Run: `docker compose build backend && docker compose run --rm backend pytest tests/test_health.py -q`
Expected: `1 passed` (the `auth_client` fixture is unused so its missing endpoints don't fail yet).

- [ ] **Step 4: Commit**

```bash
git add backend && git commit -m "feat: backend skeleton with config, db, health, test harness"
```

---

### Task 3: Data model + audit helper

**Files:**
- Create: `backend/app/ai/__init__.py`, `backend/app/ai/base.py` (only `EMBED_DIM` + protocol for now), `backend/app/models.py` (replace stub), `backend/app/audit.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: all entities below importable from `app.models`; `EMBED_DIM = 1024` from `app.ai.base`; `AIProvider` Protocol with `generate(*, system: str, user: str, json_mode: bool = False) -> str` and `embed(texts: list[str]) -> list[list[float]]`; `audit(db, user_id, action, entity_type, entity_id, detail=None)` from `app.audit` (commits nothing; caller commits).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_models.py`:
```python
from app.db import SessionLocal
from app import models as m
from app.audit import audit

def test_entities_roundtrip():
    db = SessionLocal()
    u = m.User(email="a@a.gr", password_hash="x", full_name="A")
    db.add(u); db.commit()
    c = m.Client(owner_user_id=u.id, name="Πελάτης ΑΕ", afm="123456789")
    db.add(c); db.commit()
    case = m.Case(owner_user_id=u.id, client_id=c.id, title="Ανακοπή Χ", category="civil")
    db.add(case); db.commit()
    audit(db, u.id, "case.create", "case", case.id)
    db.commit()
    assert db.query(m.AuditLog).count() == 1
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm backend pytest tests/test_models.py -q`
Expected: FAIL (models missing).

- [ ] **Step 3: Implement**

`backend/app/ai/base.py`:
```python
from typing import Protocol

EMBED_DIM = 1024

class AIProvider(Protocol):
    def generate(self, *, system: str, user: str, json_mode: bool = False) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

`backend/app/models.py`:
```python
from datetime import datetime, date
from sqlalchemy import (String, Text, Integer, Float, Boolean, DateTime, Date,
                        ForeignKey, JSON, Computed, Index)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector
from app.db import Base
from app.ai.base import EMBED_DIM


class TS:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Owned:
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)


class User(Base, TS):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    firm_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Client(Base, TS, Owned):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    afm: Mapped[str | None] = mapped_column(String(9), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class Case(Base, TS, Owned):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    title: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(100), default="civil")
    court_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="open")
    next_action: Mapped[str] = mapped_column(String(500), default="")
    ref_numbers: Mapped[str] = mapped_column(String(255), default="")
    facts_text: Mapped[str] = mapped_column(Text, default="")


class Party(Base, TS, Owned):
    __tablename__ = "parties"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(100), default="")
    source_quote: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    confirmed_by_lawyer: Mapped[bool] = mapped_column(Boolean, default=False)


class CaseFact(Base, TS, Owned):
    __tablename__ = "case_facts"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # date|amount|claim|other
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    source_quote: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    confirmed_by_lawyer: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_group: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Deadline(Base, TS, Owned):
    __tablename__ = "deadlines"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    due_date: Mapped[date] = mapped_column(Date)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DocumentType(Base, TS):
    __tablename__ = "document_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    name_gr: Mapped[str] = mapped_column(String(255), unique=True)
    category: Mapped[str] = mapped_column(String(100), default="civil")
    checklist_template: Mapped[list] = mapped_column(JSON, default=list)


class Document(Base, TS, Owned):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("document_types.id"))
    title: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|approved|exported
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DocumentVersion(Base, TS, Owned):
    __tablename__ = "document_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(10), default="ai")  # ai|lawyer
    content_hash: Mapped[str] = mapped_column(String(64), default="")


class Evidence(Base, TS, Owned):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    exhibit_number: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(500), default="")
    file_path: Mapped[str] = mapped_column(String(1000))
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    ocr_pending: Mapped[bool] = mapped_column(Boolean, default=False)


class StyleSample(Base, TS, Owned):
    __tablename__ = "style_samples"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_type_id: Mapped[int] = mapped_column(ForeignKey("document_types.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(1000))
    original_text: Mapped[str] = mapped_column(Text, default="")
    scrubbed_text: Mapped[str] = mapped_column(Text, default="")
    embedding = mapped_column(Vector(EMBED_DIM), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok|ocr_pending|rejected


class StyleProfile(Base, TS, Owned):
    __tablename__ = "style_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_type_id: Mapped[int] = mapped_column(ForeignKey("document_types.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    spec: Mapped[dict] = mapped_column(JSON, default=dict)
    built_from_sample_ids: Mapped[list] = mapped_column(JSON, default=list)
    approved_by_lawyer: Mapped[bool] = mapped_column(Boolean, default=False)


class AIDraft(Base, TS, Owned):
    __tablename__ = "ai_drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    document_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    style_profile_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inputs_manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    uncertainty_report: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|ok|failed
    error: Mapped[str] = mapped_column(Text, default="")


class ChecklistItem(Base, TS, Owned):
    __tablename__ = "checklist_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    source_agent: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(10))  # red|yellow
    text: Mapped[str] = mapped_column(Text)
    anchor_quote: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|resolved|overridden
    override_note: Mapped[str] = mapped_column(Text, default="")
    resolved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AuditLog(Base, TS):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50), default="")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class SearchIndex(Base, TS, Owned):
    __tablename__ = "search_index"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # document|evidence|sample
    ref_id: Mapped[int] = mapped_column(Integer)
    case_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('greek', text)", persisted=True))
    embedding = mapped_column(Vector(EMBED_DIM), nullable=True)
    __table_args__ = (
        Index("ix_search_tsv", "tsv", postgresql_using="gin"),
        Index("ix_search_kind_ref", "kind", "ref_id", unique=True),
    )
```

`backend/app/audit.py`:
```python
from app.models import AuditLog

def audit(db, user_id: int, action: str, entity_type: str = "",
          entity_id: int | None = None, detail: dict | None = None):
    db.add(AuditLog(user_id=user_id, action=action, entity_type=entity_type,
                    entity_id=entity_id, detail=detail or {}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose run --rm backend pytest tests/test_models.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat: full slice data model, audit helper, AI provider protocol"
```

---

### Task 4: Auth — register/login/logout/me + seed script

**Files:**
- Create: `backend/app/auth/__init__.py`, `backend/app/auth/security.py`, `backend/app/auth/deps.py`, `backend/app/auth/router.py`, `backend/app/seed.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Produces: `hash_password(p)->str`, `verify_password(p,h)->bool`, `create_token(user_id)->str`, `decode_token(t)->int` (`app.auth.security`); `get_current_user` dependency and `COOKIE="grafida_token"` (`app.auth.deps`); endpoints `POST /api/auth/register {email,password,full_name}`, `POST /api/auth/login` (sets httpOnly cookie), `POST /api/auth/logout`, `GET /api/auth/me -> {id,email,full_name}`; `python -m app.seed` idempotently creates settings.seed_email user + 2 DocumentTypes.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_auth.py`:
```python
def test_register_login_me(client):
    r = client.post("/api/auth/register",
                    json={"email": "a@a.gr", "password": "secret123", "full_name": "Α"})
    assert r.status_code == 200
    r = client.post("/api/auth/login", json={"email": "a@a.gr", "password": "secret123"})
    assert r.status_code == 200
    assert "grafida_token" in r.cookies
    r = client.get("/api/auth/me")
    assert r.json()["email"] == "a@a.gr"

def test_bad_password(client):
    client.post("/api/auth/register",
                json={"email": "b@b.gr", "password": "secret123", "full_name": "Β"})
    r = client.post("/api/auth/login", json={"email": "b@b.gr", "password": "wrong"})
    assert r.status_code == 401

def test_me_unauthenticated(client):
    assert client.get("/api/auth/me").status_code == 401
```

- [ ] **Step 2: Run to verify it fails** — `docker compose run --rm backend pytest tests/test_auth.py -q` → FAIL 404.

- [ ] **Step 3: Implement**

`backend/app/auth/security.py`:
```python
import time, bcrypt, jwt
from app.config import settings

def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except ValueError:
        return False

def create_token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": int(time.time()) + settings.jwt_expires_minutes * 60},
        settings.jwt_secret, algorithm="HS256")

def decode_token(t: str) -> int:
    return int(jwt.decode(t, settings.jwt_secret, algorithms=["HS256"])["sub"])
```

`backend/app/auth/deps.py`:
```python
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.auth.security import decode_token

COOKIE = "grafida_token"

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    tok = request.cookies.get(COOKIE)
    if not tok:
        raise HTTPException(401, "Απαιτείται σύνδεση")
    try:
        uid = decode_token(tok)
    except Exception:
        raise HTTPException(401, "Μη έγκυρη συνεδρία")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "Μη έγκυρη συνεδρία")
    return user
```

`backend/app/auth/router.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.audit import audit
from app.auth.security import hash_password, verify_password, create_token
from app.auth.deps import COOKIE, get_current_user

router = APIRouter(prefix="/api/auth")

class Creds(BaseModel):
    email: str
    password: str
    full_name: str = ""

@router.post("/register")
def register(body: Creds, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(400, "Το email χρησιμοποιείται ήδη")
    u = User(email=body.email, password_hash=hash_password(body.password),
             full_name=body.full_name)
    db.add(u); db.commit()
    return {"id": u.id}

@router.post("/login")
def login(body: Creds, response: Response, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=body.email).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Λάθος στοιχεία")
    response.set_cookie(COOKIE, create_token(u.id), httponly=True,
                        samesite="lax", max_age=8 * 3600)
    audit(db, u.id, "auth.login"); db.commit()
    return {"ok": True}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}

@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "full_name": user.full_name}
```

`backend/app/seed.py`:
```python
from app.db import SessionLocal
from app.models import User, DocumentType
from app.auth.security import hash_password
from app.config import settings

ANAKOPI_CHECKLIST = [
    "Ελέγξτε την προθεσμία άσκησης της ανακοπής (προς επαλήθευση με ΚΠολΔ).",
    "Ελέγξτε την αρμοδιότητα του δικαστηρίου.",
    "Ελέγξτε ότι όλα τα σχετικά αναφέρονται και επισυνάπτονται.",
    "Ελέγξτε γραμμάτιο προείσπραξης και λοιπά παράβολα (προς επαλήθευση).",
]

def run():
    db = SessionLocal()
    if not db.query(User).filter_by(email=settings.seed_email).first():
        db.add(User(email=settings.seed_email,
                    password_hash=hash_password(settings.seed_password),
                    full_name="Δικηγόρος"))
    for name, checklist in [
        ("Ανακοπή κατά διαταγής πληρωμής", ANAKOPI_CHECKLIST),
        ("Γενικό δικόγραφο", []),
    ]:
        if not db.query(DocumentType).filter_by(name_gr=name).first():
            db.add(DocumentType(name_gr=name, checklist_template=checklist))
    db.commit(); db.close()

if __name__ == "__main__":
    run()
```

In `backend/app/main.py` add:
```python
from app.auth.router import router as auth_router
app.include_router(auth_router)
```

- [ ] **Step 4: Run** — `docker compose run --rm backend pytest tests/test_auth.py -q` → 3 passed.
- [ ] **Step 5: Commit** — `git add backend && git commit -m "feat: cookie-JWT auth and seed script"`

---

### Task 5: Clients, cases, parties, facts, deadlines API

**Files:**
- Create: `backend/app/api/__init__.py`, `backend/app/api/clients.py`, `backend/app/api/cases.py`
- Modify: `backend/app/main.py` (include routers)
- Test: `backend/tests/test_cases.py`

**Interfaces:**
- Produces endpoints (all require auth, all filter `owner_user_id == user.id`):
  - `POST/GET /api/clients`, `GET /api/clients/{id}` (detail includes its cases)
  - `POST/GET /api/cases`, `GET /api/cases/{id}` (detail: case fields + client name + parties + facts + deadlines + documents (id,title,status,type name) + evidence (id, exhibit_number, description, ocr_pending) + doc types list)
  - `PATCH /api/cases/{id}` (any of: title, court_name, status, next_action, ref_numbers, facts_text)
  - `POST /api/cases/{id}/deadlines {title, due_date}`
  - `PATCH /api/parties/{id} {name?, role?, confirmed_by_lawyer?}`; `PATCH /api/facts/{id} {value?, description?, confirmed_by_lawyer?}` — confirming writes audit `extract.confirm`.
- Consumes: `get_current_user`, `audit`, models.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_cases.py`:
```python
def _mk_case(ac):
    cid = ac.post("/api/clients", json={"name": "Πελάτης"}).json()["id"]
    return ac.post("/api/cases", json={"client_id": cid, "title": "Υπόθεση 1",
                                       "category": "civil"}).json()["id"]

def test_case_crud_and_isolation(auth_client, client):
    case_id = _mk_case(auth_client)
    r = auth_client.get(f"/api/cases/{case_id}")
    assert r.status_code == 200 and r.json()["title"] == "Υπόθεση 1"
    auth_client.patch(f"/api/cases/{case_id}", json={"facts_text": "γεγονότα"})
    assert auth_client.get(f"/api/cases/{case_id}").json()["facts_text"] == "γεγονότα"
    # second user cannot see it
    client.post("/api/auth/register", json={"email": "x@x.gr", "password": "secret123"})
    client.post("/api/auth/login", json={"email": "x@x.gr", "password": "secret123"})
    assert client.get(f"/api/cases/{case_id}").status_code == 404

def test_deadline_and_fact_confirm(auth_client):
    case_id = _mk_case(auth_client)
    r = auth_client.post(f"/api/cases/{case_id}/deadlines",
                         json={"title": "Κατάθεση", "due_date": "2026-09-01"})
    assert r.status_code == 200
    d = auth_client.get(f"/api/cases/{case_id}").json()
    assert d["deadlines"][0]["title"] == "Κατάθεση"
```

- [ ] **Step 2: Run to verify it fails** — expected 404s.

- [ ] **Step 3: Implement**

`backend/app/api/clients.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Client, Case, User
from app.auth.deps import get_current_user

router = APIRouter(prefix="/api/clients")

class ClientIn(BaseModel):
    name: str
    afm: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str = ""

@router.post("")
def create(body: ClientIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    c = Client(owner_user_id=user.id, **body.model_dump())
    db.add(c); db.commit()
    return {"id": c.id}

@router.get("")
def list_(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Client).filter_by(owner_user_id=user.id).order_by(Client.name).all()
    return [{"id": c.id, "name": c.name, "afm": c.afm, "phone": c.phone} for c in rows]

@router.get("/{client_id}")
def detail(client_id: int, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    c = db.query(Client).filter_by(id=client_id, owner_user_id=user.id).first()
    if not c:
        raise HTTPException(404)
    cases = db.query(Case).filter_by(client_id=c.id, owner_user_id=user.id).all()
    return {"id": c.id, "name": c.name, "afm": c.afm, "email": c.email,
            "phone": c.phone, "notes": c.notes,
            "cases": [{"id": k.id, "title": k.title, "status": k.status} for k in cases]}
```

`backend/app/api/cases.py`:
```python
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import (Case, Client, Party, CaseFact, Deadline, Document,
                        DocumentType, Evidence, User)
from app.auth.deps import get_current_user
from app.audit import audit

router = APIRouter(prefix="/api")

def get_case(db: Session, user: User, case_id: int) -> Case:
    c = db.query(Case).filter_by(id=case_id, owner_user_id=user.id).first()
    if not c:
        raise HTTPException(404, "Η υπόθεση δεν βρέθηκε")
    return c

class CaseIn(BaseModel):
    client_id: int
    title: str
    category: str = "civil"
    court_name: str = ""

class CasePatch(BaseModel):
    title: str | None = None
    court_name: str | None = None
    status: str | None = None
    next_action: str | None = None
    ref_numbers: str | None = None
    facts_text: str | None = None

class DeadlineIn(BaseModel):
    title: str
    due_date: date

class PartyPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    confirmed_by_lawyer: bool | None = None

class FactPatch(BaseModel):
    value: str | None = None
    description: str | None = None
    confirmed_by_lawyer: bool | None = None

@router.post("/cases")
def create(body: CaseIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    if not db.query(Client).filter_by(id=body.client_id, owner_user_id=user.id).first():
        raise HTTPException(404, "Ο πελάτης δεν βρέθηκε")
    c = Case(owner_user_id=user.id, **body.model_dump())
    db.add(c); db.flush()
    audit(db, user.id, "case.create", "case", c.id); db.commit()
    return {"id": c.id}

@router.get("/cases")
def list_(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Case).filter_by(owner_user_id=user.id).order_by(Case.id.desc()).all()
    return [{"id": c.id, "title": c.title, "status": c.status,
             "court_name": c.court_name, "next_action": c.next_action} for c in rows]

@router.get("/cases/{case_id}")
def detail(case_id: int, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    c = get_case(db, user, case_id)
    client = db.get(Client, c.client_id)
    types = db.query(DocumentType).all()
    docs = db.query(Document).filter_by(case_id=c.id).all()
    tmap = {t.id: t.name_gr for t in types}
    return {
        "id": c.id, "title": c.title, "category": c.category, "status": c.status,
        "court_name": c.court_name, "next_action": c.next_action,
        "ref_numbers": c.ref_numbers, "facts_text": c.facts_text,
        "client": {"id": client.id, "name": client.name},
        "parties": [{"id": p.id, "name": p.name, "role": p.role,
                     "source_quote": p.source_quote, "confidence": p.confidence,
                     "confirmed": p.confirmed_by_lawyer}
                    for p in db.query(Party).filter_by(case_id=c.id)],
        "facts": [{"id": f.id, "kind": f.kind, "value": f.value,
                   "description": f.description, "source_quote": f.source_quote,
                   "confidence": f.confidence, "confirmed": f.confirmed_by_lawyer,
                   "conflict_group": f.conflict_group}
                  for f in db.query(CaseFact).filter_by(case_id=c.id)],
        "deadlines": [{"id": d.id, "title": d.title, "due_date": str(d.due_date),
                       "completed": d.completed_at is not None}
                      for d in db.query(Deadline).filter_by(case_id=c.id)
                                 .order_by(Deadline.due_date)],
        "documents": [{"id": d.id, "title": d.title, "status": d.status,
                       "type": tmap.get(d.type_id, "")} for d in docs],
        "evidence": [{"id": e.id, "exhibit_number": e.exhibit_number,
                      "description": e.description, "ocr_pending": e.ocr_pending}
                     for e in db.query(Evidence).filter_by(case_id=c.id)
                                .order_by(Evidence.exhibit_number)],
        "document_types": [{"id": t.id, "name": t.name_gr} for t in types],
    }

@router.patch("/cases/{case_id}")
def patch(case_id: int, body: CasePatch, user: User = Depends(get_current_user),
          db: Session = Depends(get_db)):
    c = get_case(db, user, case_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    return {"ok": True}

@router.post("/cases/{case_id}/deadlines")
def add_deadline(case_id: int, body: DeadlineIn,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_case(db, user, case_id)
    d = Deadline(owner_user_id=user.id, case_id=case_id, **body.model_dump())
    db.add(d); db.commit()
    return {"id": d.id}

@router.patch("/parties/{party_id}")
def patch_party(party_id: int, body: PartyPatch,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(Party).filter_by(id=party_id, owner_user_id=user.id).first()
    if not p:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    if body.confirmed_by_lawyer:
        audit(db, user.id, "extract.confirm", "party", p.id)
    db.commit()
    return {"ok": True}

@router.patch("/facts/{fact_id}")
def patch_fact(fact_id: int, body: FactPatch,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = db.query(CaseFact).filter_by(id=fact_id, owner_user_id=user.id).first()
    if not f:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(f, k, v)
    if body.confirmed_by_lawyer:
        audit(db, user.id, "extract.confirm", "fact", f.id)
    db.commit()
    return {"ok": True}
```

In `main.py` add both routers (`from app.api.clients import router as clients_router`, etc.).

- [ ] **Step 4: Run** — `docker compose run --rm backend pytest tests/test_cases.py -q` → 2 passed.
- [ ] **Step 5: Commit** — `git commit -am "feat: clients/cases/parties/facts/deadlines API with per-user isolation"`

---

### Task 6: File storage, text extraction, evidence & style-sample uploads

**Files:**
- Create: `backend/app/files/__init__.py`, `backend/app/files/storage.py`, `backend/app/files/extract.py`, `backend/app/api/uploads.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_uploads.py`

**Interfaces:**
- Produces: `save_upload(data: bytes, filename: str, subdir: str) -> str` (path under `settings.storage_dir`, uuid-prefixed); `extract_text(path: str) -> tuple[str, bool]` — returns `(text, ocr_pending)`; `.docx` via python-docx, `.pdf` via pypdf (if total text < 50 chars → `("", True)`), `.txt` read as utf-8; other extensions → `("", True)`.
- Endpoints: `POST /api/cases/{id}/evidence` (multipart `file`, form `description`) → auto exhibit_number = max+1, extracts text, audits `upload.evidence`; `POST /api/style/samples` (multipart `file`, form `document_type_id`) → extracts, scrub deferred (Task 8 wires it; store `scrubbed_text=""` for now), status `ok`/`ocr_pending`, audits `upload.sample`; `GET /api/style/samples?document_type_id=`; `DELETE /api/style/samples/{id}`.
- Max upload 15 MB (413 above); allowed extensions: pdf, docx, txt.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_uploads.py`:
```python
import io
from docx import Document as Docx

def _docx_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    d = Docx(); d.add_paragraph(text); d.save(buf)
    return buf.getvalue()

def _case(ac):
    cid = ac.post("/api/clients", json={"name": "Π"}).json()["id"]
    return ac.post("/api/cases", json={"client_id": cid, "title": "Υ"}).json()["id"]

def test_evidence_upload_extracts_text(auth_client):
    case_id = _case(auth_client)
    r = auth_client.post(f"/api/cases/{case_id}/evidence",
        files={"file": ("a.docx", _docx_bytes("Μίσθωμα 1.500,00 ευρώ"),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"description": "Μισθωτήριο"})
    assert r.status_code == 200
    ev = auth_client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert ev[0]["exhibit_number"] == 1 and ev[0]["ocr_pending"] is False

def test_style_sample_upload(auth_client):
    tid = 1  # seeded in this test directly
    from app.db import SessionLocal
    from app.models import DocumentType
    db = SessionLocal(); db.add(DocumentType(name_gr="Ανακοπή", checklist_template=[]))
    db.commit(); tid = db.query(DocumentType).first().id; db.close()
    r = auth_client.post("/api/style/samples",
        files={"file": ("s.docx", _docx_bytes("ΕΝΩΠΙΟΝ ΤΟΥ ΔΙΚΑΣΤΗΡΙΟΥ..."), "application/x")},
        data={"document_type_id": str(tid)})
    assert r.status_code == 200
    samples = auth_client.get(f"/api/style/samples?document_type_id={tid}").json()
    assert len(samples) == 1 and samples[0]["status"] == "ok"

def test_bad_extension_rejected(auth_client):
    case_id = _case(auth_client)
    r = auth_client.post(f"/api/cases/{case_id}/evidence",
        files={"file": ("x.exe", b"MZ", "application/x")}, data={"description": ""})
    assert r.status_code == 400
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement**

`backend/app/files/storage.py`:
```python
import os, uuid
from app.config import settings

def save_upload(data: bytes, filename: str, subdir: str) -> str:
    safe = filename.replace("/", "_").replace("\\", "_")
    d = os.path.join(settings.storage_dir, subdir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{uuid.uuid4().hex}_{safe}")
    with open(path, "wb") as f:
        f.write(data)
    return path
```

`backend/app/files/extract.py`:
```python
from docx import Document as Docx
from pypdf import PdfReader

def extract_text(path: str) -> tuple[str, bool]:
    low = path.lower()
    if low.endswith(".docx"):
        return "\n".join(p.text for p in Docx(path).paragraphs), False
    if low.endswith(".txt"):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(), False
    if low.endswith(".pdf"):
        try:
            text = "\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)
        except Exception:
            return "", True
        return (text, False) if len(text.strip()) >= 50 else ("", True)
    return "", True
```

`backend/app/api/uploads.py`:
```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Evidence, StyleSample, DocumentType, User
from app.auth.deps import get_current_user
from app.api.cases import get_case
from app.audit import audit
from app.files.storage import save_upload
from app.files.extract import extract_text

router = APIRouter(prefix="/api")
ALLOWED = (".pdf", ".docx", ".txt")
MAX_BYTES = 15 * 1024 * 1024

async def _read(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(ALLOWED):
        raise HTTPException(400, "Επιτρέπονται μόνο αρχεία PDF, DOCX, TXT")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Το αρχείο ξεπερνά τα 15MB")
    return data

@router.post("/cases/{case_id}/evidence")
async def upload_evidence(case_id: int, file: UploadFile = File(...),
                          description: str = Form(""),
                          user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    get_case(db, user, case_id)
    data = await _read(file)
    path = save_upload(data, file.filename, f"u{user.id}/evidence")
    text, pending = extract_text(path)
    n = (db.query(Evidence).filter_by(case_id=case_id).count()) + 1
    e = Evidence(owner_user_id=user.id, case_id=case_id, exhibit_number=n,
                 description=description or file.filename, file_path=path,
                 extracted_text=text, ocr_pending=pending)
    db.add(e); db.flush()
    audit(db, user.id, "upload.evidence", "evidence", e.id); db.commit()
    return {"id": e.id, "exhibit_number": n, "ocr_pending": pending}

@router.post("/style/samples")
async def upload_sample(file: UploadFile = File(...),
                        document_type_id: int = Form(...),
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    if not db.get(DocumentType, document_type_id):
        raise HTTPException(404, "Άγνωστος τύπος εγγράφου")
    data = await _read(file)
    path = save_upload(data, file.filename, f"u{user.id}/samples")
    text, pending = extract_text(path)
    s = StyleSample(owner_user_id=user.id, document_type_id=document_type_id,
                    file_path=path, original_text=text, scrubbed_text="",
                    status="ocr_pending" if pending else "ok")
    db.add(s); db.flush()
    audit(db, user.id, "upload.sample", "style_sample", s.id); db.commit()
    return {"id": s.id, "status": s.status}

@router.get("/style/samples")
def list_samples(document_type_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    rows = db.query(StyleSample).filter_by(
        owner_user_id=user.id, document_type_id=document_type_id).all()
    return [{"id": s.id, "status": s.status,
             "chars": len(s.original_text)} for s in rows]

@router.delete("/style/samples/{sample_id}")
def delete_sample(sample_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    s = db.query(StyleSample).filter_by(id=sample_id, owner_user_id=user.id).first()
    if not s:
        raise HTTPException(404)
    db.delete(s); db.commit()
    return {"ok": True}
```

Include router in `main.py`.

- [ ] **Step 4: Run** — 3 passed. **Step 5: Commit** — `git commit -am "feat: uploads with text extraction and exhibit numbering"`

---

### Task 7: AI providers — Mock + Ollama + prompt loader

**Files:**
- Create: `backend/app/ai/mock.py`, `backend/app/ai/ollama.py`, `backend/app/ai/factory.py`, `backend/app/agents/__init__.py`, `backend/app/agents/prompts.py`, `backend/app/agents/prompts/intake_extract.md`, `backend/app/agents/prompts/style_analyze.md`, `backend/app/agents/prompts/draft.md`
- Test: `backend/tests/test_ai_provider.py`

**Interfaces:**
- Produces: `get_provider() -> AIProvider` (`app.ai.factory`, reads `settings.ai_provider`); `MockProvider` — `generate` keys off the first line of `system` (`AGENT: <name>`) and returns canned JSON/text from `MOCK_RESPONSES[name]`; `embed` returns deterministic 1024-dim vectors (seeded md5); `OllamaProvider` — POST `{base}/api/chat` (`stream:false`, `format:"json"` when `json_mode`), POST `{base}/api/embed`; 2 retries, 300 s timeout, raises `AIError(msg_greek)`; `load_prompt(name) -> tuple[str, int]` reading `app/agents/prompts/{name}.md`, version from first line `<!-- version: N -->`.
- Prompt files begin with `<!-- version: 1 -->` then `AGENT: <name>` then the Greek prompt body (bodies given in Tasks 9–11 where each agent is built; create the three files now with version line + AGENT line + `TODO body in Task N` placeholder text is **not allowed** — instead put the full bodies in now, copied from Tasks 9, 10, 11 below).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_ai_provider.py`:
```python
import json
from app.ai.factory import get_provider
from app.agents.prompts import load_prompt

def test_mock_generate_is_keyed_by_agent():
    p = get_provider()  # AI_PROVIDER=mock in conftest
    out = p.generate(system="AGENT: intake_extract\n...", user="κείμενο")
    data = json.loads(out)
    assert "parties" in data

def test_mock_embed_deterministic():
    p = get_provider()
    a, b = p.embed(["αγωγή"]), p.embed(["αγωγή"])
    assert a == b and len(a[0]) == 1024

def test_load_prompt_versioned():
    text, version = load_prompt("intake_extract")
    assert version == 1 and "AGENT: intake_extract" in text
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement**

`backend/app/agents/prompts.py`:
```python
import os, re

DIR = os.path.join(os.path.dirname(__file__), "prompts")

def load_prompt(name: str) -> tuple[str, int]:
    with open(os.path.join(DIR, f"{name}.md"), encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"<!-- version: (\d+) -->", text)
    return text, int(m.group(1)) if m else 0
```

`backend/app/ai/mock.py`:
```python
import hashlib, json, re
from app.ai.base import EMBED_DIM

MOCK_RESPONSES: dict[str, str] = {
    "intake_extract": json.dumps({
        "parties": [{"name": "Ιωάννης Παπαδόπουλος", "role": "ανακόπτων",
                     "source_quote": "Ιωάννης Παπαδόπουλος", "confidence": 0.95}],
        "dates": [{"value": "2026-06-01", "description": "επίδοση διαταγής",
                   "source_quote": "1/6/2026", "confidence": 0.9}],
        "amounts": [{"value": "14500.00", "description": "απαίτηση",
                     "source_quote": "14.500,00", "confidence": 0.9}],
        "claims": [{"value": "ακύρωση διαταγής πληρωμής",
                    "description": "κύριο αίτημα",
                    "source_quote": "διαταγή πληρωμής", "confidence": 0.8}],
    }, ensure_ascii=False),
    "style_analyze": json.dumps({
        "structure": [{"section": "Ιστορικό", "order": 1, "share": 0.4},
                      {"section": "Λόγοι", "order": 2, "share": 0.4},
                      {"section": "Αίτημα", "order": 3, "share": 0.2}],
        "phrase_bank": {"openings": ["ΕΝΩΠΙΟΝ ΤΟΥ"], "transitions": ["Επειδή"],
                        "closers": ["ΓΙΑ ΤΟΥΣ ΛΟΓΟΥΣ ΑΥΤΟΥΣ"],
                        "favorite_expressions": ["όλως αβασίμως"]},
        "tone": {"formality": 5, "avg_sentence_length": 38},
        "formatting": {"numbering": "arabic", "headings": "caps"},
    }, ensure_ascii=False),
    "draft": ("ΕΝΩΠΙΟΝ ΤΟΥ ΔΙΚΑΣΤΗΡΙΟΥ\n\nΑΝΑΚΟΠΗ\n\nΤου Ιωάννη Παπαδόπουλου.\n\n"
              "Επειδή η προσβαλλόμενη διαταγή πληρωμής ποσού 14.500,00 ευρώ "
              "[πηγή: σχετικό 1] εκδόθηκε [ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ — δεν ανακτήθηκε πηγή] "
              "παρανόμως.\n\nΓΙΑ ΤΟΥΣ ΛΟΓΟΥΣ ΑΥΤΟΥΣ ζητώ την ακύρωσή της."),
}


class MockProvider:
    def generate(self, *, system: str, user: str, json_mode: bool = False) -> str:
        m = re.search(r"AGENT: (\w+)", system)
        key = m.group(1) if m else ""
        return MOCK_RESPONSES.get(key, "{}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            h = hashlib.md5(t.encode()).digest()
            out.append([(h[i % 16] + i) % 100 / 100.0 for i in range(EMBED_DIM)])
        return out
```

`backend/app/ai/ollama.py`:
```python
import httpx
from app.config import settings
from app.ai.base import EMBED_DIM

class AIError(Exception):
    pass

class OllamaProvider:
    def __init__(self):
        self.base = settings.ollama_base_url.rstrip("/")

    def _post(self, path: str, payload: dict) -> dict:
        last = None
        for _ in range(3):
            try:
                r = httpx.post(f"{self.base}{path}", json=payload, timeout=300)
                r.raise_for_status()
                return r.json()
            except Exception as e:  # noqa: BLE001
                last = e
        raise AIError(f"Αποτυχία επικοινωνίας με το τοπικό μοντέλο AI: {last}")

    def generate(self, *, system: str, user: str, json_mode: bool = False) -> str:
        payload = {"model": settings.ai_chat_model, "stream": False,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user}]}
        if json_mode:
            payload["format"] = "json"
        return self._post("/api/chat", payload)["message"]["content"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post("/api/embed",
                          {"model": settings.ai_embed_model, "input": texts})
        vecs = data["embeddings"]
        if vecs and len(vecs[0]) != EMBED_DIM:
            raise AIError(f"Λάθος διάσταση embeddings: {len(vecs[0])}")
        return vecs
```

`backend/app/ai/factory.py`:
```python
from app.config import settings
from app.ai.base import AIProvider
from app.ai.mock import MockProvider
from app.ai.ollama import OllamaProvider

def get_provider() -> AIProvider:
    return MockProvider() if settings.ai_provider == "mock" else OllamaProvider()
```

Prompt files — full bodies (Greek), each starting with its version comment and AGENT line. `intake_extract.md`:
```markdown
<!-- version: 1 -->
AGENT: intake_extract
Είσαι σύστημα εξαγωγής δεδομένων για ελληνικά νομικά έγγραφα. Διάβασε το κείμενο
(πιθανόν με σφάλματα OCR) και επίστρεψε ΜΟΝΟ έγκυρο JSON με κλειδιά:
parties[{name, role, source_quote, confidence}],
dates[{value(ISO 8601), description, source_quote, confidence}],
amounts[{value(αριθμός με τελεία δεκαδικών), description, source_quote, confidence}],
claims[{value, description, source_quote, confidence}].
Κανόνες: (1) Εξάγεις ΜΟΝΟ ό,τι αναγράφεται ρητά — ΠΟΤΕ δεν συμπεραίνεις τιμές.
(2) Κάθε στοιχείο περιέχει source_quote: ΑΚΡΙΒΕΣ απόσπασμα από το κείμενο.
(3) Αν κάτι είναι δυσανάγνωστο: value=null. (4) confidence: 0 έως 1.
```
`style_analyze.md`:
```markdown
<!-- version: 1 -->
AGENT: style_analyze
Ανάλυσε τα ανωνυμοποιημένα δείγματα εγγράφων του ίδιου δικηγόρου (ίδιος τύπος
εγγράφου) και επίστρεψε ΜΟΝΟ JSON: structure[{section, order, share}],
phrase_bank{openings[], transitions[], closers[], favorite_expressions[]},
tone{formality(1-5), avg_sentence_length}, formatting{numbering, headings}.
Κανόνες: (1) Μόνο μοτίβα που εμφανίζονται σε τουλάχιστον 2 δείγματα.
(2) ΑΠΑΓΟΡΕΥΕΤΑΙ να συμπεριλάβεις ονόματα, ποσά, ημερομηνίες ή πραγματικά
περιστατικά — μόνο υφολογικά και δομικά στοιχεία.
```
`draft.md`:
```markdown
<!-- version: 1 -->
AGENT: draft
Είσαι έμπειρος συντάκτης ελληνικών δικογράφων που εργάζεται ΥΠΟ ΤΟΝ ΕΛΕΓΧΟ
δικηγόρου. Σύνταξε πλήρες προσχέδιο του ζητούμενου τύπου εγγράφου στα ελληνικά.
ΠΗΓΕΣ (κλειστός κόσμος):
- CASE_FILE: μοναδική πηγή πραγματικών περιστατικών. Κάθε περιστατικό συνοδεύεται
  από δείκτη [πηγή: ...] όπου αναφέρεται το σχετικό ή το πεδίο του φακέλου.
- STYLE_PROFILE και EXEMPLARS: μόνο για δομή, ύφος, φρασεολογία — ΠΟΤΕ για γεγονότα.
ΑΠΟΛΥΤΟΙ ΚΑΝΟΝΕΣ: (1) Γεγονός εκτός CASE_FILE δεν υπάρχει. (2) Κάθε νομική
αναφορά (άρθρα, αποφάσεις) σημαίνεται [ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ — δεν ανακτήθηκε πηγή].
(3) Ελλείψεις → [ΚΕΝΟ: περιγραφή], όχι εφεύρεση. (4) Αριθμοί σχετικών μόνο από
το CASE_FILE. Επίστρεψε ΜΟΝΟ το κείμενο του εγγράφου.
```

- [ ] **Step 4: Run** — `docker compose run --rm backend pytest tests/test_ai_provider.py -q` → 3 passed.
- [ ] **Step 5: Commit** — `git commit -am "feat: AI provider layer (mock+ollama) and versioned Greek prompts"`

---

### Task 8: PII scrubber

**Files:**
- Create: `backend/app/agents/pii_scrub.py`
- Modify: `backend/app/api/uploads.py` (call scrub on sample upload)
- Test: `backend/tests/test_pii_scrub.py`

**Interfaces:**
- Produces: `scrub(text: str) -> tuple[str, list[dict]]` — returns scrubbed text + replacement list `[{"type","original"}]`. Replaces: 9-digit numbers → `⟨ΑΦΜ⟩`, 11-digit → `⟨ΑΜΚΑ⟩`, amounts (`1.500,00` w/ optional `€`/`ευρώ`) → `⟨ΠΟΣΟ⟩`, dates (`dd/mm/yyyy`, `dd.mm.yyyy`, `dd-mm-yyyy`) → `⟨ΗΜΕΡΟΜΗΝΙΑ⟩`, case numbers (`123/2026`) → `⟨ΑΡΙΘΜΟΣ⟩`, sequences of ≥2 capitalized Greek words (e.g., `Ιωάννης Παπαδόπουλος`) → `⟨ΟΝΟΜΑ⟩` (skip an ALL-CAPS whitelist: ΕΝΩΠΙΟΝ, ΔΙΚΑΣΤΗΡΙΟΥ, ΑΘΗΝΩΝ, ΓΙΑ, ΤΟΥΣ, ΛΟΓΟΥΣ, ΑΥΤΟΥΣ).
- Sample upload now stores `scrubbed_text=scrub(text)[0]`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_pii_scrub.py`:
```python
from app.agents.pii_scrub import scrub

def test_scrubs_afm_amka_amounts_dates_names():
    text = ("Ο Ιωάννης Παπαδόπουλος με ΑΦΜ 123456789 και ΑΜΚΑ 12345678901 "
            "οφείλει 14.500,00 € από 01/06/2026, υπόθεση 123/2026.")
    out, reps = scrub(text)
    for bad in ["123456789", "12345678901", "14.500,00", "01/06/2026",
                "Παπαδόπουλος", "123/2026"]:
        assert bad not in out
    assert "⟨ΑΦΜ⟩" in out and "⟨ΟΝΟΜΑ⟩" in out and "⟨ΠΟΣΟ⟩" in out
    assert len(reps) >= 5

def test_keeps_legal_caps():
    out, _ = scrub("ΕΝΩΠΙΟΝ ΤΟΥ ΜΟΝΟΜΕΛΟΥΣ ΠΡΩΤΟΔΙΚΕΙΟΥ")
    assert "ΕΝΩΠΙΟΝ" in out
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement**

`backend/app/agents/pii_scrub.py`:
```python
import re

CAPS_WHITELIST = {"ΕΝΩΠΙΟΝ", "ΔΙΚΑΣΤΗΡΙΟΥ", "ΜΟΝΟΜΕΛΟΥΣ", "ΠΟΛΥΜΕΛΟΥΣ",
                  "ΠΡΩΤΟΔΙΚΕΙΟΥ", "ΕΙΡΗΝΟΔΙΚΕΙΟΥ", "ΕΦΕΤΕΙΟΥ", "ΑΘΗΝΩΝ",
                  "ΓΙΑ", "ΤΟΥΣ", "ΛΟΓΟΥΣ", "ΑΥΤΟΥΣ", "ΑΝΑΚΟΠΗ", "ΑΓΩΓΗ"}

_GREEK_NAME = re.compile(
    r"\b[Α-ΩΆΈΉΊΌΎΏ][α-ωάέήίόύώϊϋΐΰ]+(?:\s+[Α-ΩΆΈΉΊΌΎΏ][α-ωάέήίόύώϊϋΐΰ]+)+\b")

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ΠΟΣΟ", re.compile(r"\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*(?:€|ευρώ)")),
    ("ΗΜΕΡΟΜΗΝΙΑ", re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b")),
    ("ΑΜΚΑ", re.compile(r"\b\d{11}\b")),
    ("ΑΦΜ", re.compile(r"\b\d{9}\b")),
    ("ΑΡΙΘΜΟΣ", re.compile(r"\b\d+/\d{4}\b")),
]

def scrub(text: str) -> tuple[str, list[dict]]:
    reps: list[dict] = []
    out = text
    for label, pat in PATTERNS:
        for m in pat.finditer(out):
            reps.append({"type": label, "original": m.group(0)})
        out = pat.sub(f"⟨{label}⟩", out)

    def _name(m: re.Match) -> str:
        if all(w.upper() in CAPS_WHITELIST for w in m.group(0).split()):
            return m.group(0)
        reps.append({"type": "ΟΝΟΜΑ", "original": m.group(0)})
        return "⟨ΟΝΟΜΑ⟩"

    out = _GREEK_NAME.sub(_name, out)
    return out, reps
```

In `uploads.py` `upload_sample`, after `extract_text`:
```python
from app.agents.pii_scrub import scrub
scrubbed, _ = scrub(text) if text else ("", [])
```
and pass `scrubbed_text=scrubbed`.

- [ ] **Step 4: Run** — both scrub tests + re-run `tests/test_uploads.py` → pass.
- [ ] **Step 5: Commit** — `git commit -am "feat: Greek PII scrubber wired into sample uploads"`

---

### Task 9: Intake extraction agent + endpoint

**Files:**
- Create: `backend/app/agents/intake_extract.py`
- Modify: `backend/app/api/cases.py` (add `POST /api/cases/{id}/extract`)
- Test: `backend/tests/test_intake_extract.py`

**Interfaces:**
- Produces: `run_extraction(provider, source_text: str) -> dict` — calls `load_prompt("intake_extract")`, `provider.generate(json_mode=True)`, parses JSON, then **quote validation**: for every item, `rapidfuzz.fuzz.partial_ratio(source_quote, source_text) >= 90` else `value=None, confidence=0.0, description += " [δεν επαληθεύτηκε στο κείμενο]"`. Returns dict with keys `parties, dates, amounts, claims`.
- Endpoint `POST /api/cases/{case_id}/extract`: concatenates `case.facts_text` + all evidence `extracted_text`, runs extraction, **deletes previous unconfirmed** Party/CaseFact rows for the case, inserts new ones (kinds: `date`, `amount`, `claim`), detects conflicts: two `amount` facts with same `description`-similarity ≥80 but different value → same `conflict_group`. Audits `extract.run`. Returns the case detail payload.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_intake_extract.py`:
```python
from app.agents.intake_extract import run_extraction
from app.ai.mock import MockProvider

def test_quote_validation_nulls_unfound_quotes():
    # Mock returns quote "14.500,00" etc.; source lacks the amount quote
    src = "Ο Ιωάννης Παπαδόπουλος έλαβε διαταγή πληρωμής την 1/6/2026"
    out = run_extraction(MockProvider(), src)
    amounts = out["amounts"]
    assert amounts[0]["value"] is None and amounts[0]["confidence"] == 0.0
    assert out["parties"][0]["name"] == "Ιωάννης Παπαδόπουλος"  # quote found

def test_extract_endpoint_creates_facts(auth_client):
    cid = auth_client.post("/api/clients", json={"name": "Π"}).json()["id"]
    case_id = auth_client.post("/api/cases",
        json={"client_id": cid, "title": "Υ"}).json()["id"]
    auth_client.patch(f"/api/cases/{case_id}", json={
        "facts_text": "Ο Ιωάννης Παπαδόπουλος οφείλει 14.500,00 βάσει "
                      "διαταγής πληρωμής που επιδόθηκε την 1/6/2026"})
    r = auth_client.post(f"/api/cases/{case_id}/extract")
    assert r.status_code == 200
    d = r.json()
    assert len(d["parties"]) == 1 and len(d["facts"]) >= 2
    assert all(not f["confirmed"] for f in d["facts"])
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement**

`backend/app/agents/intake_extract.py`:
```python
import json
from rapidfuzz import fuzz
from app.agents.prompts import load_prompt

KEYS = ["parties", "dates", "amounts", "claims"]

def run_extraction(provider, source_text: str) -> dict:
    system, _v = load_prompt("intake_extract")
    raw = provider.generate(system=system, user=source_text, json_mode=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {k: [] for k in KEYS}
    out: dict = {}
    for key in KEYS:
        items = []
        for it in data.get(key, []) or []:
            quote = (it.get("source_quote") or "").strip()
            ok = bool(quote) and fuzz.partial_ratio(quote, source_text) >= 90
            if not ok:
                it["value" if key != "parties" else "name"] = it.get(
                    "value" if key != "parties" else "name")
                if key != "parties":
                    it["value"] = None
                it["confidence"] = 0.0
                it["description"] = (it.get("description", "") +
                                     " [δεν επαληθεύτηκε στο κείμενο]").strip()
            items.append(it)
        out[key] = items
    return out
```

Add to `cases.py`:
```python
from rapidfuzz import fuzz as _fuzz
from app.ai.factory import get_provider
from app.agents.intake_extract import run_extraction

@router.post("/cases/{case_id}/extract")
def extract(case_id: int, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    c = get_case(db, user, case_id)
    texts = [c.facts_text] + [e.extracted_text for e in
             db.query(Evidence).filter_by(case_id=c.id) if e.extracted_text]
    source = "\n\n".join(t for t in texts if t)
    if not source.strip():
        raise HTTPException(400, "Δεν υπάρχουν γεγονότα ή αποδεικτικά για εξαγωγή")
    data = run_extraction(get_provider(), source)
    db.query(Party).filter_by(case_id=c.id, confirmed_by_lawyer=False).delete()
    db.query(CaseFact).filter_by(case_id=c.id, confirmed_by_lawyer=False).delete()
    for p in data["parties"]:
        db.add(Party(owner_user_id=user.id, case_id=c.id, name=p.get("name") or "",
                     role=p.get("role", ""), source_quote=p.get("source_quote", ""),
                     confidence=p.get("confidence", 0.0)))
    kind_map = {"dates": "date", "amounts": "amount", "claims": "claim"}
    new_facts = []
    for key, kind in kind_map.items():
        for it in data[key]:
            new_facts.append(CaseFact(
                owner_user_id=user.id, case_id=c.id, kind=kind,
                value=it.get("value"), description=it.get("description", ""),
                source_quote=it.get("source_quote", ""),
                confidence=it.get("confidence", 0.0)))
    # conflict detection among amounts
    group = 1
    amounts = [f for f in new_facts if f.kind == "amount" and f.value]
    for i in range(len(amounts)):
        for j in range(i + 1, len(amounts)):
            a, b = amounts[i], amounts[j]
            if (a.value != b.value and
                    _fuzz.ratio(a.description, b.description) >= 80):
                a.conflict_group = b.conflict_group = group
                group += 1
    db.add_all(new_facts)
    audit(db, user.id, "extract.run", "case", c.id)
    db.commit()
    return detail(case_id, user, db)
```

- [ ] **Step 4: Run** — `docker compose run --rm backend pytest tests/test_intake_extract.py -q` → 2 passed.
- [ ] **Step 5: Commit** — `git commit -am "feat: intake extraction with source-quote validation and conflict groups"`

---

### Task 10: Style profile — analyze, endpoints, sample embeddings/indexing

**Files:**
- Create: `backend/app/agents/style_analyze.py`, `backend/app/search/__init__.py`, `backend/app/search/index.py`, `backend/app/api/style.py`
- Modify: `backend/app/main.py`, `backend/app/api/uploads.py` (index samples on upload)
- Test: `backend/tests/test_style.py`

**Interfaces:**
- Produces: `build_profile(provider, scrubbed_samples: list[str]) -> dict` — prompt `style_analyze`, JSON-parse; then filter `phrase_bank` lists: keep phrase only if it appears (case-insensitive substring) in ≥2 samples; `index_text(db, user_id, kind, ref_id, case_id, text, provider)` — upserts `SearchIndex` row with embedding of first 2000 chars.
- Endpoints: `GET /api/style/profiles/{document_type_id}` → latest profile or 404; `POST /api/style/profiles/{document_type_id}/rebuild` → requires ≥3 samples with status `ok` (else 400 Greek message incl. count), creates new `StyleProfile` version, returns it; `PATCH /api/style/profiles/{profile_id}` body `{spec}` (lawyer edit, sets `approved_by_lawyer=true`).
- Sample upload now also calls `index_text(db, user.id, "sample", s.id, None, s.scrubbed_text, provider)` and stores `s.embedding = provider.embed([s.scrubbed_text[:2000]])[0]` when text non-empty.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_style.py`:
```python
import io
from docx import Document as Docx

def _docx(text):
    b = io.BytesIO(); d = Docx(); d.add_paragraph(text); d.save(b)
    return b.getvalue()

def _type_id():
    from app.db import SessionLocal
    from app.models import DocumentType
    db = SessionLocal()
    t = DocumentType(name_gr="Ανακοπή Τ", checklist_template=[])
    db.add(t); db.commit(); tid = t.id; db.close()
    return tid

def _upload(ac, tid, text):
    ac.post("/api/style/samples",
            files={"file": ("s.docx", _docx(text), "application/x")},
            data={"document_type_id": str(tid)})

def test_rebuild_requires_three_samples(auth_client):
    tid = _type_id()
    _upload(auth_client, tid, "ΕΝΩΠΙΟΝ ΤΟΥ ΔΙΚΑΣΤΗΡΙΟΥ Επειδή α")
    r = auth_client.post(f"/api/style/profiles/{tid}/rebuild")
    assert r.status_code == 400 and "1/3" in r.json()["detail"]

def test_rebuild_builds_profile(auth_client):
    tid = _type_id()
    for t in ["ΕΝΩΠΙΟΝ ΤΟΥ Επειδή πρώτον", "ΕΝΩΠΙΟΝ ΤΟΥ Επειδή δεύτερον",
              "ΕΝΩΠΙΟΝ ΤΟΥ Επειδή τρίτον"]:
        _upload(auth_client, tid, t)
    r = auth_client.post(f"/api/style/profiles/{tid}/rebuild")
    assert r.status_code == 200
    spec = r.json()["spec"]
    assert "Επειδή" in spec["phrase_bank"]["transitions"]
    r2 = auth_client.get(f"/api/style/profiles/{tid}")
    assert r2.json()["version"] == 1
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement**

`backend/app/agents/style_analyze.py`:
```python
import json
from app.agents.prompts import load_prompt

def build_profile(provider, scrubbed_samples: list[str]) -> dict:
    system, _v = load_prompt("style_analyze")
    joined = "\n\n=== ΔΕΙΓΜΑ ===\n\n".join(scrubbed_samples)
    raw = provider.generate(system=system, user=joined, json_mode=True)
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError:
        spec = {}
    bank = spec.get("phrase_bank", {})
    for key, phrases in list(bank.items()):
        kept = []
        for ph in phrases or []:
            hits = sum(1 for s in scrubbed_samples if ph.lower() in s.lower())
            if hits >= 2:
                kept.append(ph)
        bank[key] = kept
    spec["phrase_bank"] = bank
    return spec
```

`backend/app/search/index.py`:
```python
from app.models import SearchIndex

def index_text(db, user_id: int, kind: str, ref_id: int,
               case_id: int | None, text: str, provider):
    if not text or not text.strip():
        return
    row = db.query(SearchIndex).filter_by(kind=kind, ref_id=ref_id).first()
    emb = provider.embed([text[:2000]])[0]
    if row:
        row.text, row.embedding, row.case_id = text, emb, case_id
    else:
        db.add(SearchIndex(owner_user_id=user_id, kind=kind, ref_id=ref_id,
                           case_id=case_id, text=text, embedding=emb))
```

`backend/app/api/style.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import StyleProfile, StyleSample, User
from app.auth.deps import get_current_user
from app.ai.factory import get_provider
from app.agents.style_analyze import build_profile

router = APIRouter(prefix="/api/style/profiles")

def _serialize(p: StyleProfile) -> dict:
    return {"id": p.id, "document_type_id": p.document_type_id,
            "version": p.version, "spec": p.spec,
            "approved_by_lawyer": p.approved_by_lawyer,
            "built_from_sample_ids": p.built_from_sample_ids}

@router.get("/{document_type_id}")
def get_profile(document_type_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    p = (db.query(StyleProfile)
         .filter_by(owner_user_id=user.id, document_type_id=document_type_id)
         .order_by(StyleProfile.version.desc()).first())
    if not p:
        raise HTTPException(404, "Δεν υπάρχει προφίλ ύφους")
    return _serialize(p)

@router.post("/{document_type_id}/rebuild")
def rebuild(document_type_id: int, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    samples = (db.query(StyleSample)
               .filter_by(owner_user_id=user.id,
                          document_type_id=document_type_id, status="ok").all())
    if len(samples) < 3:
        raise HTTPException(400,
            f"Χρειάζονται τουλάχιστον 3 δείγματα ({len(samples)}/3). "
            "Συνιστώνται 10 για καλύτερη ποιότητα.")
    spec = build_profile(get_provider(), [s.scrubbed_text for s in samples])
    prev = (db.query(StyleProfile)
            .filter_by(owner_user_id=user.id, document_type_id=document_type_id)
            .order_by(StyleProfile.version.desc()).first())
    p = StyleProfile(owner_user_id=user.id, document_type_id=document_type_id,
                     version=(prev.version + 1) if prev else 1, spec=spec,
                     built_from_sample_ids=[s.id for s in samples])
    db.add(p); db.commit()
    return _serialize(p)

class SpecPatch(BaseModel):
    spec: dict

@router.patch("/{profile_id}")
def patch(profile_id: int, body: SpecPatch,
          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(StyleProfile).filter_by(id=profile_id, owner_user_id=user.id).first()
    if not p:
        raise HTTPException(404)
    p.spec = body.spec; p.approved_by_lawyer = True
    db.commit()
    return _serialize(p)
```

In `uploads.py` `upload_sample`, after creating `s` and before commit:
```python
from app.ai.factory import get_provider
from app.search.index import index_text
if s.scrubbed_text:
    provider = get_provider()
    s.embedding = provider.embed([s.scrubbed_text[:2000]])[0]
    index_text(db, user.id, "sample", s.id, None, s.scrubbed_text, provider)
```
Also in `upload_evidence`, index the extracted text:
```python
if text:
    index_text(db, user.id, "evidence", e.id, case_id, text, get_provider())
```
Include style router in `main.py`.

- [ ] **Step 4: Run** — `docker compose run --rm backend pytest tests/test_style.py tests/test_uploads.py -q` → all pass.
- [ ] **Step 5: Commit** — `git commit -am "feat: style profiles with >=2-sample phrase filter and sample indexing"`

---

### Task 11: Draft agent + generation pipeline (background) + document endpoints

**Files:**
- Create: `backend/app/agents/draft_agent.py`, `backend/app/agents/pipeline.py`, `backend/app/api/documents.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_draft.py`

**Interfaces:**
- Produces:
  - `build_case_file(db, case) -> dict` — `{title, court, parties:[{name,role}], facts:[{kind,value,description,source_quote}] (confirmed only), evidence:[{exhibit_number,description}], conflicts:[...]}`. **Only `confirmed_by_lawyer=True` parties/facts enter.**
  - `run_draft(provider, case_file, profile_spec, exemplars, doc_type_name) -> tuple[str, dict]` — returns `(content, uncertainty_report)`; report = `{"unverified_refs": count of "[ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ", "gaps": count of "[ΚΕΝΟ", "exemplar_count": n, "confirmed_fact_count": n}`.
  - `leak_scan(draft: str, case_file: dict) -> list[dict]` — red findings for any 9/11-digit number in draft absent from case-file values; `overlap_scan(draft, sample_texts) -> list[dict]` — yellow findings for verbatim ≥12-word spans shared with any sample.
  - `generate_document(document_id: int)` in `pipeline.py` — background job with own `SessionLocal`: loads doc/case/profile, picks top-3 exemplars by pgvector cosine between embedding of `case_file` JSON string and `StyleSample.embedding` (same user+type, status ok), calls `run_draft`, creates `DocumentVersion` (author `ai`, sha256 hash), updates `Document.current_version_id`, fills `AIDraft` (`status="ok"`, `inputs_manifest={model, prompt_version, profile_id, sample_ids, case_file_hash}`), then runs Task-12 functions (`consistency + checklist`) — Task 11 stubs that call with empty results if module missing is **not allowed**; instead Task 12 is imported lazily: `from app.agents.checklist import build_checklist` wrapped in try/ImportError→skip, replaced in Task 12. On exception: `AIDraft.status="failed"`, `error=str(e)`.
  - Endpoints: `POST /api/cases/{case_id}/documents {type_id, title}` → creates Document + AIDraft(status running) + schedules `BackgroundTasks.add_task(generate_document, doc.id)`; requires profile exists for type (400 otherwise); audits `draft.generate`. `GET /api/documents/{doc_id}` → `{id,title,status,type,case_id, draft:{status,error,uncertainty_report,inputs_manifest}, content, version_no, checklist:[...]}`. `POST /api/documents/{doc_id}/versions {content}` → new lawyer version.
- Consumes: `build_profile` output shape, `index_text`, `get_provider`, `load_prompt("draft")`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_draft.py`:
```python
import io, time
from docx import Document as Docx

def _docx(text):
    b = io.BytesIO(); d = Docx(); d.add_paragraph(text); d.save(b)
    return b.getvalue()

def _setup(ac):
    from app.db import SessionLocal
    from app.models import DocumentType
    db = SessionLocal(); t = DocumentType(name_gr="Ανακοπή Δ", checklist_template=["Ελέγξτε προθεσμία."])
    db.add(t); db.commit(); tid = t.id; db.close()
    for txt in ["ΕΝΩΠΙΟΝ Επειδή α", "ΕΝΩΠΙΟΝ Επειδή β", "ΕΝΩΠΙΟΝ Επειδή γ"]:
        ac.post("/api/style/samples",
                files={"file": ("s.docx", _docx(txt), "application/x")},
                data={"document_type_id": str(tid)})
    ac.post(f"/api/style/profiles/{tid}/rebuild")
    cid = ac.post("/api/clients", json={"name": "Π"}).json()["id"]
    case_id = ac.post("/api/cases", json={"client_id": cid, "title": "Υ"}).json()["id"]
    ac.patch(f"/api/cases/{case_id}", json={
        "facts_text": "Ο Ιωάννης Παπαδόπουλος οφείλει 14.500,00 από 1/6/2026 "
                      "βάσει διαταγής πληρωμής"})
    ac.post(f"/api/cases/{case_id}/extract")
    for f in ac.get(f"/api/cases/{case_id}").json()["facts"]:
        ac.patch(f"/api/facts/{f['id']}", json={"confirmed_by_lawyer": True})
    for p in ac.get(f"/api/cases/{case_id}").json()["parties"]:
        ac.patch(f"/api/parties/{p['id']}", json={"confirmed_by_lawyer": True})
    return tid, case_id

def test_generate_document_flow(auth_client):
    tid, case_id = _setup(auth_client)
    r = auth_client.post(f"/api/cases/{case_id}/documents",
                         json={"type_id": tid, "title": "Ανακοπή 1"})
    assert r.status_code == 200
    doc_id = r.json()["id"]
    for _ in range(20):  # TestClient runs background tasks synchronously post-response
        d = auth_client.get(f"/api/documents/{doc_id}").json()
        if d["draft"]["status"] != "running":
            break
        time.sleep(0.2)
    assert d["draft"]["status"] == "ok"
    assert "ΑΝΑΚΟΠΗ" in d["content"]
    assert d["draft"]["uncertainty_report"]["unverified_refs"] >= 1
    assert d["draft"]["inputs_manifest"]["prompt_version"] == 1

def test_requires_profile(auth_client):
    from app.db import SessionLocal
    from app.models import DocumentType
    db = SessionLocal(); t = DocumentType(name_gr="Χωρίς προφίλ", checklist_template=[])
    db.add(t); db.commit(); tid = t.id; db.close()
    cid = auth_client.post("/api/clients", json={"name": "Π"}).json()["id"]
    case_id = auth_client.post("/api/cases",
        json={"client_id": cid, "title": "Υ"}).json()["id"]
    r = auth_client.post(f"/api/cases/{case_id}/documents",
                         json={"type_id": tid, "title": "Χ"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement**

`backend/app/agents/draft_agent.py`:
```python
import json, re
from app.agents.prompts import load_prompt

def build_case_file(db, case) -> dict:
    from app.models import Party, CaseFact, Evidence
    parties = db.query(Party).filter_by(case_id=case.id, confirmed_by_lawyer=True).all()
    facts = db.query(CaseFact).filter_by(case_id=case.id, confirmed_by_lawyer=True).all()
    evidence = db.query(Evidence).filter_by(case_id=case.id).all()
    return {
        "title": case.title, "court": case.court_name, "category": case.category,
        "parties": [{"name": p.name, "role": p.role} for p in parties],
        "facts": [{"kind": f.kind, "value": f.value, "description": f.description,
                   "source_quote": f.source_quote} for f in facts],
        "evidence": [{"exhibit_number": e.exhibit_number,
                      "description": e.description} for e in evidence],
        "conflicts": [f.id for f in facts if f.conflict_group is not None],
    }

def run_draft(provider, case_file: dict, profile_spec: dict,
              exemplars: list[str], doc_type_name: str) -> tuple[str, dict]:
    system, version = load_prompt("draft")
    user = (f"ΤΥΠΟΣ ΕΓΓΡΑΦΟΥ: {doc_type_name}\n\n"
            f"CASE_FILE:\n{json.dumps(case_file, ensure_ascii=False, indent=1)}\n\n"
            f"STYLE_PROFILE:\n{json.dumps(profile_spec, ensure_ascii=False, indent=1)}\n\n"
            + "".join(f"EXEMPLAR (ανωνυμοποιημένο):\n{e[:4000]}\n\n" for e in exemplars))
    content = provider.generate(system=system, user=user)
    report = {
        "unverified_refs": content.count("[ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ"),
        "gaps": content.count("[ΚΕΝΟ"),
        "exemplar_count": len(exemplars),
        "confirmed_fact_count": len(case_file["facts"]),
        "prompt_version": version,
    }
    return content, report

def leak_scan(draft: str, case_file: dict) -> list[dict]:
    known = json.dumps(case_file, ensure_ascii=False)
    findings = []
    for num in set(re.findall(r"\b\d{9}\b|\b\d{11}\b", draft)):
        if num not in known:
            findings.append({"severity": "red", "source_agent": "leak_scan",
                             "text": f"Ο αριθμός {num} δεν υπάρχει στον φάκελο — "
                                     "πιθανή διαρροή από παλαιό έγγραφο.",
                             "anchor_quote": num})
    return findings

def overlap_scan(draft: str, sample_texts: list[str]) -> list[dict]:
    words = draft.split()
    findings, seen = [], set()
    for i in range(0, max(0, len(words) - 12), 4):
        span = " ".join(words[i:i + 12])
        if len(span) < 40 or span in seen:
            continue
        for s in sample_texts:
            if span in s:
                seen.add(span)
                findings.append({"severity": "yellow", "source_agent": "overlap_scan",
                                 "text": "Απόσπασμα ταυτίζεται αυτολεξεί με παλαιό "
                                         "δείγμα — ελέγξτε για μεταφορά περιεχομένου.",
                                 "anchor_quote": span[:120]})
                break
    return findings
```

`backend/app/agents/pipeline.py`:
```python
import hashlib, json
from app.db import SessionLocal
from app.models import (AIDraft, Case, Document, DocumentType, DocumentVersion,
                        StyleProfile, StyleSample)
from app.ai.factory import get_provider
from app.config import settings
from app.agents.draft_agent import build_case_file, run_draft, leak_scan, overlap_scan
from app.search.index import index_text

def generate_document(document_id: int):
    db = SessionLocal()
    draft_row = (db.query(AIDraft).filter_by(document_id=document_id)
                 .order_by(AIDraft.id.desc()).first())
    try:
        doc = db.get(Document, document_id)
        case = db.get(Case, doc.case_id)
        dtype = db.get(DocumentType, doc.type_id)
        profile = (db.query(StyleProfile)
                   .filter_by(owner_user_id=doc.owner_user_id, document_type_id=doc.type_id)
                   .order_by(StyleProfile.version.desc()).first())
        provider = get_provider()
        case_file = build_case_file(db, case)
        qvec = provider.embed([json.dumps(case_file, ensure_ascii=False)[:2000]])[0]
        samples = (db.query(StyleSample)
                   .filter_by(owner_user_id=doc.owner_user_id,
                              document_type_id=doc.type_id, status="ok")
                   .filter(StyleSample.embedding.isnot(None))
                   .order_by(StyleSample.embedding.cosine_distance(qvec))
                   .limit(3).all())
        exemplars = [s.scrubbed_text for s in samples]
        content, report = run_draft(provider, case_file, profile.spec,
                                    exemplars, dtype.name_gr)
        ver = DocumentVersion(owner_user_id=doc.owner_user_id, document_id=doc.id,
                              version_no=1, content=content, author="ai",
                              content_hash=hashlib.sha256(content.encode()).hexdigest())
        db.add(ver); db.flush()
        doc.current_version_id = ver.id
        draft_row.document_version_id = ver.id
        draft_row.style_profile_id = profile.id
        draft_row.status = "ok"
        draft_row.uncertainty_report = report
        draft_row.inputs_manifest = {
            "model": settings.ai_chat_model if settings.ai_provider != "mock" else "mock",
            "prompt_version": report["prompt_version"],
            "profile_id": profile.id, "profile_version": profile.version,
            "sample_ids": [s.id for s in samples],
            "case_file_hash": hashlib.sha256(
                json.dumps(case_file, ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest(),
        }
        findings = leak_scan(content, case_file) + overlap_scan(content, exemplars)
        from app.agents.checklist import run_checks  # Task 12
        run_checks(db, doc, case_file, content, dtype, extra_findings=findings)
        index_text(db, doc.owner_user_id, "document", doc.id, case.id,
                   content, provider)
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        if draft_row:
            draft_row.status = "failed"
            draft_row.error = f"Η δημιουργία απέτυχε: {e}"
            db.commit()
    finally:
        db.close()
```
(Task 12 creates `app/agents/checklist.py` with `run_checks`. Until then, add a temporary module in THIS task so imports resolve: `backend/app/agents/checklist.py` containing a minimal `run_checks(db, doc, case_file, content, dtype, extra_findings)` that only inserts `extra_findings` + template items as `ChecklistItem` rows plus the fixed attestation item — Task 12 extends it with consistency findings. Code below.)

Temporary `backend/app/agents/checklist.py` (extended in Task 12):
```python
from app.models import ChecklistItem

ATTESTATION = "Έλεγξα και εγκρίνω το έγγραφο ως δικηγόρος. Το AI βοηθά — ο δικηγόρος αποφασίζει."

def run_checks(db, doc, case_file, content, dtype, extra_findings=None):
    db.query(ChecklistItem).filter_by(document_id=doc.id).delete()
    items = list(extra_findings or [])
    if content.count("[ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ"):
        items.append({"severity": "red", "source_agent": "citation",
                      "text": f"{content.count('[ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ')} νομικές αναφορές "
                              "χωρίς πηγή — απαιτείται επαλήθευση.",
                      "anchor_quote": "[ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ"})
    for t in (dtype.checklist_template or []):
        items.append({"severity": "yellow", "source_agent": "procedure",
                      "text": t, "anchor_quote": ""})
    items.append({"severity": "red", "source_agent": "attestation",
                  "text": ATTESTATION, "anchor_quote": ""})
    for it in items:
        db.add(ChecklistItem(owner_user_id=doc.owner_user_id, document_id=doc.id,
                             **it))
```

`backend/app/api/documents.py`:
```python
import hashlib
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import (AIDraft, ChecklistItem, Document, DocumentType,
                        DocumentVersion, StyleProfile, User)
from app.auth.deps import get_current_user
from app.api.cases import get_case
from app.audit import audit
from app.agents.pipeline import generate_document

router = APIRouter(prefix="/api")

class DocIn(BaseModel):
    type_id: int
    title: str

class VersionIn(BaseModel):
    content: str

def get_doc(db, user, doc_id) -> Document:
    d = db.query(Document).filter_by(id=doc_id, owner_user_id=user.id).first()
    if not d:
        raise HTTPException(404, "Το έγγραφο δεν βρέθηκε")
    return d

@router.post("/cases/{case_id}/documents")
def create_doc(case_id: int, body: DocIn, bg: BackgroundTasks,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_case(db, user, case_id)
    if not db.get(DocumentType, body.type_id):
        raise HTTPException(404, "Άγνωστος τύπος εγγράφου")
    profile = (db.query(StyleProfile)
               .filter_by(owner_user_id=user.id, document_type_id=body.type_id)
               .first())
    if not profile:
        raise HTTPException(400,
            "Δεν υπάρχει προφίλ ύφους για αυτόν τον τύπο. Ανεβάστε δείγματα και "
            "δημιουργήστε προφίλ πρώτα.")
    doc = Document(owner_user_id=user.id, case_id=case_id,
                   type_id=body.type_id, title=body.title)
    db.add(doc); db.flush()
    db.add(AIDraft(owner_user_id=user.id, document_id=doc.id, status="running"))
    audit(db, user.id, "draft.generate", "document", doc.id)
    db.commit()
    bg.add_task(generate_document, doc.id)
    return {"id": doc.id}

@router.get("/documents/{doc_id}")
def get_document(doc_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    d = get_doc(db, user, doc_id)
    dtype = db.get(DocumentType, d.type_id)
    draft = (db.query(AIDraft).filter_by(document_id=d.id)
             .order_by(AIDraft.id.desc()).first())
    ver = db.get(DocumentVersion, d.current_version_id) if d.current_version_id else None
    items = db.query(ChecklistItem).filter_by(document_id=d.id).all()
    return {
        "id": d.id, "title": d.title, "status": d.status, "case_id": d.case_id,
        "type": dtype.name_gr,
        "draft": {"status": draft.status if draft else "none",
                  "error": draft.error if draft else "",
                  "uncertainty_report": draft.uncertainty_report if draft else {},
                  "inputs_manifest": draft.inputs_manifest if draft else {}},
        "content": ver.content if ver else "",
        "version_no": ver.version_no if ver else 0,
        "checklist": [{"id": i.id, "severity": i.severity, "text": i.text,
                       "source_agent": i.source_agent, "status": i.status,
                       "anchor_quote": i.anchor_quote,
                       "override_note": i.override_note} for i in items],
    }

@router.post("/documents/{doc_id}/versions")
def save_version(doc_id: int, body: VersionIn,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = get_doc(db, user, doc_id)
    if d.status != "draft":
        raise HTTPException(400, "Το έγγραφο έχει ήδη εγκριθεί")
    last = (db.query(DocumentVersion).filter_by(document_id=d.id)
            .order_by(DocumentVersion.version_no.desc()).first())
    ver = DocumentVersion(owner_user_id=user.id, document_id=d.id,
                          version_no=(last.version_no + 1) if last else 1,
                          content=body.content, author="lawyer",
                          content_hash=hashlib.sha256(body.content.encode()).hexdigest())
    db.add(ver); db.flush()
    d.current_version_id = ver.id
    db.commit()
    return {"version_no": ver.version_no}
```

Include `documents` router in `main.py`.

- [ ] **Step 4: Run** — `docker compose run --rm backend pytest tests/test_draft.py -q` → 2 passed.
- [ ] **Step 5: Commit** — `git commit -am "feat: draft pipeline with exemplar retrieval, leak/overlap scans, manifest"`

---

### Task 12: Consistency check, full checklist, override/resolve, approval

**Files:**
- Modify: `backend/app/agents/checklist.py` (extend), `backend/app/api/documents.py` (checklist + approve endpoints)
- Create: `backend/app/agents/consistency.py`
- Test: `backend/tests/test_checklist.py`

**Interfaces:**
- Produces: `check_consistency(case_file: dict, draft: str) -> list[dict]` — deterministic: (1) every confirmed `amount` value formatted Greek-style (`14500.00` → `14.500,00`) must appear in draft, else red "ποσό λείπει"; amounts in draft (regex) not in case file → red "ποσό δεν αντιστοιχεί στον φάκελο"; (2) party names: each confirmed party's surname (last word, length>3) should appear in draft (fuzzy ≥85 on any draft word) else yellow; (3) exhibit numbers referenced as `σχετικό N` in draft must exist in case_file evidence, else red.
- `run_checks` now = `extra_findings + check_consistency(...) + citation count + template + attestation` (same insert logic).
- Endpoints: `POST /api/checklist-items/{id}/resolve`; `POST /api/checklist-items/{id}/override {note}` (400 if note empty; audits `checklist.override`); `POST /api/documents/{id}/approve {attestation: bool}` — 400 unless attestation true; 400 listing count if any red item (except `source_agent=="attestation"`) not resolved/overridden; on success: attestation item → resolved, `Document.status="approved"`, audit `document.approve` with `{"content_hash": ...}`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_checklist.py`:
```python
from app.agents.consistency import check_consistency

CF = {"parties": [{"name": "Ιωάννης Παπαδόπουλος", "role": "ανακόπτων"}],
      "facts": [{"kind": "amount", "value": "14500.00", "description": "οφειλή",
                 "source_quote": "14.500,00"}],
      "evidence": [{"exhibit_number": 1, "description": "διαταγή"}]}

def test_amount_mismatch_is_red():
    findings = check_consistency(CF, "Οφειλή 15.400,00 ευρώ του Παπαδόπουλου (σχετικό 1)")
    reds = [f for f in findings if f["severity"] == "red"]
    assert any("15.400,00" in f["text"] or "14.500,00" in f["text"] for f in reds)

def test_unknown_exhibit_is_red():
    findings = check_consistency(CF, "ποσό 14.500,00 (σχετικό 7) του Παπαδόπουλου")
    assert any("σχετικό 7" in f["text"] for f in findings if f["severity"] == "red")

def test_clean_draft_no_reds():
    findings = check_consistency(CF, "Ο Παπαδόπουλος οφείλει 14.500,00 (σχετικό 1)")
    assert not [f for f in findings if f["severity"] == "red"]

def test_approve_blocked_then_allowed(auth_client):
    from tests.test_draft import _setup
    import time
    tid, case_id = _setup(auth_client)
    doc_id = auth_client.post(f"/api/cases/{case_id}/documents",
        json={"type_id": tid, "title": "Α"}).json()["id"]
    for _ in range(20):
        d = auth_client.get(f"/api/documents/{doc_id}").json()
        if d["draft"]["status"] != "running":
            break
        time.sleep(0.2)
    r = auth_client.post(f"/api/documents/{doc_id}/approve", json={"attestation": True})
    assert r.status_code == 400  # open red items exist (mock draft has ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ)
    for item in d["checklist"]:
        if item["severity"] == "red" and item["source_agent"] != "attestation":
            rr = auth_client.post(f"/api/checklist-items/{item['id']}/override",
                                  json={"note": ""})
            assert rr.status_code == 400  # empty note rejected
            auth_client.post(f"/api/checklist-items/{item['id']}/override",
                             json={"note": "ελέγχθηκε χειροκίνητα"})
    r = auth_client.post(f"/api/documents/{doc_id}/approve", json={"attestation": False})
    assert r.status_code == 400
    r = auth_client.post(f"/api/documents/{doc_id}/approve", json={"attestation": True})
    assert r.status_code == 200
    assert auth_client.get(f"/api/documents/{doc_id}").json()["status"] == "approved"
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement**

`backend/app/agents/consistency.py`:
```python
import re
from rapidfuzz import fuzz

def _gr_amount(value: str) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return value or ""
    whole, dec = f"{n:,.2f}".split(".")
    return whole.replace(",", ".") + "," + dec

AMOUNT_RE = re.compile(r"\b\d{1,3}(?:\.\d{3})+,\d{2}\b|\b\d+,\d{2}\b")
EXHIBIT_RE = re.compile(r"σχετικ[όο]\s+(\d+)", re.IGNORECASE)

def check_consistency(case_file: dict, draft: str) -> list[dict]:
    findings = []
    cf_amounts = {_gr_amount(f["value"]) for f in case_file.get("facts", [])
                  if f.get("kind") == "amount" and f.get("value")}
    for amt in cf_amounts:
        if amt and amt not in draft:
            findings.append({"severity": "red", "source_agent": "consistency",
                "text": f"Το ποσό {amt} του φακέλου δεν εμφανίζεται στο προσχέδιο.",
                "anchor_quote": amt})
    for amt in set(AMOUNT_RE.findall(draft)):
        if amt not in cf_amounts:
            findings.append({"severity": "red", "source_agent": "consistency",
                "text": f"Το ποσό {amt} του προσχεδίου δεν αντιστοιχεί σε "
                        "επιβεβαιωμένο στοιχείο του φακέλου.",
                "anchor_quote": amt})
    draft_words = draft.split()
    for p in case_file.get("parties", []):
        surname = (p.get("name") or "").split()[-1] if p.get("name") else ""
        if len(surname) > 3 and not any(
                fuzz.ratio(surname.lower(), w.strip(".,;:()").lower()) >= 85
                for w in draft_words):
            findings.append({"severity": "yellow", "source_agent": "consistency",
                "text": f"Ο διάδικος «{p['name']}» δεν εντοπίστηκε στο προσχέδιο.",
                "anchor_quote": p["name"]})
    known_exhibits = {e["exhibit_number"] for e in case_file.get("evidence", [])}
    for num in {int(n) for n in EXHIBIT_RE.findall(draft)}:
        if num not in known_exhibits:
            findings.append({"severity": "red", "source_agent": "consistency",
                "text": f"Αναφέρεται «σχετικό {num}» που δεν υπάρχει στον φάκελο.",
                "anchor_quote": f"σχετικό {num}"})
    return findings
```

Extend `checklist.py` `run_checks` — after `items = list(extra_findings or [])` add:
```python
from app.agents.consistency import check_consistency
items.extend(check_consistency(case_file, content))
```

Append to `documents.py`:
```python
class OverrideIn(BaseModel):
    note: str

class ApproveIn(BaseModel):
    attestation: bool = False

def _get_item(db, user, item_id) -> ChecklistItem:
    it = db.query(ChecklistItem).filter_by(id=item_id, owner_user_id=user.id).first()
    if not it:
        raise HTTPException(404)
    return it

@router.post("/checklist-items/{item_id}/resolve")
def resolve_item(item_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    it = _get_item(db, user, item_id)
    it.status, it.resolved_by = "resolved", user.id
    db.commit()
    return {"ok": True}

@router.post("/checklist-items/{item_id}/override")
def override_item(item_id: int, body: OverrideIn,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not body.note.strip():
        raise HTTPException(400, "Απαιτείται αιτιολόγηση για την παράκαμψη")
    it = _get_item(db, user, item_id)
    it.status, it.override_note, it.resolved_by = "overridden", body.note, user.id
    audit(db, user.id, "checklist.override", "checklist_item", it.id,
          {"note": body.note})
    db.commit()
    return {"ok": True}

@router.post("/documents/{doc_id}/approve")
def approve(doc_id: int, body: ApproveIn,
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = get_doc(db, user, doc_id)
    if not body.attestation:
        raise HTTPException(400, "Απαιτείται η βεβαίωση του δικηγόρου")
    open_reds = [i for i in db.query(ChecklistItem)
                 .filter_by(document_id=d.id, severity="red", status="open")
                 if i.source_agent != "attestation"]
    if open_reds:
        raise HTTPException(400,
            f"{len(open_reds)} κρίσιμα σημεία της λίστας ελέγχου εκκρεμούν")
    att = (db.query(ChecklistItem)
           .filter_by(document_id=d.id, source_agent="attestation").first())
    if att:
        att.status, att.resolved_by = "resolved", user.id
    d.status = "approved"
    ver = db.get(DocumentVersion, d.current_version_id)
    audit(db, user.id, "document.approve", "document", d.id,
          {"content_hash": ver.content_hash if ver else ""})
    db.commit()
    return {"ok": True}
```

- [ ] **Step 4: Run** — `docker compose run --rm backend pytest tests/test_checklist.py tests/test_draft.py -q` → all pass.
- [ ] **Step 5: Commit** — `git commit -am "feat: consistency checks, checklist gating, attested approval"`

---

### Task 13: DOCX export with approval gate

**Files:**
- Create: `backend/app/export/__init__.py`, `backend/app/export/docx.py`
- Modify: `backend/app/api/documents.py`
- Test: `backend/tests/test_export.py`

**Interfaces:**
- Produces: `export_docx(title: str, content: str, out_path: str)` — python-docx; title as centered bold heading; content split on `\n\n` into justified paragraphs; footer paragraph: `"Δημιουργήθηκε με υποβοήθηση AI — εγκρίθηκε από δικηγόρο. Grafida"`. Endpoint `GET /api/documents/{doc_id}/export` → **403 if `document.status == "draft"`**; else writes file to `settings.storage_dir/exports/`, sets `status="exported"` (if was `approved`), audits `document.export`, returns `FileResponse` with `media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_export.py`:
```python
import time

def _approved_doc(ac):
    from tests.test_draft import _setup
    tid, case_id = _setup(ac)
    doc_id = ac.post(f"/api/cases/{case_id}/documents",
                     json={"type_id": tid, "title": "Α"}).json()["id"]
    for _ in range(20):
        d = ac.get(f"/api/documents/{doc_id}").json()
        if d["draft"]["status"] != "running":
            break
        time.sleep(0.2)
    return doc_id, d

def test_export_blocked_before_approval(auth_client):
    doc_id, _ = _approved_doc(auth_client)
    assert auth_client.get(f"/api/documents/{doc_id}/export").status_code == 403

def test_export_after_approval(auth_client):
    doc_id, d = _approved_doc(auth_client)
    for item in d["checklist"]:
        if item["severity"] == "red" and item["source_agent"] != "attestation":
            auth_client.post(f"/api/checklist-items/{item['id']}/override",
                             json={"note": "ok"})
    auth_client.post(f"/api/documents/{doc_id}/approve", json={"attestation": True})
    r = auth_client.get(f"/api/documents/{doc_id}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument")
    assert auth_client.get(f"/api/documents/{doc_id}").json()["status"] == "exported"
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement**

`backend/app/export/docx.py`:
```python
import os
from docx import Document as Docx
from docx.enum.text import WD_ALIGN_PARAGRAPH

FOOTER = "Δημιουργήθηκε με υποβοήθηση AI — εγκρίθηκε από δικηγόρο. Grafida"

def export_docx(title: str, content: str, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    d = Docx()
    h = d.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = h.add_run(title)
    run.bold = True
    for para in content.split("\n\n"):
        p = d.add_paragraph(para.strip())
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    f = d.add_paragraph(FOOTER)
    f.alignment = WD_ALIGN_PARAGRAPH.CENTER
    d.save(out_path)
```

Append to `documents.py`:
```python
import os
from fastapi.responses import FileResponse
from app.config import settings
from app.export.docx import export_docx

@router.get("/documents/{doc_id}/export")
def export(doc_id: int, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    d = get_doc(db, user, doc_id)
    if d.status == "draft":
        raise HTTPException(403,
            "Το έγγραφο πρέπει πρώτα να εγκριθεί από δικηγόρο")
    ver = db.get(DocumentVersion, d.current_version_id)
    if not ver:
        raise HTTPException(400, "Δεν υπάρχει περιεχόμενο")
    out = os.path.join(settings.storage_dir, "exports", f"doc_{d.id}.docx")
    export_docx(d.title, ver.content, out)
    if d.status == "approved":
        d.status = "exported"
    audit(db, user.id, "document.export", "document", d.id)
    db.commit()
    return FileResponse(out, filename=f"{d.title}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
```

- [ ] **Step 4: Run** — 2 passed. **Step 5: Commit** — `git commit -am "feat: DOCX export gated on lawyer approval"`

---

### Task 14: Hybrid search + dashboard endpoint

**Files:**
- Create: `backend/app/search/service.py`, `backend/app/api/search.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_search.py`

**Interfaces:**
- Produces: `hybrid_search(db, user_id, q, provider, limit=10) -> list[dict]` — FTS: `SELECT id, kind, ref_id, case_id, ts_rank(tsv, plainto_tsquery('greek', :q)) AS r FROM search_index WHERE owner_user_id=:u AND tsv @@ plainto_tsquery('greek', :q) ORDER BY r DESC LIMIT 20`; vector: `ORDER BY embedding <=> :qvec LIMIT 20` (same owner filter); merge with RRF `score = Σ 1/(60+rank)`; return `[{kind, ref_id, case_id, snippet(200 chars around first query-word hit or start), score}]`.
- Endpoints: `GET /api/search?q=` (min 2 chars); `GET /api/dashboard` → `{open_cases:[{id,title,next_action}], deadlines:[{id,case_id,case_title,title,due_date}] (next 14 days, not completed), pending_drafts:[{document_id,title,status}]}` — all owner-filtered.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_search.py`:
```python
def test_search_finds_evidence_and_isolates_users(auth_client, client):
    import io
    from docx import Document as Docx
    b = io.BytesIO(); d = Docx()
    d.add_paragraph("μίσθωση ακινήτου στην Καλλιθέα με μηνιαίο μίσθωμα")
    d.save(b)
    cid = auth_client.post("/api/clients", json={"name": "Π"}).json()["id"]
    case_id = auth_client.post("/api/cases",
        json={"client_id": cid, "title": "Μίσθωση"}).json()["id"]
    auth_client.post(f"/api/cases/{case_id}/evidence",
        files={"file": ("m.docx", b.getvalue(), "application/x")},
        data={"description": "Μισθωτήριο"})
    r = auth_client.get("/api/search?q=μίσθωμα")
    assert r.status_code == 200 and len(r.json()) >= 1
    assert r.json()[0]["kind"] == "evidence"
    # user isolation
    client.post("/api/auth/register", json={"email": "z@z.gr", "password": "secret123"})
    client.post("/api/auth/login", json={"email": "z@z.gr", "password": "secret123"})
    assert client.get("/api/search?q=μίσθωμα").json() == []

def test_dashboard(auth_client):
    cid = auth_client.post("/api/clients", json={"name": "Π"}).json()["id"]
    case_id = auth_client.post("/api/cases",
        json={"client_id": cid, "title": "Υ"}).json()["id"]
    from datetime import date, timedelta
    auth_client.post(f"/api/cases/{case_id}/deadlines",
        json={"title": "Κατάθεση", "due_date": str(date.today() + timedelta(days=3))})
    d = auth_client.get("/api/dashboard").json()
    assert len(d["open_cases"]) == 1 and len(d["deadlines"]) == 1
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement**

`backend/app/search/service.py`:
```python
from sqlalchemy import text as sql
from app.models import SearchIndex

def _snippet(t: str, q: str, width: int = 200) -> str:
    low, pos = t.lower(), -1
    for w in q.lower().split():
        pos = low.find(w)
        if pos >= 0:
            break
    start = max(0, pos - width // 2) if pos >= 0 else 0
    return t[start:start + width]

def hybrid_search(db, user_id: int, q: str, provider, limit: int = 10) -> list[dict]:
    fts = db.execute(sql(
        "SELECT id FROM search_index WHERE owner_user_id=:u "
        "AND tsv @@ plainto_tsquery('greek', :q) "
        "ORDER BY ts_rank(tsv, plainto_tsquery('greek', :q)) DESC LIMIT 20"),
        {"u": user_id, "q": q}).scalars().all()
    qvec = provider.embed([q])[0]
    vec = [r.id for r in db.query(SearchIndex)
           .filter(SearchIndex.owner_user_id == user_id,
                   SearchIndex.embedding.isnot(None))
           .order_by(SearchIndex.embedding.cosine_distance(qvec)).limit(20)]
    scores: dict[int, float] = {}
    for ranked in (fts, vec):
        for rank, rid in enumerate(ranked):
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (60 + rank)
    top = sorted(scores, key=scores.get, reverse=True)[:limit]
    rows = {r.id: r for r in db.query(SearchIndex).filter(SearchIndex.id.in_(top))} if top else {}
    out = []
    for rid in top:
        r = rows.get(rid)
        if not r:
            continue
        item = {"kind": r.kind, "ref_id": r.ref_id, "case_id": r.case_id,
                "snippet": _snippet(r.text, q), "score": scores[rid]}
        # keyword-only relevance guard: keep vector-only hits but rank FTS first
        out.append(item)
    fts_set = set(fts)
    out.sort(key=lambda i: (0 if any(r.id in fts_set and r.ref_id == i["ref_id"]
                                     and r.kind == i["kind"]
                                     for r in rows.values()) else 1, -i["score"]))
    return out
```
Note for implementer: if no FTS hits AND query words don't appear in any vector-hit text, return `[]` — add after building `out`:
```python
    if not fts and not any(any(w in i["snippet"].lower() for w in q.lower().split())
                           for i in out):
        return []
```

`backend/app/api/search.py`:
```python
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import AIDraft, Case, Deadline, Document, User
from app.auth.deps import get_current_user
from app.ai.factory import get_provider
from app.search.service import hybrid_search

router = APIRouter(prefix="/api")

@router.get("/search")
def search(q: str, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    if len(q.strip()) < 2:
        raise HTTPException(400, "Πολύ σύντομο ερώτημα")
    return hybrid_search(db, user.id, q.strip(), get_provider())

@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cases = db.query(Case).filter_by(owner_user_id=user.id, status="open").all()
    cmap = {c.id: c.title for c in cases}
    horizon = date.today() + timedelta(days=14)
    dls = (db.query(Deadline)
           .filter(Deadline.owner_user_id == user.id,
                   Deadline.completed_at.is_(None),
                   Deadline.due_date <= horizon)
           .order_by(Deadline.due_date).all())
    pending = (db.query(Document)
               .filter(Document.owner_user_id == user.id,
                       Document.status == "draft").all())
    return {
        "open_cases": [{"id": c.id, "title": c.title,
                        "next_action": c.next_action} for c in cases],
        "deadlines": [{"id": d.id, "case_id": d.case_id,
                       "case_title": cmap.get(d.case_id, ""),
                       "title": d.title, "due_date": str(d.due_date)} for d in dls],
        "pending_drafts": [{"document_id": p.id, "title": p.title,
                            "status": p.status} for p in pending],
    }
```

Include router; run full suite: `docker compose run --rm backend pytest -q` → all pass.

- [ ] **Step 4: Commit** — `git commit -am "feat: hybrid Greek search (FTS+vector RRF) and dashboard endpoint"`

---

### Task 15: Frontend scaffold — Next.js, Tailwind, API client, login, layout

**Files:**
- Create: `frontend/` via scaffold, then `frontend/Dockerfile`, `frontend/src/lib/api.ts`, `frontend/src/app/login/page.tsx`, `frontend/src/app/layout.tsx`, `frontend/src/components/Nav.tsx`, replace `frontend/src/app/page.tsx` (placeholder dashboard: "Φόρτωση…" then case count; full dashboard in Task 18)

**Interfaces:**
- Produces: `api(path, init?)` and `apiForm(path, formData)` fetch wrappers (credentials include, 401 → redirect `/login`, non-OK → throw Greek `detail`); `<Nav/>` with links Αρχική/Υποθέσεις/Πελάτες/Ύφος/Αναζήτηση + logout; all later pages are `"use client"` components using these.

- [ ] **Step 1: Scaffold**

Run (from repo root):
```bash
npx --yes create-next-app@latest frontend --ts --tailwind --eslint --app --src-dir --no-import-alias --use-npm
```

`frontend/Dockerfile`:
```dockerfile
FROM node:22-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
```

- [ ] **Step 2: Implement shared pieces**

`frontend/src/lib/api.ts`:
```ts
export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function handle(res: Response) {
  if (res.status === 401 && typeof window !== "undefined"
      && !location.pathname.startsWith("/login")) {
    location.href = "/login";
  }
  if (!res.ok) {
    let msg = "Σφάλμα";
    try { msg = (await res.json()).detail ?? msg; } catch {}
    throw new Error(msg);
  }
  return res;
}

export async function api(path: string, init?: RequestInit) {
  return handle(await fetch(`${API}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  }));
}

export async function apiForm(path: string, form: FormData) {
  return handle(await fetch(`${API}${path}`, {
    method: "POST", credentials: "include", body: form,
  }));
}
```

`frontend/src/components/Nav.tsx`:
```tsx
"use client";
import Link from "next/link";
import { api } from "@/lib/api";

export default function Nav() {
  return (
    <nav className="flex items-center gap-6 border-b bg-white px-6 py-3 text-sm">
      <span className="font-bold text-indigo-700">Grafida</span>
      <Link href="/">Αρχική</Link>
      <Link href="/cases">Υποθέσεις</Link>
      <Link href="/clients">Πελάτες</Link>
      <Link href="/style">Το ύφος μου</Link>
      <Link href="/search">Αναζήτηση</Link>
      <button className="ml-auto text-gray-500"
        onClick={async () => { await api("/api/auth/logout", { method: "POST" });
                               location.href = "/login"; }}>
        Αποσύνδεση
      </button>
    </nav>
  );
}
```

`frontend/src/app/layout.tsx` — html lang="el", body `bg-gray-50`, render `<Nav/>` above `{children}` in a `max-w-6xl mx-auto p-6` main. `login/page.tsx`:
```tsx
"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export default function Login() {
  const [email, setEmail] = useState(""); const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  return (
    <div className="mx-auto mt-24 max-w-sm rounded-xl border bg-white p-8 shadow-sm">
      <h1 className="mb-1 text-xl font-bold text-indigo-700">Grafida</h1>
      <p className="mb-6 text-sm text-gray-500">
        Το AI βοηθά — ο δικηγόρος αποφασίζει.</p>
      <form onSubmit={async (e) => { e.preventDefault(); setErr("");
        try {
          await api("/api/auth/login", { method: "POST",
            body: JSON.stringify({ email, password: pw }) });
          location.href = "/";
        } catch (x) { setErr((x as Error).message); } }}>
        <input className="mb-3 w-full rounded border p-2" placeholder="Email"
               value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="mb-3 w-full rounded border p-2" type="password"
               placeholder="Κωδικός" value={pw}
               onChange={(e) => setPw(e.target.value)} />
        {err && <p className="mb-3 text-sm text-red-600">{err}</p>}
        <button className="w-full rounded bg-indigo-600 p-2 text-white">
          Σύνδεση</button>
      </form>
    </div>
  );
}
```
(Hide `<Nav/>` on `/login`: in `Nav.tsx` return `null` when `usePathname() === "/login"`.)

- [ ] **Step 3: Verify** — `cd frontend && npm run build` → build succeeds. `docker compose up -d frontend backend` → login page at `http://localhost:3000/login` authenticates against seeded user.
- [ ] **Step 4: Commit** — `git add frontend && git commit -m "feat: frontend scaffold, api client, Greek login"`

---

### Task 16: Frontend — clients, cases list, case detail (facts, evidence, extraction review)

**Files:**
- Create: `frontend/src/app/clients/page.tsx`, `frontend/src/app/cases/page.tsx`, `frontend/src/app/cases/[id]/page.tsx`, `frontend/src/components/ExtractionReview.tsx`

**Interfaces:**
- Consumes: Task 5/6/9 endpoints exactly as defined.
- Produces: case detail page with sections: Στοιχεία (editable facts_text + court + next_action, PATCH on blur), Σχετικά (evidence list + upload form), Εξαγωγή στοιχείων button → POST extract → renders `<ExtractionReview/>`, Προθεσμίες (list + add), Έγγραφα (list linking `/drafts/{id}` + "Νέο έγγραφο με AI" select+button → POST documents → router.push `/drafts/{id}`).

- [ ] **Step 1: Implement pages**

`clients/page.tsx` — table of clients + inline create form (name, ΑΦΜ, phone):
```tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type C = { id: number; name: string; afm?: string; phone?: string };
export default function Clients() {
  const [rows, setRows] = useState<C[]>([]); const [name, setName] = useState("");
  const load = () => api("/api/clients").then(r => r.json()).then(setRows);
  useEffect(() => { load(); }, []);
  return (
    <div>
      <h1 className="mb-4 text-lg font-bold">Πελάτες</h1>
      <form className="mb-4 flex gap-2" onSubmit={async e => { e.preventDefault();
        await api("/api/clients", { method: "POST",
          body: JSON.stringify({ name }) }); setName(""); load(); }}>
        <input className="rounded border p-2" placeholder="Ονοματεπώνυμο"
               value={name} onChange={e => setName(e.target.value)} />
        <button className="rounded bg-indigo-600 px-4 text-white">Προσθήκη</button>
      </form>
      <table className="w-full rounded border bg-white text-sm">
        <tbody>{rows.map(c => (
          <tr key={c.id} className="border-b">
            <td className="p-2 font-medium">{c.name}</td>
            <td className="p-2 text-gray-500">{c.afm ?? "—"}</td>
            <td className="p-2 text-gray-500">{c.phone ?? "—"}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}
```

`cases/page.tsx` — same pattern: list (title, court, status, next_action) linking to `/cases/{id}`; create form needs a client select (`GET /api/clients`) + title.

`cases/[id]/page.tsx` — loads `GET /api/cases/{id}` into state `d`, refetch helper `reload()`. Renders sections in order; each is a bordered white card. Key excerpts (write the full file combining these):
```tsx
"use client";
import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { api, apiForm } from "@/lib/api";
import ExtractionReview from "@/components/ExtractionReview";

export default function CaseDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [d, setD] = useState<any>(null);
  const [file, setFile] = useState<File | null>(null);
  const [typeId, setTypeId] = useState(""); const [busy, setBusy] = useState(false);
  const reload = () => api(`/api/cases/${id}`).then(r => r.json()).then(setD);
  useEffect(() => { reload(); }, [id]);
  if (!d) return <p>Φόρτωση…</p>;
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-bold">{d.title}
        <span className="ml-2 text-sm font-normal text-gray-500">
          {d.client.name} · {d.court_name || "χωρίς δικαστήριο"}</span></h1>

      <section className="rounded border bg-white p-4">
        <h2 className="mb-2 font-semibold">Γεγονότα υπόθεσης</h2>
        <textarea className="w-full rounded border p-2" rows={5}
          defaultValue={d.facts_text}
          onBlur={e => api(`/api/cases/${id}`, { method: "PATCH",
            body: JSON.stringify({ facts_text: e.target.value }) })} />
        <button className="mt-2 rounded bg-indigo-600 px-4 py-1 text-white"
          disabled={busy}
          onClick={async () => { setBusy(true);
            try { await api(`/api/cases/${id}/extract`, { method: "POST" });
                  await reload(); } finally { setBusy(false); } }}>
          {busy ? "Εξαγωγή…" : "Εξαγωγή στοιχείων με AI"}</button>
      </section>

      {(d.parties.length > 0 || d.facts.length > 0) &&
        <ExtractionReview d={d} onChange={reload} />}

      <section className="rounded border bg-white p-4">
        <h2 className="mb-2 font-semibold">Σχετικά</h2>
        <ul className="mb-3 text-sm">{d.evidence.map((e: any) => (
          <li key={e.id}>Σχετικό {e.exhibit_number}: {e.description}
            {e.ocr_pending && <span className="ml-2 text-amber-600">
              OCR εκκρεμεί — δεν αναγνώστηκε κείμενο</span>}</li>))}</ul>
        <form className="flex gap-2" onSubmit={async e => { e.preventDefault();
          if (!file) return;
          const f = new FormData(); f.append("file", file);
          f.append("description", file.name);
          await apiForm(`/api/cases/${id}/evidence`, f);
          setFile(null); reload(); }}>
          <input type="file" accept=".pdf,.docx,.txt"
                 onChange={e => setFile(e.target.files?.[0] ?? null)} />
          <button className="rounded bg-gray-800 px-3 py-1 text-sm text-white">
            Μεταφόρτωση</button>
        </form>
      </section>

      <section className="rounded border bg-white p-4">
        <h2 className="mb-2 font-semibold">Έγγραφα</h2>
        <ul className="mb-3 text-sm">{d.documents.map((doc: any) => (
          <li key={doc.id}>
            <a className="text-indigo-700 underline" href={`/drafts/${doc.id}`}>
              {doc.title}</a> — {doc.type} ({doc.status})</li>))}</ul>
        <div className="flex gap-2">
          <select className="rounded border p-2" value={typeId}
                  onChange={e => setTypeId(e.target.value)}>
            <option value="">Τύπος εγγράφου…</option>
            {d.document_types.map((t: any) =>
              <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <button className="rounded bg-indigo-600 px-4 py-1 text-white"
            onClick={async () => {
              if (!typeId) return;
              const r = await api(`/api/cases/${id}/documents`, { method: "POST",
                body: JSON.stringify({ type_id: Number(typeId),
                  title: `${d.document_types.find((t: any) => t.id == typeId)?.name} — ${d.title}` }) });
              router.push(`/drafts/${(await r.json()).id}`); }}>
            Νέο έγγραφο με AI</button>
        </div>
      </section>
      {/* Προθεσμίες section: list d.deadlines + date/title inputs POSTing to
          /api/cases/{id}/deadlines, same form pattern as above */}
    </div>
  );
}
```

`components/ExtractionReview.tsx`:
```tsx
"use client";
import { api } from "@/lib/api";

const KIND: Record<string, string> = {
  date: "Ημερομηνία", amount: "Ποσό", claim: "Αίτημα", other: "Άλλο" };

export default function ExtractionReview({ d, onChange }:
    { d: any; onChange: () => void }) {
  const confirm = (kind: "parties" | "facts", id: number) =>
    api(`/api/${kind === "parties" ? "parties" : "facts"}/${id}`, {
      method: "PATCH", body: JSON.stringify({ confirmed_by_lawyer: true }),
    }).then(onChange);
  const Row = ({ label, quote, conf, confirmed, warn, onOk }: any) => (
    <div className={`flex items-center gap-3 border-b py-2 text-sm
        ${warn ? "bg-amber-50" : ""}`}>
      <div className="flex-1">
        <div>{label}</div>
        <div className="text-xs text-gray-500">
          πηγή: «{quote || "—"}» · βεβαιότητα {(conf * 100).toFixed(0)}%</div>
      </div>
      {confirmed
        ? <span className="text-green-700">✓ Επιβεβαιώθηκε</span>
        : <button className="rounded bg-green-600 px-3 py-1 text-white"
                  onClick={onOk}>Επιβεβαίωση</button>}
    </div>);
  return (
    <section className="rounded border bg-white p-4">
      <h2 className="mb-1 font-semibold">Έλεγχος εξαγωγής</h2>
      <p className="mb-3 text-xs text-gray-500">
        Επιβεβαιώστε κάθε στοιχείο — μόνο επιβεβαιωμένα στοιχεία
        χρησιμοποιούνται στη σύνταξη.</p>
      {d.parties.map((p: any) => (
        <Row key={`p${p.id}`} label={`Διάδικος: ${p.name} (${p.role})`}
             quote={p.source_quote} conf={p.confidence} confirmed={p.confirmed}
             warn={p.confidence < 0.8} onOk={() => confirm("parties", p.id)} />))}
      {d.facts.map((f: any) => (
        <Row key={`f${f.id}`}
             label={`${KIND[f.kind]}: ${f.value ?? "—"} · ${f.description}`}
             quote={f.source_quote} conf={f.confidence} confirmed={f.confirmed}
             warn={f.confidence < 0.8 || f.conflict_group != null}
             onOk={() => confirm("facts", f.id)} />))}
    </section>
  );
}
```

- [ ] **Step 2: Verify** — `npm run build` passes; manual flow: create client → case → paste facts → extract → confirm rows.
- [ ] **Step 3: Commit** — `git commit -am "feat: clients/cases pages with extraction review"`

---

### Task 17: Frontend — style page + draft workspace

**Files:**
- Create: `frontend/src/app/style/page.tsx`, `frontend/src/app/drafts/[id]/page.tsx`

**Interfaces:**
- Consumes: Tasks 6/10 style endpoints; Tasks 11–13 document endpoints.
- Produces: style page — doc-type select, sample list with count badge `n/10`, upload form, "Δημιουργία/Ανανέωση προφίλ" button, profile display (structure table, phrase-bank chips with × delete → PATCH spec, tone), warning banner when samples < 10. Draft page — poller (2 s while `draft.status==="running"`), error banner on `failed`, textarea editor + "Αποθήκευση" (POST versions), transparency panel from `uncertainty_report`+`inputs_manifest` («Τι χρησιμοποίησα: N δείγματα, M επιβεβαιωμένα στοιχεία· Αβεβαιότητες: X αναφορές προς επαλήθευση»), checklist sidebar (red/yellow, Επιλύθηκε / Παράκαμψη-με-σημείωση buttons), approve modal (attestation checkbox → POST approve), export button (`window.open(API + "/api/documents/{id}/export")`) shown only when status ≠ draft; persistent banner «Προσχέδιο AI — απαιτείται έλεγχος δικηγόρου» while status === "draft".

- [ ] **Step 1: Implement**

`style/page.tsx` core logic (write full file with imports/useState as in prior pages):
```tsx
// state: types[], typeId, samples[], profile|null, file
// load types from any case? No—add GET /api/document-types? Use existing:
// document_types come with case detail; for the style page add a tiny fetch:
// api("/api/style/samples?document_type_id=..") for samples and
// api(`/api/style/profiles/${typeId}`) for profile (404 → null).
// NOTE: add GET /api/document-types endpoint to backend cases.py router:
//   @router.get("/document-types")
//   def doc_types(db=Depends(get_db), user=Depends(get_current_user)):
//       return [{"id": t.id, "name": t.name_gr} for t in db.query(DocumentType).all()]
// (2-line backend addition, include in this task's commit + a one-line test)
```
Full page: select doc type → shows `Δείγματα {samples.length}/10` (red text if <3, amber if <10), file input + upload via `apiForm("/api/style/samples", form)`, rebuild button → `api(`/api/style/profiles/${typeId}/rebuild`, {method:"POST"})` (show err.detail on 400), profile card mapping `spec.structure` rows and phrase chips:
```tsx
{Object.entries(profile.spec.phrase_bank ?? {}).map(([k, arr]: any) => (
  <div key={k} className="mb-2">
    <span className="text-xs uppercase text-gray-500">{k}</span>
    <div className="flex flex-wrap gap-1">{arr.map((ph: string) => (
      <span key={ph} className="rounded bg-indigo-50 px-2 py-0.5 text-sm">
        {ph}<button className="ml-1 text-gray-400" onClick={() => {
          const spec = structuredClone(profile.spec);
          spec.phrase_bank[k] = spec.phrase_bank[k].filter((x: string) => x !== ph);
          api(`/api/style/profiles/${profile.id}`, { method: "PATCH",
            body: JSON.stringify({ spec }) }).then(loadProfile);
        }}>×</button></span>))}</div>
  </div>))}
```

`drafts/[id]/page.tsx` — full file; core structure:
```tsx
"use client";
import { useEffect, useRef, useState, use } from "react";
import { api, API } from "@/lib/api";

export default function Draft({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [d, setD] = useState<any>(null);
  const [content, setContent] = useState("");
  const [attest, setAttest] = useState(false);
  const [note, setNote] = useState<Record<number, string>>({});
  const timer = useRef<any>(null);
  const load = async () => {
    const j = await (await api(`/api/documents/${id}`)).json();
    setD(j); setContent(j.content);
    if (j.draft.status === "running")
      timer.current = setTimeout(load, 2000);
  };
  useEffect(() => { load(); return () => clearTimeout(timer.current); }, [id]);
  if (!d) return <p>Φόρτωση…</p>;
  if (d.draft.status === "running")
    return <p className="animate-pulse">Το AI συντάσσει το προσχέδιο…</p>;
  if (d.draft.status === "failed")
    return <p className="text-red-600">{d.draft.error}</p>;
  const reds = d.checklist.filter((i: any) =>
    i.severity === "red" && i.status === "open" && i.source_agent !== "attestation");
  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="col-span-2">
        {d.status === "draft" &&
          <div className="mb-2 rounded bg-amber-100 p-2 text-sm">
            Προσχέδιο AI — απαιτείται έλεγχος δικηγόρου</div>}
        <h1 className="mb-2 font-bold">{d.title}</h1>
        <textarea className="h-[60vh] w-full rounded border p-3 font-serif"
          value={content} onChange={e => setContent(e.target.value)}
          disabled={d.status !== "draft"} />
        <div className="mt-2 flex gap-2">
          {d.status === "draft" && <>
            <button className="rounded bg-gray-800 px-4 py-1 text-white"
              onClick={() => api(`/api/documents/${id}/versions`, {
                method: "POST", body: JSON.stringify({ content }) }).then(load)}>
              Αποθήκευση</button>
            <button className="rounded bg-green-700 px-4 py-1 text-white
                               disabled:opacity-40" disabled={reds.length > 0}
              onClick={async () => {
                if (!attest) { alert("Απαιτείται η βεβαίωση"); return; }
                await api(`/api/documents/${id}/approve`, { method: "POST",
                  body: JSON.stringify({ attestation: true }) }); load(); }}>
              Έγκριση</button></>}
          {d.status !== "draft" &&
            <button className="rounded bg-indigo-600 px-4 py-1 text-white"
              onClick={() => window.open(`${API}/api/documents/${id}/export`)}>
              Εξαγωγή σε Word</button>}
        </div>
        {d.status === "draft" &&
          <label className="mt-2 block text-sm">
            <input type="checkbox" checked={attest}
                   onChange={e => setAttest(e.target.checked)} className="mr-2" />
            Έλεγξα και εγκρίνω το έγγραφο ως δικηγόρος. Το AI βοηθά — ο
            δικηγόρος αποφασίζει.</label>}
        <div className="mt-4 rounded border bg-white p-3 text-xs text-gray-600">
          Τι χρησιμοποίησα: {d.draft.uncertainty_report.exemplar_count ?? 0} δείγματα,
          {" "}{d.draft.uncertainty_report.confirmed_fact_count ?? 0} επιβεβαιωμένα
          στοιχεία · Αβεβαιότητες: {d.draft.uncertainty_report.unverified_refs ?? 0}
          {" "}αναφορές προς επαλήθευση, {d.draft.uncertainty_report.gaps ?? 0} κενά ·
          Μοντέλο: {d.draft.inputs_manifest.model}
        </div>
      </div>
      <aside className="space-y-2">
        <h2 className="font-semibold">Λίστα ελέγχου</h2>
        {d.checklist.map((i: any) => (
          <div key={i.id} className={`rounded border p-2 text-sm ${
              i.severity === "red" ? "border-red-300 bg-red-50"
                                   : "border-amber-300 bg-amber-50"}`}>
            <p>{i.text}</p>
            {i.status === "open" && i.source_agent !== "attestation" &&
             d.status === "draft" && (
              <div className="mt-1 flex gap-1">
                <button className="rounded bg-green-600 px-2 text-xs text-white"
                  onClick={() => api(`/api/checklist-items/${i.id}/resolve`,
                    { method: "POST" }).then(load)}>Επιλύθηκε</button>
                {i.severity === "red" && <>
                  <input className="w-24 rounded border px-1 text-xs"
                    placeholder="αιτιολόγηση" value={note[i.id] ?? ""}
                    onChange={e => setNote({ ...note, [i.id]: e.target.value })} />
                  <button className="rounded bg-gray-600 px-2 text-xs text-white"
                    onClick={() => api(`/api/checklist-items/${i.id}/override`,
                      { method: "POST",
                        body: JSON.stringify({ note: note[i.id] ?? "" }) })
                      .then(load).catch(e => alert(e.message))}>
                    Παράκαμψη</button></>}
              </div>)}
            {i.status !== "open" &&
              <p className="text-xs text-gray-500">
                {i.status === "resolved" ? "✓ Επιλύθηκε"
                  : `Παρακάμφθηκε: ${i.override_note}`}</p>}
          </div>))}
      </aside>
    </div>
  );
}
```
Backend addition in this task: `GET /api/document-types` (see note above) + one-line pytest asserting 200 and ≥0 rows.

- [ ] **Step 2: Verify** — `npm run build`; manual: full flow style → draft → checklist → approve → export downloads a .docx.
- [ ] **Step 3: Commit** — `git commit -am "feat: style training page and draft workspace with gated approval"`

---

### Task 18: Frontend dashboard + search page; README finalize; full-suite pass

**Files:**
- Modify: `frontend/src/app/page.tsx` (real dashboard), `README.md`
- Create: `frontend/src/app/search/page.tsx`

**Interfaces:** Consumes `GET /api/dashboard`, `GET /api/search?q=`.

- [ ] **Step 1: Implement**

`page.tsx` — three cards from `/api/dashboard`: «Ανοιχτές υποθέσεις» (link each to `/cases/{id}`, show next_action), «Προθεσμίες 14 ημερών» (red row when due ≤3 days: compare `due_date` with today), «Προσχέδια σε εκκρεμότητα» (link `/drafts/{document_id}`). Same fetch/useEffect pattern as prior pages.

`search/page.tsx`:
```tsx
"use client";
import { useState } from "react";
import { api } from "@/lib/api";

const KIND: Record<string, string> = {
  document: "Έγγραφο", evidence: "Σχετικό", sample: "Δείγμα ύφους" };

export default function Search() {
  const [q, setQ] = useState(""); const [rows, setRows] = useState<any[]>([]);
  const [done, setDone] = useState(false);
  return (
    <div>
      <form className="mb-4 flex gap-2" onSubmit={async e => { e.preventDefault();
        setRows(await (await api(`/api/search?q=${encodeURIComponent(q)}`)).json());
        setDone(true); }}>
        <input className="flex-1 rounded border p-2"
          placeholder="Αναζήτηση σε υποθέσεις, έγγραφα, δείγματα…"
          value={q} onChange={e => setQ(e.target.value)} />
        <button className="rounded bg-indigo-600 px-4 text-white">Αναζήτηση</button>
      </form>
      {done && rows.length === 0 && <p className="text-gray-500">Δεν βρέθηκε
        σχετικό υλικό στο αρχείο σας.</p>}
      {rows.map((r, i) => (
        <div key={i} className="mb-2 rounded border bg-white p-3 text-sm">
          <span className="mr-2 rounded bg-gray-100 px-2 py-0.5 text-xs">
            {KIND[r.kind] ?? r.kind}</span>
          {r.case_id && <a className="text-indigo-700 underline"
            href={`/cases/${r.case_id}`}>Υπόθεση #{r.case_id}</a>}
          <p className="mt-1 text-gray-600">…{r.snippet}…</p>
        </div>))}
    </div>
  );
}
```

`README.md` — finalize: prerequisites, Ollama setup (`ollama pull qwen2.5:7b && ollama pull bge-m3`; note: try `ollama pull ilsp/llama-krikri-8b` and set `AI_CHAT_MODEL` if available), run, login, **manual E2E script** (the 11-step flow from the spec), **manual model-quality checklist** (draft uses lawyer's phrases? facts only from case file? unverified refs flagged?), test command, disclaimer paragraph («Το Grafida βοηθά — ο δικηγόρος αποφασίζει...»).

- [ ] **Step 2: Full verification**

Run: `docker compose run --rm backend pytest -q` → all pass. `cd frontend && npm run build` → success. `docker compose up` → walk the manual E2E script end-to-end with Ollama running.
Expected: complete flow works; export downloads DOCX only after attested approval.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: dashboard, search page, final README with E2E script"
```

---

## Self-review notes (already applied)

- Spec coverage: flow steps 1–14 → Tasks 4–13; search → 14/18; style editing → 10/17; audit events → Tasks 4,5,6,9,11,12,13; leak/overlap scans → Task 11; conflict groups → Task 9; OCR-pending flagging → Task 6; attestation gate server-side → Task 12/13. Alembic deviation documented in Global Constraints and spec.
- Type consistency: `run_checks(db, doc, case_file, content, dtype, extra_findings)` defined in Task 11, extended (not renamed) in Task 12; `get_case`/`get_doc` helpers reused; `EMBED_DIM=1024` used by models, mock, ollama.
- Known simplification: `overlap_scan` uses whitespace tokenization (no legal-formula whitelist yet — the whitelist lives in `CAPS_WHITELIST` only for scrubbing); acceptable for slice, noted for post-slice.
