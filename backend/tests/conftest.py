import uuid as _uuid_mod

# ── Patch PostgreSQL-specific types before any app model is imported ──────────
# SQLite can't render UUID, JSONB, or INET. We swap them for generic SQLAlchemy
# types so the in-memory test database works without touching production code.
import sqlalchemy.dialects.postgresql as _pg
from sqlalchemy import JSON, String, Text, TypeDecorator


class _SQLiteUUID(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return _uuid_mod.UUID(str(value)) if value is not None else None


_pg.UUID = lambda as_uuid=True: _SQLiteUUID()  # used as UUID(as_uuid=True)
_pg.JSONB = JSON    # used as bare class: Column(JSONB, ...) — JSON binds dicts on SQLite
_pg.INET = String   # used as bare class: Column(INET, ...)

# ── App imports (models now see the patched UUID) ─────────────────────────────
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base
from app.main import app
from app.api.deps import get_db
from app.core.security import hash_password

# ── In-memory SQLite engine ───────────────────────────────────────────────────
_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


# ── Fixtures ──────────────────────────────────────────────────────────────────

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
