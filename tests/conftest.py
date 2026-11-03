from __future__ import annotations

import os
import tempfile
from pathlib import Path

TEST_DIR = Path(tempfile.mkdtemp(prefix="survey-builder-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DIR / 'test.db'}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DEMO_EMAIL"] = "demo@example.com"
os.environ["DEMO_PASSWORD"] = "demo12345"

import pytest
from fastapi.testclient import TestClient

from database.db import Base, engine
from main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
