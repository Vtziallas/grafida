import os

os.environ["AI_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = "postgresql+psycopg://grafida:grafida@db:5432/grafida_test"
os.environ["STORAGE_DIR"] = "/tmp/grafida_test_uploads"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


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
    with engine.begin() as c:
        for t in reversed(Base.metadata.sorted_tables):
            c.execute(text(f'TRUNCATE "{t.name}" RESTART IDENTITY CASCADE'))


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
