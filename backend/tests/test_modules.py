"""
Tests for module rename (PATCH /modules/{id}) and delete (DELETE /modules/{id}).
"""

import uuid

import pytest

LOGIN_URL = "/api/v1/auth/login"
MODULES_URL = "/api/v1/modules"

_TEACHER_EMAIL = "modules_teacher@test.com"
_TEACHER_PASSWORD = "password123"


# ---------------------------------------------------------------------------
# Module-local teacher fixture (avoids email collision with other test files)
# ---------------------------------------------------------------------------

@pytest.fixture
def modules_teacher(db):
    """Get-or-create a teacher used exclusively by this test module.

    The teacher is intentionally NOT deleted in teardown: the session-scoped
    SQLite DB is dropped at the end of the test session anyway, and deleting
    the teacher would cascade-null the teacher_id FK on any modules created
    during the test (violating the NOT NULL constraint).
    """
    from app.models.teacher import Teacher
    from app.core.security import hash_password

    existing = db.query(Teacher).filter(Teacher.email == _TEACHER_EMAIL).first()
    if existing:
        yield existing
        return

    t = Teacher(
        id=uuid.uuid4(),
        name="Modules Teacher",
        email=_TEACHER_EMAIL,
        password_hash=hash_password(_TEACHER_PASSWORD),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    yield t
    # No teardown delete — session-scoped DB is dropped after all tests finish.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client):
    res = client.post(LOGIN_URL, json={"email": _TEACHER_EMAIL, "password": _TEACHER_PASSWORD})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth(client):
    return {"Authorization": f"Bearer {_login(client)}"}


def _create_module(client, headers, name="Test Module", academic_year="2024-2025"):
    res = client.post(
        MODULES_URL,
        json={"name": name, "academic_year": academic_year},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# PATCH /modules/{module_id} — rename
# ---------------------------------------------------------------------------

class TestRenameModule:
    def test_rename_updates_name(self, client, modules_teacher):
        headers = _auth(client)
        module = _create_module(client, headers)

        res = client.patch(
            f"{MODULES_URL}/{module['id']}",
            json={"name": "Renamed Module"},
            headers=headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["name"] == "Renamed Module"
        assert body["id"] == module["id"]

    def test_rename_preserves_academic_year(self, client, modules_teacher):
        headers = _auth(client)
        module = _create_module(client, headers, academic_year="2023-2024")

        res = client.patch(
            f"{MODULES_URL}/{module['id']}",
            json={"name": "New Name"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["academic_year"] == "2023-2024"

    def test_rename_can_also_update_academic_year(self, client, modules_teacher):
        headers = _auth(client)
        module = _create_module(client, headers, academic_year="2023-2024")

        res = client.patch(
            f"{MODULES_URL}/{module['id']}",
            json={"name": "Updated", "academic_year": "2025-2026"},
            headers=headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["name"] == "Updated"
        assert body["academic_year"] == "2025-2026"

    def test_rename_empty_name_returns_422(self, client, modules_teacher):
        headers = _auth(client)
        module = _create_module(client, headers)

        res = client.patch(
            f"{MODULES_URL}/{module['id']}",
            json={"name": "   "},
            headers=headers,
        )
        assert res.status_code == 422

    def test_rename_missing_name_returns_422(self, client, modules_teacher):
        headers = _auth(client)
        module = _create_module(client, headers)

        res = client.patch(
            f"{MODULES_URL}/{module['id']}",
            json={},
            headers=headers,
        )
        assert res.status_code == 422

    def test_rename_nonexistent_module_returns_404(self, client, modules_teacher):
        headers = _auth(client)
        fake_id = str(uuid.uuid4())

        res = client.patch(
            f"{MODULES_URL}/{fake_id}",
            json={"name": "Ghost"},
            headers=headers,
        )
        assert res.status_code == 404

    def test_rename_other_teachers_module_returns_404(self, client, modules_teacher, db):
        """A teacher cannot rename a module they don't own."""
        from app.models.module import Module
        from app.core.security import hash_password
        from app.models.teacher import Teacher

        other_email = f"other_rename_{uuid.uuid4().hex[:8]}@test.com"
        other = Teacher(
            id=uuid.uuid4(),
            name="Other Teacher",
            email=other_email,
            password_hash=hash_password("password123"),
        )
        db.add(other)
        db.commit()

        other_module = Module(
            id=uuid.uuid4(),
            teacher_id=other.id,
            name="Other's Module",
        )
        db.add(other_module)
        db.commit()

        # Log in as the modules teacher and try to rename the other's module
        headers = _auth(client)
        res = client.patch(
            f"{MODULES_URL}/{other_module.id}",
            json={"name": "Stolen Name"},
            headers=headers,
        )
        assert res.status_code == 404

        db.delete(other_module)
        db.delete(other)
        db.commit()

    def test_rename_without_auth_returns_401(self, client, modules_teacher):
        headers = _auth(client)
        module = _create_module(client, headers)

        res = client.patch(
            f"{MODULES_URL}/{module['id']}",
            json={"name": "No Auth"},
        )
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /modules/{module_id}
# ---------------------------------------------------------------------------

class TestDeleteModule:
    def test_delete_returns_204(self, client, modules_teacher):
        headers = _auth(client)
        module = _create_module(client, headers, name="To Delete")

        res = client.delete(f"{MODULES_URL}/{module['id']}", headers=headers)
        assert res.status_code == 204

    def test_deleted_module_no_longer_in_list(self, client, modules_teacher):
        headers = _auth(client)
        module = _create_module(client, headers, name="Will Be Gone")

        client.delete(f"{MODULES_URL}/{module['id']}", headers=headers)

        list_res = client.get(MODULES_URL, headers=headers)
        assert list_res.status_code == 200
        ids = [m["id"] for m in list_res.json()]
        assert module["id"] not in ids

    def test_delete_nonexistent_module_returns_404(self, client, modules_teacher):
        headers = _auth(client)
        fake_id = str(uuid.uuid4())

        res = client.delete(f"{MODULES_URL}/{fake_id}", headers=headers)
        assert res.status_code == 404

    def test_delete_other_teachers_module_returns_404(self, client, modules_teacher, db):
        """A teacher cannot delete a module they don't own."""
        from app.models.module import Module
        from app.core.security import hash_password
        from app.models.teacher import Teacher

        other_email = f"other_delete_{uuid.uuid4().hex[:8]}@test.com"
        other = Teacher(
            id=uuid.uuid4(),
            name="Other Teacher 2",
            email=other_email,
            password_hash=hash_password("password123"),
        )
        db.add(other)
        db.commit()

        other_module = Module(
            id=uuid.uuid4(),
            teacher_id=other.id,
            name="Other's Module 2",
        )
        db.add(other_module)
        db.commit()

        headers = _auth(client)
        res = client.delete(f"{MODULES_URL}/{other_module.id}", headers=headers)
        assert res.status_code == 404

        db.delete(other_module)
        db.delete(other)
        db.commit()

    def test_delete_without_auth_returns_401(self, client, modules_teacher):
        headers = _auth(client)
        module = _create_module(client, headers, name="Auth Required")

        res = client.delete(f"{MODULES_URL}/{module['id']}")
        assert res.status_code == 401

    def test_get_after_delete_returns_404(self, client, modules_teacher):
        headers = _auth(client)
        module = _create_module(client, headers, name="Check After Delete")

        client.delete(f"{MODULES_URL}/{module['id']}", headers=headers)

        get_res = client.get(f"{MODULES_URL}/{module['id']}", headers=headers)
        assert get_res.status_code == 404
