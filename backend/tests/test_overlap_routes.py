import uuid

from app.models.enums import FileType, SourceType

LOGIN_URL = "/api/v1/auth/login"
MODULES_URL = "/api/v1/modules"


def _auth_headers(client):
    res = client.post(
        LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"}
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _seed_module_with_overlap(db, teacher, upload_dir=None):
    from app.models.evidence import Evidence
    from app.models.module import Module
    from app.models.project import Project
    from app.models.student import Student
    from app.services.evidence_service import EVIDENCE_UPLOAD_DIR

    module = Module(id=uuid.uuid4(), teacher_id=teacher.id, name="Overlap Module")
    db.add(module)
    db.commit()

    group = Project(id=uuid.uuid4(), module_id=module.id, name="Group A")
    db.add(group)
    db.commit()

    alice = Student(name="Alice", student_number="1001001")
    bob = Student(name="Bob", student_number="1001002")
    db.add(alice)
    db.add(bob)
    db.flush()
    alice.projects.append(group)
    bob.projects.append(group)
    db.commit()

    shared = (
        "Our team implemented the authentication module using JWT tokens and bcrypt hashing. "
        "We documented every REST endpoint and wrote integration tests for login and logout."
    )
    base_dir = upload_dir or EVIDENCE_UPLOAD_DIR
    rel_a = f"{alice.student_number}/alice-report.md"
    rel_b = f"{bob.student_number}/bob-report.md"
    path_a = base_dir / rel_a
    path_b = base_dir / rel_b
    path_a.parent.mkdir(parents=True, exist_ok=True)
    path_b.parent.mkdir(parents=True, exist_ok=True)
    path_a.write_text(shared, encoding="utf-8")
    path_b.write_text(shared, encoding="utf-8")

    ev_a = Evidence(
        id=uuid.uuid4(),
        student_id=alice.student_number,
        file_name="report_a.md",
        file_type=FileType.markdown,
        file_path=rel_a,
        source_type=SourceType.upload,
    )
    ev_b = Evidence(
        id=uuid.uuid4(),
        student_id=bob.student_number,
        file_name="report_b.md",
        file_type=FileType.markdown,
        file_path=rel_b,
        source_type=SourceType.upload,
    )
    db.add(ev_a)
    db.add(ev_b)
    db.commit()

    return {
        "module": module,
        "group_a": group,
        "group_b": group,
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
    project_ids = [seed["group_a"].id]
    student_ids = [seed["alice"].student_number, seed["bob"].student_number]

    (
        db.query(OverlapSignal)
        .filter(
            OverlapSignal.student_a_id.in_(student_ids),
            OverlapSignal.student_b_id.in_(student_ids),
        )
        .delete(synchronize_session=False)
    )
    from app.models.student import student_projects
    db.query(Evidence).filter(Evidence.student_id.in_(student_ids)).delete(
        synchronize_session=False
    )
    db.execute(student_projects.delete().where(student_projects.c.student_id.in_(student_ids)))
    db.query(Student).filter(Student.student_number.in_(student_ids)).delete(
        synchronize_session=False
    )
    db.query(Project).filter(Project.id.in_(project_ids)).delete(
        synchronize_session=False
    )
    db.query(Module).filter(Module.id == module.id).delete(synchronize_session=False)
    db.commit()


class TestOverlapRoutes:
    def _patch_ai(self, monkeypatch):
        from app.services.overlap_service import OverlapService

        def _fake_enrich(hit, **kwargs):
            return {
                **hit,
                "ai_verified": True,
                "ai_explanation": "AI detected shared authentication wording.",
                "detection_method": "ai_plagiarism",
                "integrity_type": "student_plagiarism",
                "ai_shared_excerpt": "authentication module using JWT tokens",
                "flags": [
                    {
                        "type": "student",
                        "confidence": 0.85,
                        "reason": "Paraphrased shared paragraph",
                        "text_a": "authentication module using JWT tokens",
                        "text_b": "authentication module using JWT tokens",
                    }
                ],
            }

        monkeypatch.setattr(
            "app.services.overlap_service.enrich_hit_with_ai",
            _fake_enrich,
        )
        monkeypatch.setattr(
            "app.services.overlap_service.detect_ai_segments",
            lambda _text: __import__(
                "app.services.overlap_integrity_detector",
                fromlist=["IntegrityResult"],
            ).IntegrityResult(integrity_type="none", confidence=0, status="none"),
        )
        monkeypatch.setattr(
            "app.services.overlap_service.combine_ai_results",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            OverlapService,
            "_generate_ollama_warning",
            staticmethod(lambda _prompt: "AI warning: possible overlap found, review manually."),
        )

    def test_analyze_overlap_generates_signal_and_warning(
        self, client, db, teacher, monkeypatch, tmp_path
    ):
        upload_dir = tmp_path / "evidence"
        monkeypatch.setattr(
            "app.services.evidence_service.EVIDENCE_UPLOAD_DIR",
            upload_dir,
        )
        monkeypatch.setattr(
            "app.services.overlap_service.EVIDENCE_UPLOAD_DIR",
            upload_dir,
        )
        self._patch_ai(monkeypatch)

        seed = _seed_module_with_overlap(db, teacher, upload_dir=upload_dir)
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

    def test_list_signals_returns_detected_pairs(
        self, client, db, teacher, monkeypatch, tmp_path
    ):
        upload_dir = tmp_path / "evidence"
        monkeypatch.setattr(
            "app.services.evidence_service.EVIDENCE_UPLOAD_DIR",
            upload_dir,
        )
        monkeypatch.setattr(
            "app.services.overlap_service.EVIDENCE_UPLOAD_DIR",
            upload_dir,
        )
        self._patch_ai(monkeypatch)

        seed = _seed_module_with_overlap(db, teacher, upload_dir=upload_dir)
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
