"""Tests for FR-06 recording, consent, transcription and retention."""
import uuid
from datetime import datetime, timedelta

import pytest

from app.config import settings
from app.core.security import create_access_token
from app.models.assessment import Assessment
from app.models.audit_event import AuditEvent
from app.models.enums import ConsentStatus, NotificationType, TranscriptionStatus
from app.models.file_record import FileRecord
from app.models.notification import Notification
from app.services import (
    assessment_service,
    recording_service,
    retention_service,
    stt_client,
)


@pytest.fixture
def assessment(db, teacher):
    a = Assessment(
        id=uuid.uuid4(),
        student_id=uuid.uuid4(),  # FKs are not enforced under SQLite tests
        teacher_id=teacher.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    yield a
    # Clean up feature rows before the teacher fixture tears down, otherwise
    # deleting the teacher would try to null assessments.teacher_id (NOT NULL).
    db.query(Notification).delete()
    db.query(AuditEvent).delete()
    db.query(Assessment).delete()
    db.query(FileRecord).delete()
    db.commit()


def _auth(teacher):
    return {"Authorization": f"Bearer {create_access_token(subject=str(teacher.id))}"}


# ── Consent (G2-137 / G2-138) ────────────────────────────────────────────────

class TestConsentService:
    def test_accept_sets_status_and_audits(self, db, assessment, teacher):
        assessment_service.set_consent(
            db, assessment=assessment, teacher=teacher, status=ConsentStatus.accepted
        )
        assert assessment.consent_status == ConsentStatus.accepted
        assert assessment.consent_confirmed_at is not None
        assert assessment.consent_confirmed_by == teacher.id

        event = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "consent.accepted")
            .first()
        )
        assert event is not None
        assert event.details_json["teacher_name"] == teacher.name

    def test_decline_sets_status(self, db, assessment, teacher):
        assessment_service.set_consent(
            db, assessment=assessment, teacher=teacher, status=ConsentStatus.declined
        )
        assert assessment.consent_status == ConsentStatus.declined

    def test_pending_is_rejected(self, db, assessment, teacher):
        with pytest.raises(ValueError):
            assessment_service.set_consent(
                db, assessment=assessment, teacher=teacher, status=ConsentStatus.pending
            )


class TestConsentEndpoint:
    def test_accept_via_api(self, client, assessment, teacher):
        res = client.post(
            f"/api/v1/assessments/{assessment.id}/consent",
            json={"status": "accepted"},
            headers=_auth(teacher),
        )
        assert res.status_code == 200
        assert res.json()["consent_status"] == "accepted"

    def test_pending_rejected_with_400(self, client, assessment, teacher):
        res = client.post(
            f"/api/v1/assessments/{assessment.id}/consent",
            json={"status": "pending"},
            headers=_auth(teacher),
        )
        assert res.status_code == 400

    def test_other_teacher_forbidden(self, client, db, assessment):
        from app.models.teacher import Teacher

        other = Teacher(id=uuid.uuid4(), name="Other", email="other@test.com")
        db.add(other)
        db.commit()
        res = client.post(
            f"/api/v1/assessments/{assessment.id}/consent",
            json={"status": "accepted"},
            headers=_auth(other),
        )
        assert res.status_code == 403

    def test_missing_assessment_404(self, client, teacher):
        res = client.post(
            f"/api/v1/assessments/{uuid.uuid4()}/consent",
            json={"status": "accepted"},
            headers=_auth(teacher),
        )
        assert res.status_code == 404

    def test_invalid_assessment_id_returns_422(self, client, teacher):
        res = client.get(
            "/api/v1/assessments/student-1/recording",
            headers=_auth(teacher),
        )
        assert res.status_code == 422


# ── Recording storage + transcription (G2-136 / G2-140) ──────────────────────

