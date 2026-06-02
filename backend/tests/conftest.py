import uuid as _uuid_mod

# Patch PostgreSQL-specific types before app models import (SQLite in-memory tests).
import sqlalchemy.dialects.postgresql as _pg
from sqlalchemy import String, Text, TypeDecorator


class _SQLiteUUID(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return _uuid_mod.UUID(str(value)) if value is not None else None


_pg.UUID = lambda as_uuid=True: _SQLiteUUID()
_pg.JSONB = Text
_pg.INET = String

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(scope="session", autouse=True)
def _tables():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def db(_tables):
    session = _Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def teacher(db):
    from app.models.teacher import Teacher

    t = Teacher(
        id=_uuid_mod.uuid4(),
        name="Test Teacher",
        email="teacher@test.com",
        password_hash=hash_password("password123"),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    yield t
    db.delete(t)
    db.commit()
