import uuid
from pathlib import Path

import pytest

from app.core.security import hash_password

LOGIN_URL = "/api/v1/auth/login"
MODULES_URL = "/api/v1/modules"
_EMAIL = "rubrics_teacher@test.com"
_PW = "password123"


@pytest.fixture
def rubrics_teacher(db):
    from app.models.teacher import Teacher

    existing = db.query(Teacher).filter(Teacher.email == _EMAIL).first()
    if existing:
        yield existing
        return
    t = Teacher(
        id=uuid.uuid4(),
        name="Rubrics Teacher",
        email=_EMAIL,
        password_hash=hash_password(_PW),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    yield t


def _auth(client):
    res = client.post(LOGIN_URL, json={"email": _EMAIL, "password": _PW})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _module(client, headers):
    res = client.post(
        MODULES_URL,
        json={"name": "Rubric Module", "academic_year": "2024-2025"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add(client, headers, mid, fname, name, weight):
    files = {"file": (fname, b"%PDF-1.4 fake pdf", "application/pdf")}
    return client.post(
        f"{MODULES_URL}/{mid}/rubrics",
        params={"name": name, "weight": weight},
        files=files,
        headers=headers,
    )


class TestModuleRubrics:
    def test_add_list_update_delete(
        self, client, rubrics_teacher, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.module_service.RUBRIC_UPLOAD_DIR",
            Path(tmp_path) / "rubrics",
        )
        headers = _auth(client)
        mid = _module(client, headers)

        r1 = _add(client, headers, mid, "report.pdf", "Report", 0.6)
        assert r1.status_code == 201, r1.text
        r2 = _add(client, headers, mid, "reflection.pdf", "Reflection", 0.4)
        assert r2.status_code == 201, r2.text

        listed = client.get(f"{MODULES_URL}/{mid}/rubrics", headers=headers)
        assert listed.status_code == 200, listed.text
        body = listed.json()
        assert len(body) == 2
        assert {b["name"] for b in body} == {"Report", "Reflection"}
        assert [b["position"] for b in body] == [0, 1]
        assert {b["weight"] for b in body} == {0.6, 0.4}

        rid = body[0]["id"]
        upd = client.patch(
            f"{MODULES_URL}/{mid}/rubrics/{rid}",
            json={"weight": 0.7},
            headers=headers,
        )
        assert upd.status_code == 200, upd.text
        assert upd.json()["weight"] == 0.7

        gone = client.delete(
            f"{MODULES_URL}/{mid}/rubrics/{rid}", headers=headers
        )
        assert gone.status_code == 204, gone.text

        remaining = client.get(
            f"{MODULES_URL}/{mid}/rubrics", headers=headers
        ).json()
        assert len(remaining) == 1
        assert remaining[0]["name"] == "Reflection"

    def test_rubric_not_found_returns_404(
        self, client, rubrics_teacher, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(
            "app.services.module_service.RUBRIC_UPLOAD_DIR",
            Path(tmp_path) / "rubrics",
        )
        headers = _auth(client)
        mid = _module(client, headers)
        res = client.delete(
            f"{MODULES_URL}/{mid}/rubrics/{uuid.uuid4()}", headers=headers
        )
        assert res.status_code == 404
