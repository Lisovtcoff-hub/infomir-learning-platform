from __future__ import annotations

import os
from pathlib import Path
import tempfile


TEST_DIR = Path(tempfile.mkdtemp(prefix="infomir-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DIR / 'test.sqlite3'}"
os.environ["APP_ENV"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-key-only-for-the-automated-suite"
os.environ["ALLOWED_HOSTS"] = "testserver,localhost,127.0.0.1"
os.environ["ADMIN_HOSTS"] = "admin.localhost"

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    config = Config("backend/alembic.ini")
    command.upgrade(config, "head")
    from backend.app.db.seed import run_seed

    run_seed()
    return TEST_DIR


@pytest.fixture()
def public_client(migrated_database):
    from backend.app.main import app

    with TestClient(app, base_url="http://testserver") as client:
        yield client


@pytest.fixture()
def admin_client(migrated_database):
    from backend.app.main import app

    with TestClient(app, base_url="http://admin.localhost") as client:
        yield client
