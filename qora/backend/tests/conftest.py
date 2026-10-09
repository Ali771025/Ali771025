"""Shared test fixtures — isolated SQLite per test session."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./qora_test.db"


@pytest.fixture(scope="session")
def client():
    if os.path.exists("qora_test.db"):
        os.remove("qora_test.db")
    from app.core.db import Base, engine
    import app.modules  # noqa: F401

    Base.metadata.create_all(bind=engine)
    from seed import seed

    seed()
    from app.main import app

    with TestClient(app) as c:
        yield c
    if os.path.exists("qora_test.db"):
        os.remove("qora_test.db")


@pytest.fixture()
def emma(client):
    t = client.post("/api/v1/auth/login", json={"email": "emma@qora.ai", "password": "consumer123"}).json()
    return {"Authorization": "Bearer " + t["access_token"]}


@pytest.fixture()
def sarah(client):
    t = client.post("/api/v1/auth/login", json={"email": "sarah@qora.ai", "password": "provider123"}).json()
    return {"Authorization": "Bearer " + t["access_token"]}
