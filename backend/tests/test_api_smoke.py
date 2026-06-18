"""Post-merge API smoke checks — exercises major route groups via TestClient."""
from __future__ import annotations

import uuid

import pytest

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
MODULES = "/api/v1/modules"
HEALTH = "/api/v1/health"


@pytest.fixture
def auth(client, teacher):
    res = client.post(
        LOGIN, json={"email": "teacher@test.com", "password": "password123"}
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get(ME, headers=headers)
    assert me.status_code == 200
    return headers


class TestApiSmoke:
    def test_health_and_ollama_probe(self, client):
        assert client.get(f"{HEALTH}/").status_code == 200
        # Ollama may be offline locally; endpoint should still respond structurally.
        res = client.get(f"{HEALTH}/ollama")
        assert res.status_code == 200
        body = res.json()
        assert "service" in body

    def test_module_lifecycle_and_overlap_routes(self, client, db, teacher, auth, monkeypatch):
        from app.models.module import Module
        from app.models.project import Project
        from app.models.student import Student
        from app.services.overlap_service import OverlapService

        module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Smoke Module")
        db.add(module)
        db.commit()

        group = Project(id=uuid.uuid4(), module_id=module.id, name="Smoke Group")
        db.add(group)
        db.commit()

        alice = Student(name="Smoke Alice", student_number="9009001")
        bob = Student(name="Smoke Bob", student_number="9009002")
        db.add(alice)
        db.add(bob)
        db.flush()
        alice.projects.append(group)
        bob.projects.append(group)
        db.commit()

        module_id = str(module.id)

        listed = client.get(MODULES, headers=auth)
        assert listed.status_code == 200
        assert any(m["id"] == module_id for m in listed.json())

        warning = client.get(f"{MODULES}/{module_id}/overlap/warning", headers=auth)
        assert warning.status_code == 200
        assert warning.json()["has_overlap"] is False

        monkeypatch.setattr(
            OverlapService,
            "_generate_ollama_warning",
            staticmethod(lambda _prompt: "Smoke overlap warning."),
        )
        monkeypatch.setattr(
            "app.services.overlap_service.enrich_hit_with_ai",
            lambda hit, **kwargs: None,
        )
        analyze = client.post(f"{MODULES}/{module_id}/overlap/analyze", headers=auth)
        assert analyze.status_code == 200
        assert "warning" in analyze.json()

        signals = client.get(f"{MODULES}/{module_id}/overlap/signals", headers=auth)
        assert signals.status_code == 200
        assert isinstance(signals.json(), list)

    def test_evidence_supported_types_and_auth_pin_flow(self, client, teacher, auth):
        types_res = client.get("/api/v1/evidence/supported-types")
        assert types_res.status_code == 200
        extensions = types_res.json()["supported_extensions"]
        for ext in (".md", ".pdf", ".docx", ".xlsx", ".png"):
            assert ext in extensions

        pin_res = client.post(
            "/api/v1/auth/pin",
            headers=auth,
            json={"password": "password123", "pin": "1234"},
        )
        assert pin_res.status_code == 200

        login = client.post(
            LOGIN,
            json={"email": "teacher@test.com", "password": "password123", "pin": "1234"},
        )
        assert login.status_code == 200
        assert "access_token" in login.json()

        client.request(
            "DELETE",
            "/api/v1/auth/pin",
            headers=auth,
            json={"password": "password123"},
        )

    def test_github_and_evidence_match_routes_importable(self, client, auth):
        # Route registration smoke — 404/422 is fine; 500 means broken imports/handlers.
        bogus_student = "9999999"
        match_run = client.post(
            f"/api/v1/students/{bogus_student}/evidence-matches/run",
            headers=auth,
            json={"module_id": str(uuid.uuid4()), "mode": "fast"},
        )
        assert match_run.status_code in (404, 422)

        github = client.get(
            "/api/v1/github/verify?url=https://github.com/octocat/Hello-World",
            headers=auth,
        )
        assert github.status_code in (200, 400, 405, 422, 502)
