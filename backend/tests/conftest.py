import os
import fakeredis
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/url_shortener")
os.environ.setdefault("TEST_DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/url_shortener_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.config import settings  # noqa: E402
from app.db import Base  # noqa: E402
import app.models  # noqa: E402,F401  (ensure models are registered on Base)


@pytest.fixture(scope="session")
def test_engine():
    admin_engine = create_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS url_shortener_test"))
        conn.execute(text("CREATE DATABASE url_shortener_test"))
    engine = create_engine(settings.test_database_url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def fake_redis():
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture()
def client(db_session, fake_redis):
    from app.main import app
    from app.db import get_db
    from app.redis_client import get_redis
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: fake_redis
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
