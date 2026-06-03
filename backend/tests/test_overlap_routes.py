import uuid

from app.models.enums import FileType, SourceType

LOGIN_URL = "/api/v1/auth/login"
MODULES_URL = "/api/v1/modules"


def _auth_headers(client):
    res = client.post(
        LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"}
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _seed_module_with_overlap(db, teacher):
    from app.models.evidence import Evidence
    from app.models.module import Module
    from app.models.project import Project
    from app.models.student import Student

    module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Overlap Module")
    db.add(module)
    db.commit()

    group_a = Project(id=uuid.uuid4(), module_id=module.id, name="Group A")
    group_b = Project(id=uuid.uuid4(), module_id=module.id, name="Group B")
    db.add(group_a)
    db.add(group_b)
    db.commit()

    alice = Student(
        id=uuid.uuid4(),
        project_id=group_a.id,
        name="Alice",
        student_number="S-ALICE",
    )
    bob = Student(
        id=uuid.uuid4(),
        project_id=group_b.id,
        name="Bob",
        student_number="S-BOB",
    )
    db.add(alice)
    db.add(bob)
    db.commit()

    # Same file name across students should trigger a high-confidence textual signal.
    ev_a = Evidence(
        id=uuid.uuid4(),
        student_id=alice.id,
        file_name="Architecture_Report.pdf",
        file_type=FileType.pdf,
        file_path="/tmp/alice-architecture-report.pdf",
        source_type=SourceType.upload,
    )
    ev_b = Evidence(
        id=uuid.uuid4(),
        student_id=bob.id,
        file_name="Architecture_Report.pdf",
        file_type=FileType.pdf,
        file_path="/tmp/bob-architecture-report.pdf",
        source_type=SourceType.upload,
    )
    db.add(ev_a)
    db.add(ev_b)
    db.commit()

    return {
        "module": module,
        "group_a": group_a,
        "group_b": group_b,
        "alice": alice,
        "bob": bob,
        "evidence": [ev_a, ev_b],
    }


def _cleanup_module_seed(db, seed):
    from app.models.evidence import Evidence
    from app.models.module import Module
    from app.models.overlap_signal import OverlapSignal
    from app.models.project import Project
    from app.models.student import Student

    module = seed["module"]
    project_ids = [seed["group_a"].id, seed["group_b"].id]
    student_ids = [seed["alice"].id, seed["bob"].id]

    (
        db.query(OverlapSignal)
        .filter(
            OverlapSignal.student_a_id.in_(student_ids),
            OverlapSignal.student_b_id.in_(student_ids),
        )
        .delete(synchronize_session=False)
    )
    db.query(Evidence).filter(Evidence.student_id.in_(student_ids)).delete(
        synchronize_session=False
    )
    db.query(Student).filter(Student.id.in_(student_ids)).delete(
        synchronize_session=False
    )
    db.query(Project).filter(Project.id.in_(project_ids)).delete(
        synchronize_session=False
    )
    db.query(Module).filter(Module.id == module.id).delete(synchronize_session=False)
    db.commit()


class TestOverlapRoutes:
    def test_analyze_overlap_generates_signal_and_warning(self, client, db, teacher, monkeypatch):
        from app.services.overlap_service import OverlapService

        monkeypatch.setattr(
            OverlapService,
            "_generate_ollama_warning",
            staticmethod(lambda _prompt: "AI warning: possible overlap found, review manually."),
        )

        seed = _seed_module_with_overlap(db, teacher)
        headers = _auth_headers(client)
        module_id = seed["module"].id
        try:
            res = client.post(f"{MODULES_URL}/{module_id}/overlap/analyze", headers=headers)
            assert res.status_code == 200
            body = res.json()
            assert body["module_id"] == str(module_id)
            assert body["generated_count"] >= 1
            assert body["warning"]["has_overlap"] is True
            assert body["warning"]["high_risk_count"] >= 1
            assert body["warning"]["signal_count"] >= 1
            assert body["warning"]["warning"].startswith("AI warning")
            assert len(body["signals"]) >= 1
        finally:
            _cleanup_module_seed(db, seed)

    def test_warning_route_reports_no_overlap_without_signals(self, client, db, teacher):
        from app.models.module import Module

        module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="No Overlap Module")
        db.add(module)
        db.commit()

        headers = _auth_headers(client)
        try:
            res = client.get(f"{MODULES_URL}/{module.id}/overlap/warning", headers=headers)
            assert res.status_code == 200
            body = res.json()
            assert body["has_overlap"] is False
            assert body["signal_count"] == 0
        finally:
            db.delete(module)
            db.commit()

    def test_list_signals_returns_detected_pairs(self, client, db, teacher, monkeypatch):
        from app.services.overlap_service import OverlapService

        monkeypatch.setattr(
            OverlapService,
            "_generate_ollama_warning",
            staticmethod(lambda _prompt: "warning"),
        )

        seed = _seed_module_with_overlap(db, teacher)
        headers = _auth_headers(client)
        module_id = seed["module"].id

        try:
            analyze = client.post(f"{MODULES_URL}/{module_id}/overlap/analyze", headers=headers)
            assert analyze.status_code == 200

            listed = client.get(f"{MODULES_URL}/{module_id}/overlap/signals", headers=headers)
            assert listed.status_code == 200
            rows = listed.json()
            assert len(rows) >= 1
            assert rows[0]["student_a_name"] in {"Alice", "Bob"}
            assert rows[0]["student_b_name"] in {"Alice", "Bob"}
            assert rows[0]["confidence"] >= 0.6
        finally:
            _cleanup_module_seed(db, seed)
