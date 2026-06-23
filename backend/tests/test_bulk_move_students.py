"""Tests for POST /api/v1/modules/{module_id}/students/bulk-move"""
import uuid

import pytest

LOGIN_URL = "/api/v1/auth/login"
MODULES_URL = "/api/v1/modules"


def _auth_headers(client):
    res = client.post(
        LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"}
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _setup_module_with_groups(db, teacher):
    """Create a module with two groups and return (module, group_a, group_b)."""
    from app.models.module import Module
    from app.models.project import Project

    module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Test Module")
    db.add(module)
    db.commit()

    group_a = Project(id=uuid.uuid4(), module_id=module.id, name="Group A")
    group_b = Project(id=uuid.uuid4(), module_id=module.id, name="Group B")
    db.add(group_a)
    db.add(group_b)
    db.commit()
    db.refresh(group_a)
    db.refresh(group_b)
    return module, group_a, group_b


def _add_student(client, headers, module_id, group_id, name, number):
    """Add a student to a module group via the API and return the response body."""
    res = client.post(
        f"{MODULES_URL}/{module_id}/students",
        json={"name": name, "student_number": number, "project_id": str(group_id)},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _bulk_move_url(module_id):
    return f"{MODULES_URL}/{module_id}/students/bulk-move"


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestBulkMoveStudentsSuccess:
    def test_move_single_student(self, client, db, teacher):
        headers = _auth_headers(client)
        module, group_a, group_b = _setup_module_with_groups(db, teacher)

        student = _add_student(
            client, headers, module.id, group_a.id, "Alice Smith", "1001"
        )

        res = client.post(
            _bulk_move_url(module.id),
            json={
                "student_ids": [student["id"]],
                "target_project_id": str(group_b.id),
            },
            headers=headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["moved_count"] == 1
        assert body["skipped_count"] == 0
        assert body["skipped_ids"] == []

    def test_move_multiple_students(self, client, db, teacher):
        headers = _auth_headers(client)
        module, group_a, group_b = _setup_module_with_groups(db, teacher)

        s1 = _add_student(client, headers, module.id, group_a.id, "Alice", "2001")
        s2 = _add_student(client, headers, module.id, group_a.id, "Bob", "2002")
        s3 = _add_student(client, headers, module.id, group_a.id, "Carol", "2003")

        res = client.post(
            _bulk_move_url(module.id),
            json={
                "student_ids": [s1["id"], s2["id"], s3["id"]],
                "target_project_id": str(group_b.id),
            },
            headers=headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["moved_count"] == 3
        assert body["skipped_count"] == 0

    def test_students_appear_in_target_group_after_move(self, client, db, teacher):
        headers = _auth_headers(client)
        module, group_a, group_b = _setup_module_with_groups(db, teacher)

        student = _add_student(
            client, headers, module.id, group_a.id, "Dave", "3001"
        )

        client.post(
            _bulk_move_url(module.id),
            json={
                "student_ids": [student["id"]],
                "target_project_id": str(group_b.id),
            },
            headers=headers,
        )

        # Verify the student is now in group_b
        list_res = client.get(
            f"{MODULES_URL}/{module.id}/students", headers=headers
        )
        assert list_res.status_code == 200
        students = list_res.json()
        moved = next((s for s in students if s["id"] == student["id"]), None)
        assert moved is not None
        assert moved["project_id"] == str(group_b.id)

    def test_students_removed_from_source_group_after_move(self, client, db, teacher):
        headers = _auth_headers(client)
        module, group_a, group_b = _setup_module_with_groups(db, teacher)

        student = _add_student(
            client, headers, module.id, group_a.id, "Eve", "4001"
        )

        client.post(
            _bulk_move_url(module.id),
            json={
                "student_ids": [student["id"]],
                "target_project_id": str(group_b.id),
            },
            headers=headers,
        )

        list_res = client.get(
            f"{MODULES_URL}/{module.id}/students", headers=headers
        )
        students = list_res.json()
        moved = next((s for s in students if s["id"] == student["id"]), None)
        assert moved is not None
        # Must NOT still be in group_a
        assert moved["project_id"] != str(group_a.id)

    def test_duplicate_student_ids_are_deduplicated(self, client, db, teacher):
        headers = _auth_headers(client)
        module, group_a, group_b = _setup_module_with_groups(db, teacher)

        student = _add_student(
            client, headers, module.id, group_a.id, "Frank", "5001"
        )

        # Send the same ID twice
        res = client.post(
            _bulk_move_url(module.id),
            json={
                "student_ids": [student["id"], student["id"]],
                "target_project_id": str(group_b.id),
            },
            headers=headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["moved_count"] == 1

    def test_unknown_student_ids_are_skipped(self, client, db, teacher):
        headers = _auth_headers(client)
        module, group_a, group_b = _setup_module_with_groups(db, teacher)

        student = _add_student(
            client, headers, module.id, group_a.id, "Grace", "6001"
        )

        res = client.post(
            _bulk_move_url(module.id),
            json={
                "student_ids": [student["id"], "9999999"],
                "target_project_id": str(group_b.id),
            },
            headers=headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["moved_count"] == 1
        assert body["skipped_count"] == 1
        assert "9999999" in body["skipped_ids"]


# ---------------------------------------------------------------------------
# Validation & error tests
# ---------------------------------------------------------------------------


class TestBulkMoveStudentsValidation:
    def test_empty_student_ids_returns_422(self, client, db, teacher):
        headers = _auth_headers(client)
        module, group_a, group_b = _setup_module_with_groups(db, teacher)

        res = client.post(
            _bulk_move_url(module.id),
            json={"student_ids": [], "target_project_id": str(group_b.id)},
            headers=headers,
        )
        assert res.status_code == 422

    def test_missing_target_project_id_returns_422(self, client, db, teacher):
        headers = _auth_headers(client)
        module, group_a, _ = _setup_module_with_groups(db, teacher)

        res = client.post(
            _bulk_move_url(module.id),
            json={"student_ids": ["1001"]},
            headers=headers,
        )
        assert res.status_code == 422

    def test_unknown_target_group_returns_404(self, client, db, teacher):
        headers = _auth_headers(client)
        module, group_a, _ = _setup_module_with_groups(db, teacher)

        student = _add_student(
            client, headers, module.id, group_a.id, "Hank", "7001"
        )

        res = client.post(
            _bulk_move_url(module.id),
            json={
                "student_ids": [student["id"]],
                "target_project_id": str(uuid.uuid4()),
            },
            headers=headers,
        )
        assert res.status_code == 404

    def test_all_unknown_student_ids_returns_400(self, client, db, teacher):
        headers = _auth_headers(client)
        module, group_a, group_b = _setup_module_with_groups(db, teacher)

        res = client.post(
            _bulk_move_url(module.id),
            json={
                "student_ids": ["9999991", "9999992"],
                "target_project_id": str(group_b.id),
            },
            headers=headers,
        )
        assert res.status_code == 400

    def test_unknown_module_returns_404(self, client, db, teacher):
        headers = _auth_headers(client)

        res = client.post(
            _bulk_move_url(uuid.uuid4()),
            json={
                "student_ids": ["1001"],
                "target_project_id": str(uuid.uuid4()),
            },
            headers=headers,
        )
        assert res.status_code == 404

    def test_exceeding_100_students_returns_422(self, client, db, teacher):
        headers = _auth_headers(client)
        module, _, group_b = _setup_module_with_groups(db, teacher)

        res = client.post(
            _bulk_move_url(module.id),
            json={
                "student_ids": [str(i) for i in range(101)],
                "target_project_id": str(group_b.id),
            },
            headers=headers,
        )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# Permission / authorization tests
# ---------------------------------------------------------------------------


class TestBulkMoveStudentsPermissions:
    def test_unauthenticated_request_returns_401(self, client, db, teacher):
        module, _, group_b = _setup_module_with_groups(db, teacher)

        res = client.post(
            _bulk_move_url(module.id),
            json={
                "student_ids": ["1001"],
                "target_project_id": str(group_b.id),
            },
        )
        assert res.status_code == 401

    def test_other_teachers_module_returns_404(self, client, db, teacher):
        """A teacher cannot bulk-move students in another teacher's module."""
        from app.core.security import hash_password
        from app.models.module import Module
        from app.models.project import Project
        from app.models.teacher import Teacher

        other = Teacher(
            id=uuid.uuid4(),
            name="Other Teacher",
            email="other2@test.com",
            password_hash=hash_password("password123"),
        )
        db.add(other)
        db.commit()

        other_module = Module(
            id=uuid.uuid4(), teacher_id=other.id, name="Other Module"
        )
        db.add(other_module)
        db.commit()

        other_group = Project(
            id=uuid.uuid4(), module_id=other_module.id, name="Other Group"
        )
        db.add(other_group)
        db.commit()

        # Log in as the fixture teacher (not the owner)
        headers = _auth_headers(client)

        res = client.post(
            _bulk_move_url(other_module.id),
            json={
                "student_ids": ["1001"],
                "target_project_id": str(other_group.id),
            },
            headers=headers,
        )
        # Must look like the module doesn't exist (404, not 403)
        assert res.status_code == 404

    def test_target_group_from_different_module_returns_404(
        self, client, db, teacher
    ):
        """Target group must belong to the same module."""
        from app.models.module import Module
        from app.models.project import Project

        module, group_a, _ = _setup_module_with_groups(db, teacher)

        # Create a second module with its own group
        other_module = Module(
            id=uuid.uuid4(), teacher_id=teacher.id, name="Other Module 2"
        )
        db.add(other_module)
        db.commit()
        foreign_group = Project(
            id=uuid.uuid4(), module_id=other_module.id, name="Foreign Group"
        )
        db.add(foreign_group)
        db.commit()

        student = _add_student(
            client, _auth_headers(client), module.id, group_a.id, "Ivy", "8001"
        )

        res = client.post(
            _bulk_move_url(module.id),
            json={
                "student_ids": [student["id"]],
                "target_project_id": str(foreign_group.id),
            },
            headers=_auth_headers(client),
        )