class TestRecordingService:
    def test_save_recording_stores_file_and_links(self, db, assessment, teacher, tmp_path):
        settings.RECORDING_DIR = str(tmp_path)
        record = recording_service.save_recording(
            db,
            assessment=assessment,
            teacher=teacher,
            audio_bytes=b"fake-audio",
            content_type="audio/webm",
            filename="rec.webm",
        )
        assert assessment.recording_file_id == record.id
        assert record.delete_after is not None
        # 3-month retention window
        expected = datetime.utcnow() + timedelta(days=settings.RECORDING_RETENTION_DAYS)
        assert abs((record.delete_after - expected).total_seconds()) < 60
        with open(record.path, "rb") as fh:
            assert fh.read() == b"fake-audio"

        assert (
            db.query(AuditEvent).filter(AuditEvent.action == "recording.uploaded").count()
            == 1
        )

    def test_transcribe_success(self, db, assessment, teacher, tmp_path, monkeypatch):
        settings.RECORDING_DIR = str(tmp_path)
        recording_service.save_recording(
            db, assessment=assessment, teacher=teacher, audio_bytes=b"audio"
        )
        monkeypatch.setattr(
            stt_client,
            "transcribe",
            lambda *a, **k: {
                "text": "Jane Doe. I consent.",
                "segments": [{"start": 0, "end": 2, "text": "Jane Doe. I consent."}],
            },
        )
        recording_service.transcribe_recording(db, assessment=assessment, teacher=teacher)
        assert assessment.transcription_status == TranscriptionStatus.completed
        assert "I consent" in assessment.transcript_text

    def test_transcribe_failure_sets_failed(self, db, assessment, teacher, tmp_path, monkeypatch):
        settings.RECORDING_DIR = str(tmp_path)
        recording_service.save_recording(
            db, assessment=assessment, teacher=teacher, audio_bytes=b"audio"
        )

        def boom(*a, **k):
            raise RuntimeError("stt down")

        monkeypatch.setattr(stt_client, "transcribe", boom)
        with pytest.raises(RuntimeError):
            recording_service.transcribe_recording(db, assessment=assessment, teacher=teacher)
        assert assessment.transcription_status == TranscriptionStatus.failed


class TestUploadEndpoint:
    def test_upload_saves_file_and_links(
        self, client, assessment, teacher, tmp_path, monkeypatch
    ):
        settings.RECORDING_DIR = str(tmp_path)
        # STT isn't running in tests; stub it so the background task succeeds.
        monkeypatch.setattr(
            stt_client,
            "transcribe",
            lambda *a, **k: {"text": "Jane Doe. I consent.", "segments": []},
        )
        res = client.post(
            f"/api/v1/assessments/{assessment.id}/recording",
            files={"file": ("recording.webm", b"binary-audio-bytes", "audio/webm")},
            headers=_auth(teacher),
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["has_recording"] is True

        # A file was actually written to RECORDING_DIR.
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].read_bytes() == b"binary-audio-bytes"

        # And the FileRecord row points at that path.
        rec = db_record_for(client)
        assert rec is not None


def db_record_for(client):
    # helper: the client fixture shares the test db session via dependency override
    from app.api.deps import get_db

    db = client.app.dependency_overrides[get_db]()
    return db.query(FileRecord).first()


# ── Retention + reminders (G2-141 / G2-142) ──────────────────────────────────

class TestRetention:
    def _recording(self, db, assessment, delete_after):
        rec = FileRecord(
            id=uuid.uuid4(),
            path="/tmp/x.webm",
            file_type="audio/webm",
            size_bytes=1,
            delete_after=delete_after,
        )
        db.add(rec)
        db.flush()
        assessment.recording_file_id = rec.id
        db.commit()
        return rec

    def test_flags_expired_only(self, db, assessment, teacher):
        expired = self._recording(db, assessment, datetime.utcnow() - timedelta(days=1))
        fresh = FileRecord(
            id=uuid.uuid4(),
            path="/tmp/y.webm",
            delete_after=datetime.utcnow() + timedelta(days=30),
        )
        db.add(fresh)
        db.commit()

        flagged = retention_service.flag_expired_recordings(db)
        db.refresh(expired)
        db.refresh(fresh)
        assert flagged == 1
        assert expired.flagged_for_deletion is True
        assert fresh.flagged_for_deletion is False

    def test_flag_is_idempotent(self, db, assessment, teacher):
        self._recording(db, assessment, datetime.utcnow() - timedelta(days=1))
        assert retention_service.flag_expired_recordings(db) == 1
        assert retention_service.flag_expired_recordings(db) == 0

    def test_reminder_created_within_lead_window(self, db, assessment, teacher):
        # delete_after within the reminder lead window
        self._recording(
            db,
            assessment,
            datetime.utcnow() + timedelta(days=settings.RECORDING_REMINDER_LEAD_DAYS - 1),
        )
        created = retention_service.create_deletion_reminders(db)
        assert created == 1
        n = db.query(Notification).filter(Notification.assessment_id == assessment.id).first()
        assert n is not None
        assert n.type == NotificationType.deletion_reminder
        assert n.teacher_id == teacher.id

    def test_reminder_not_duplicated(self, db, assessment, teacher):
        self._recording(
            db,
            assessment,
            datetime.utcnow() + timedelta(days=settings.RECORDING_REMINDER_LEAD_DAYS - 1),
        )
        assert retention_service.create_deletion_reminders(db) == 1
        assert retention_service.create_deletion_reminders(db) == 0

    def test_no_reminder_when_far_off(self, db, assessment, teacher):
        self._recording(db, assessment, datetime.utcnow() + timedelta(days=365))
        assert retention_service.create_deletion_reminders(db) == 0
