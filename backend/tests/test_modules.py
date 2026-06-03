import uuid

from app.core.security import hash_password

LOGIN_URL = "/api/v1/auth/login"
MODULES_URL = "/api/v1/modules"


def _login(client, email: str, password: str) -> dict:
    res = client.post(LOGIN_URL, json={"email": email, "password": password})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_upload_and_delete_rubric_for_other_teachers_module(client, db, teacher):
    from app.models.file_record import FileRecord
    from app.models.module import Module
    from app.models.teacher import Teacher

    admin = Teacher(
        id=uuid.uuid4(),
        name="Admin Teacher",
        email="admin@test.com",
        password_hash=hash_password("password123"),
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Owned by non-admin")
    db.add(module)
    db.commit()
    db.refresh(module)

    try:
        headers = _login(client, "admin@test.com", "password123")

        upload = client.post(
            f"{MODULES_URL}/{module.id}/rubric",
            files={"file": ("rubric.pdf", b"%PDF-1.4 test rubric", "application/pdf")},
            headers=headers,
        )
        assert upload.status_code == 200
        body = upload.json()
        assert body["id"] == str(module.id)
        assert body["rubric_file"] is not None
        assert body["rubric_file"]["file_name"] == "rubric.pdf"

        remove = client.delete(f"{MODULES_URL}/{module.id}/rubric", headers=headers)
        assert remove.status_code == 204

        db.refresh(module)
        assert module.rubric_file_id is None
        assert db.query(FileRecord).count() == 0
    finally:
        db.query(FileRecord).delete()
        db.query(Module).filter(Module.id == module.id).delete()
        db.query(Teacher).filter(Teacher.id == admin.id).delete()
        db.commit()
