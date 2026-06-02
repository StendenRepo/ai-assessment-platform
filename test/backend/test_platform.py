import json
import time

import pytest

from app.ai import ollama_client

PROJECT = "proj-1"
GROUP = "group-1"
STUDENT_A = "student-1"
STUDENT_B = "student-2"


@pytest.fixture
def platform_store(tmp_path, monkeypatch):
    import app.api.v1.endpoints.modules as modules_api
    import app.api.v1.endpoints.platform as platform_api
    import app.audit as audit_mod
    import app.store as store_mod

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    store_file = data_dir / "platform_store.json"
    store_file.write_text(
        json.dumps(
            {
                "modules": [],
                "audit_log": [],
                "chat_history": [],
                "current_teacher": "",
                "evidence_content": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(store_mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(store_mod, "STORE_FILE", store_file)
    fresh = store_mod.PlatformStore()
    for mod in (store_mod, modules_api, platform_api, audit_mod):
        monkeypatch.setattr(mod, "store", fresh)
    return fresh


def _wait_for_analysis(client, project: str, group: str, timeout: float = 90.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = client.get(f"/api/v1/modules/{project}/projects/{group}/analyze/status")
        assert res.status_code == 200
        body = res.json()
        if body.get("status") == "completed":
            return body
        if body.get("status") == "failed":
            pytest.fail(body.get("error") or "analysis failed")
        time.sleep(0.2)
    pytest.fail("analysis timed out")


class TestPlatformRoutes:
    def test_llm_status(self, client):
        res = client.get("/api/v1/llm-status")
        assert res.status_code == 200
        body = res.json()
        assert body["model"] == ollama_client.OLLAMA_MODEL
        assert "ready" in body

    def test_empty_modules_list(self, client, platform_store):
        assert platform_store.modules == {}
        assert client.get("/api/v1/modules").json() == []

    def test_seed_demo(self, client, platform_store):
        res = client.post("/api/v1/seed-demo")
        assert res.status_code == 200
        assert res.json()["ok"] is True
        assert platform_store.modules

    def test_create_module_and_project(self, client, platform_store):
        mod = client.post(
            "/api/v1/modules",
            json={"name": "Test Module", "academic_year": "2025-2026"},
        )
        module_id = mod.json()["id"]
        proj = client.post(
            f"/api/v1/modules/{module_id}/projects",
            json={"name": "Group A"},
        )
        assert proj.status_code == 200


class TestDevBridge:
    def test_ensure_fixture_students(self, client, platform_store):
        res = client.post(f"/api/v1/modules/{PROJECT}/projects/{GROUP}/ensure")
        assert res.status_code == 200
        body = res.json()
        ids = {s["id"] for s in body["students"]}
        assert {STUDENT_A, STUDENT_B} <= ids
        student = platform_store._find_student(PROJECT, GROUP, STUDENT_A)
        assert student and student.evidence

    def test_analyze_and_insights(self, client, platform_store):
        assert (
            client.post(f"/api/v1/modules/{PROJECT}/projects/{GROUP}/ensure").status_code
            == 200
        )
        start = client.post(f"/api/v1/modules/{PROJECT}/projects/{GROUP}/analyze")
        assert start.json()["status"] == "started"
        assert _wait_for_analysis(client, PROJECT, GROUP)["status"] == "completed"

        for sid in (STUDENT_A, STUDENT_B):
            s = platform_store._find_student(PROJECT, GROUP, sid)
            assert s.analysis and "overlaps" in s.analysis
            for d in s.analysis.get("draft_suggestions", []):
                assert d.get("student") == s.name
            other = STUDENT_B if sid == STUDENT_A else STUDENT_A
            other_s = platform_store._find_student(PROJECT, GROUP, other)
            other_drafts = other_s.analysis.get("draft_suggestions", [])
            assert all(d.get("student") == other_s.name for d in other_drafts)

        insights = client.get(
            f"/api/v1/modules/{PROJECT}/projects/{GROUP}/students/{STUDENT_A}/ai-insights"
        )
        data = insights.json()
        assert data["student_id"] == STUDENT_A
        assert len(data["insights"]) >= 1

    def test_analyze_rejects_empty_group(self, client, platform_store):
        import app.store as store_mod

        mod = store_mod.Module(
            id="empty-mod",
            name="Empty",
            academic_year="2025",
            criteria=[],
        )
        mod.projects.append(
            store_mod.Project(id="empty-group", name="Empty", students=[])
        )
        platform_store.modules["empty-mod"] = mod
        platform_store.save()
        res = client.post("/api/v1/modules/empty-mod/projects/empty-group/analyze")
        assert res.status_code == 400


class TestChunker:
    def test_rejects_invalid_overlap(self):
        import pytest
        from app.ai.chunker import chunk_text

        with pytest.raises(ValueError):
            chunk_text("hello world", chunk_size=10, overlap=10)


class TestAuthWithPlatform:
    def test_jwt_login_unaffected(self, client, teacher):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "teacher@test.com", "password": "password123"},
        )
        assert res.status_code == 200
        assert "access_token" in res.json()
