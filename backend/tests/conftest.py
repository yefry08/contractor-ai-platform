"""Test setup. Critically: this points the app at an isolated, throwaway
SQLite file BEFORE any `app.*` module is imported, so the test suite can
never accidentally hit the real database configured in backend/.env
(production Postgres, see app/config.py) -- pydantic-settings prioritizes
real environment variables over the .env file, so setting DATABASE_URL here
first is what makes that safe."""

import os
import tempfile
from pathlib import Path

TEST_DB_PATH = Path(tempfile.gettempdir()) / "contractor_ai_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
# Same reasoning as DATABASE_URL above: never let the test suite pick up a
# real BazaarLink key from backend/.env and make real network calls against
# a shared, global free-tier quota. Tests that need "available" behavior
# monkeypatch app.ai.settings.bazaarlink_api_key explicitly instead.
os.environ["BAZAARLINK_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402, F401  (import so its table is registered on Base.metadata)
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _fresh_test_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    Base.metadata.create_all(engine)
    yield
    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Every test starts from an empty database -- simplest way to keep
    tests independent of each other and of insertion order."""
    yield
    session = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """app.main's in-memory rate limiter is module-level state keyed by
    client IP -- and Starlette's TestClient always reports the same fake IP,
    so without this every test sharing an endpoint's rate-limit bucket would
    silently count hits left over from whichever test ran before it."""
    from app import main

    main._rate_hits.clear()
    yield
    main._rate_hits.clear()


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


def make_country(session, code="PY", name="Paraguay"):
    country = models.Country(code=code, name=name)
    session.add(country)
    session.flush()
    return country


def make_buyer(session, country_code="PY", name="Municipalidad de Prueba"):
    buyer = models.Buyer(country_code=country_code, name=name, normalized_name=name.lower())
    session.add(buyer)
    session.flush()
    return buyer


def make_contract(session, **overrides):
    defaults = dict(
        country_code="PY",
        currency="PYG",
        amount_original=1_000_000.0,
        category_code="services",
        title="Contrato de prueba",
    )
    defaults.update(overrides)
    contract = models.Contract(**defaults)
    session.add(contract)
    session.flush()
    return contract
