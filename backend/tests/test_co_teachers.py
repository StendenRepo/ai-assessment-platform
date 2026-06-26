"""Tests for the module co-teachers feature.

Covers:
- GET  /modules/{module_id}/co-teachers  — list co-teachers
- POST /modules/{module_id}/co-teachers  — add co-teacher by email
- DELETE /modules/{module_id}/co-teachers/{teacher_id}  — remove co-teacher
- Permission: only module owner (or admin) can add/remove
- Co-teacher can view the module (visibility check)
- Validation: duplicate, owner-as-co-teacher, unknown email
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.module import Module
from app.models.teacher import Teacher
from app.models.enums import ModuleStatus
from app.core.security import create_access_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_teacher(db: Session, *, name: str, email: str) -> Teacher:
    teacher = Teacher(
        id=uuid.uuid4(),
        name=name,
        email=email,
        password_hash="x",
    )
    db.add(teacher)
    db.flush()
    return teacher


def _make_module(db: Session, *, teacher: Teacher, name: str = "Test Module") -> Module:
    module = Module(
        id=uuid.uuid4(),
        teacher_id=teacher.id,
        name=name,
        status=ModuleStatus.active,
    )
    db.add(module)
    db.flush()
    return module


def _auth(teacher: Teacher) -> dict:
    token = create_access_token(str(teacher.id))
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def owner_and_module(db: Session):
    owner = _make_teacher(db, name="Owner", email="owner@test.com")
    module = _make_module(db, teacher=owner)
    db.commit()
    return owner, module


@pytest.fixture()
def other_teacher(db: Session):
    teacher = _make_teacher(db, name="Other", email="other@test.com")
    db.commit()
    return teacher


@pytest.fixture()
def third_teacher(db: Session):
    teacher = _make_teacher(db, name="Third", email="third@test.com")
    db.commit()
    return teacher


# ---------------------------------------------------------------------------
# List co-teachers
# ---------------------------------------------------------------------------


def test_list_co_teachers_empty(client, db, owner_and_module):
    owner, module = owner_and_module
    resp = client.get(
        f"/api/v1/modules/{module.id}/co-teachers",
        headers=_auth(owner),
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_co_teachers_unauthenticated(client, db, owner_and_module):
    _, module = owner_and_module
    resp = client.get(f"/api/v1/modules/{module.id}/co-teachers")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Add co-teacher
# ---------------------------------------------------------------------------


def test_add_co_teacher_success(client, db, owner_and_module, other_teacher):
    owner, module = owner_and_module
    resp = client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": other_teacher.email},
        headers=_auth(owner),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == other_teacher.email
    assert data["name"] == other_teacher.name
    assert "id" in data


def test_add_co_teacher_appears_in_list(client, db, owner_and_module, other_teacher):
    owner, module = owner_and_module
    client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": other_teacher.email},
        headers=_auth(owner),
    )
    resp = client.get(
        f"/api/v1/modules/{module.id}/co-teachers",
        headers=_auth(owner),
    )
    assert resp.status_code == 200
    emails = [t["email"] for t in resp.json()]
    assert other_teacher.email in emails


def test_add_co_teacher_unknown_email(client, db, owner_and_module):
    owner, module = owner_and_module
    resp = client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": "nobody@nowhere.com"},
        headers=_auth(owner),
    )
    assert resp.status_code == 404


def test_add_co_teacher_owner_as_co_teacher(client, db, owner_and_module):
    owner, module = owner_and_module
    resp = client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": owner.email},
        headers=_auth(owner),
    )
    assert resp.status_code == 400


def test_add_co_teacher_duplicate(client, db, owner_and_module, other_teacher):
    owner, module = owner_and_module
    client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": other_teacher.email},
        headers=_auth(owner),
    )
    resp = client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": other_teacher.email},
        headers=_auth(owner),
    )
    assert resp.status_code == 409


def test_add_co_teacher_forbidden_for_co_teacher(
    client, db, owner_and_module, other_teacher, third_teacher
):
    """A co-teacher cannot add further co-teachers."""
    owner, module = owner_and_module
    # First make other_teacher a co-teacher
    client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": other_teacher.email},
        headers=_auth(owner),
    )
    # Now other_teacher tries to add third_teacher
    resp = client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": third_teacher.email},
        headers=_auth(other_teacher),
    )
    assert resp.status_code == 403


def test_add_co_teacher_forbidden_for_unrelated_teacher(
    client, db, owner_and_module, other_teacher
):
    _, module = owner_and_module
    resp = client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": other_teacher.email},
        headers=_auth(other_teacher),
    )
    # other_teacher cannot see the module at all → 404
    assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# Remove co-teacher
# ---------------------------------------------------------------------------


def test_remove_co_teacher_success(client, db, owner_and_module, other_teacher):
    owner, module = owner_and_module
    add_resp = client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": other_teacher.email},
        headers=_auth(owner),
    )
    teacher_id = add_resp.json()["id"]

    resp = client.delete(
        f"/api/v1/modules/{module.id}/co-teachers/{teacher_id}",
        headers=_auth(owner),
    )
    assert resp.status_code == 204

    # Verify removed
    list_resp = client.get(
        f"/api/v1/modules/{module.id}/co-teachers",
        headers=_auth(owner),
    )
    assert all(t["id"] != teacher_id for t in list_resp.json())


def test_remove_co_teacher_not_found(client, db, owner_and_module):
    owner, module = owner_and_module
    resp = client.delete(
        f"/api/v1/modules/{module.id}/co-teachers/{uuid.uuid4()}",
        headers=_auth(owner),
    )
    assert resp.status_code == 404


def test_remove_co_teacher_forbidden_for_co_teacher(
    client, db, owner_and_module, other_teacher, third_teacher
):
    """A co-teacher cannot remove other co-teachers."""
    owner, module = owner_and_module
    # Add both as co-teachers
    client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": other_teacher.email},
        headers=_auth(owner),
    )
    add_resp = client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": third_teacher.email},
        headers=_auth(owner),
    )
    third_id = add_resp.json()["id"]

    resp = client.delete(
        f"/api/v1/modules/{module.id}/co-teachers/{third_id}",
        headers=_auth(other_teacher),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Co-teacher visibility
# ---------------------------------------------------------------------------


def test_co_teacher_can_view_module(client, db, owner_and_module, other_teacher):
    """After being added as co-teacher, the teacher can GET the module."""
    owner, module = owner_and_module
    client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": other_teacher.email},
        headers=_auth(owner),
    )
    resp = client.get(
        f"/api/v1/modules/{module.id}",
        headers=_auth(other_teacher),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(module.id)


def test_co_teacher_appears_in_module_list(client, db, owner_and_module, other_teacher):
    """The module appears in the co-teacher's module list."""
    owner, module = owner_and_module
    client.post(
        f"/api/v1/modules/{module.id}/co-teachers",
        json={"email": other_teacher.email},
        headers=_auth(owner),
    )
    resp = client.get("/api/v1/modules", headers=_auth(other_teacher))
    assert resp.status_code == 200
    ids = [m["id"] for m in resp.json()]
    assert str(module.id) in ids


def test_non_co_teacher_cannot_view_module(client, db, owner_and_module, other_teacher):
    """A teacher who is NOT a co-teacher cannot see the module."""
    _, module = owner_and_module
    resp = client.get(
        f"/api/v1/modules/{module.id}",
        headers=_auth(other_teacher),
    )
    assert resp.status_code == 404
