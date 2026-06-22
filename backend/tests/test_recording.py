"""Tests for FR-06 recording, consent, transcription and retention."""
import os
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
from app.models.recording import Recording
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
        student_id="9999999",  # FKs are not enforced under SQLite tests
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
    db.query(Recording).delete()
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
    def test_append_recording_stores_file_and_links(self, db, assessment, teacher, tmp_path):
        settings.RECORDING_DIR = str(tmp_path)
        recording = recording_service.append_recording(
            db,
            assessment=assessment,
            teacher=teacher,
            audio_bytes=b"fake-audio",
            content_type="audio/webm",
            filename="rec.webm",
        )
        assert recording.assessment_id == assessment.id
        assert recording.sequence_number == 1
        assert recording.display_name == "Recording 1"

        record = db.query(FileRecord).filter(FileRecord.id == recording.file_id).first()
        assert record is not None
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

    def test_append_increments_sequence_number(self, db, assessment, teacher, tmp_path):
        settings.RECORDING_DIR = str(tmp_path)
        r1 = recording_service.append_recording(
            db, assessment=assessment, teacher=teacher, audio_bytes=b"a"
        )
        r2 = recording_service.append_recording(
            db, assessment=assessment, teacher=teacher, audio_bytes=b"b"
        )
        assert (r1.sequence_number, r2.sequence_number) == (1, 2)
        assert r2.display_name == "Recording 2"

    def test_transcribe_success(self, db, assessment, teacher, tmp_path, monkeypatch):
        settings.RECORDING_DIR = str(tmp_path)
        recording = recording_service.append_recording(
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
        recording_service.transcribe_recording(db, recording=recording, teacher=teacher)
        assert recording.transcription_status == TranscriptionStatus.completed
        assert "I consent" in recording.transcript_text

    def test_transcribe_failure_sets_failed(self, db, assessment, teacher, tmp_path, monkeypatch):
        settings.RECORDING_DIR = str(tmp_path)
        recording = recording_service.append_recording(
            db, assessment=assessment, teacher=teacher, audio_bytes=b"audio"
        )

        def boom(*a, **k):
            raise RuntimeError("stt down")

        monkeypatch.setattr(stt_client, "transcribe", boom)
        with pytest.raises(RuntimeError):
            recording_service.transcribe_recording(db, recording=recording, teacher=teacher)
        assert recording.transcription_status == TranscriptionStatus.failed


def _accept_consent(db, assessment):
    assessment.consent_status = ConsentStatus.accepted
    db.commit()


class TestUploadEndpoint:
    def test_upload_requires_consent(self, client, assessment, teacher, tmp_path):
        settings.RECORDING_DIR = str(tmp_path)
        # consent is pending by default -> 409
        res = client.post(
            f"/api/v1/assessments/{assessment.id}/recording",
            files={"file": ("recording.webm", b"abc", "audio/webm")},
            headers=_auth(teacher),
        )
        assert res.status_code == 409

    def test_upload_saves_file_and_appends(
        self, client, db, assessment, teacher, tmp_path, monkeypatch
    ):
        settings.RECORDING_DIR = str(tmp_path)
        _accept_consent(db, assessment)
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
        assert body["display_name"] == "Recording 1"
        assert body["sequence_number"] == 1

        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].read_bytes() == b"binary-audio-bytes"
        assert db.query(FileRecord).count() == 1


class TestRecordingsApi:
    def _make(self, db, teacher, assessment, tmp_path, n=1):
        settings.RECORDING_DIR = str(tmp_path)
        recs = []
        for _ in range(n):
            recs.append(
                recording_service.append_recording(
                    db, assessment=assessment, teacher=teacher, audio_bytes=b"x"
                )
            )
        return recs

    def test_list_recordings(self, client, db, assessment, teacher, tmp_path):
        self._make(db, teacher, assessment, tmp_path, n=2)
        res = client.get(
            f"/api/v1/assessments/{assessment.id}/recordings", headers=_auth(teacher)
        )
        assert res.status_code == 200
        body = res.json()
        assert [r["sequence_number"] for r in body] == [1, 2]

    def test_get_recording_detail(self, client, db, assessment, teacher, tmp_path):
        rec = self._make(db, teacher, assessment, tmp_path)[0]
        res = client.get(
            f"/api/v1/assessments/{assessment.id}/recordings/{rec.id}",
            headers=_auth(teacher),
        )
        assert res.status_code == 200
        assert "transcript_text" in res.json()

    def test_rename(self, client, db, assessment, teacher, tmp_path):
        rec = self._make(db, teacher, assessment, tmp_path)[0]
        res = client.patch(
            f"/api/v1/assessments/{assessment.id}/recordings/{rec.id}",
            json={"display_name": "Intro segment"},
            headers=_auth(teacher),
        )
        assert res.status_code == 200
        assert res.json()["display_name"] == "Intro segment"
        assert (
            db.query(AuditEvent).filter(AuditEvent.action == "recording.renamed").count() == 1
        )

    def test_extend_expiry_within_cap(self, client, db, assessment, teacher, tmp_path):
        rec = self._make(db, teacher, assessment, tmp_path)[0]
        res = client.patch(
            f"/api/v1/assessments/{assessment.id}/recordings/{rec.id}",
            json={"extend_expiry": {"reason": "appeal pending", "extra_days": 30}},
            headers=_auth(teacher),
        )
        assert res.status_code == 200
        assert res.json()["extension_count"] == 1

    def test_extend_requires_reason(self, client, db, assessment, teacher, tmp_path):
        rec = self._make(db, teacher, assessment, tmp_path)[0]
        res = client.patch(
            f"/api/v1/assessments/{assessment.id}/recordings/{rec.id}",
            json={"extend_expiry": {"reason": "", "extra_days": 30}},
            headers=_auth(teacher),
        )
        assert res.status_code == 422  # pydantic min_length

    def test_extend_capped_at_two(self, client, db, assessment, teacher, tmp_path):
        rec = self._make(db, teacher, assessment, tmp_path)[0]
        url = f"/api/v1/assessments/{assessment.id}/recordings/{rec.id}"
        for _ in range(2):
            ok = client.patch(
                url, json={"extend_expiry": {"reason": "r"}}, headers=_auth(teacher)
            )
            assert ok.status_code == 200
        third = client.patch(
            url, json={"extend_expiry": {"reason": "r"}}, headers=_auth(teacher)
        )
        assert third.status_code == 400

    def test_delete_is_soft_and_unlinks_file(
        self, client, db, assessment, teacher, tmp_path
    ):
        rec = self._make(db, teacher, assessment, tmp_path)[0]
        record = db.query(FileRecord).filter(FileRecord.id == rec.file_id).first()
        assert os.path.exists(record.path)

        res = client.delete(
            f"/api/v1/assessments/{assessment.id}/recordings/{rec.id}",
            headers=_auth(teacher),
        )
        assert res.status_code == 204

        db.refresh(rec)
        assert rec.deleted_at is not None          # row kept (audit trail)
        assert not os.path.exists(record.path)     # file unlinked
        # no longer listed
        listed = client.get(
            f"/api/v1/assessments/{assessment.id}/recordings", headers=_auth(teacher)
        ).json()
        assert listed == []

    def test_other_teacher_cannot_list(self, client, db, assessment, teacher, tmp_path):
        from app.models.teacher import Teacher

        self._make(db, teacher, assessment, tmp_path)
        other = Teacher(id=uuid.uuid4(), name="Other", email="other2@test.com")
        db.add(other)
        db.commit()
        res = client.get(
            f"/api/v1/assessments/{assessment.id}/recordings", headers=_auth(other)
        )
        assert res.status_code == 403


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
        recording = Recording(
            id=uuid.uuid4(),
            assessment_id=assessment.id,
            file_id=rec.id,
            display_name="Recording 1",
            sequence_number=1,
        )
        db.add(recording)
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


# ── Per-recording reminders (G2-142) ─────────────────────────────────────────

class TestPerRecordingReminders:
    def _expiring(self, db, assessment, seq, days):
        rec = FileRecord(
            id=uuid.uuid4(),
            path=f"/tmp/r{seq}.webm",
            delete_after=datetime.utcnow() + timedelta(days=days),
        )
        db.add(rec)
        db.flush()
        recording = Recording(
            id=uuid.uuid4(),
            assessment_id=assessment.id,
            file_id=rec.id,
            display_name=f"Recording {seq}",
            sequence_number=seq,
        )
        db.add(recording)
        db.commit()
        return recording

    def test_each_expiring_recording_gets_its_own_reminder(self, db, assessment, teacher):
        lead = settings.RECORDING_REMINDER_LEAD_DAYS
        for seq in (1, 2, 3):
            self._expiring(db, assessment, seq, lead - 1)

        created = retention_service.create_deletion_reminders(db)
        assert created == 3

        notes = db.query(Notification).all()
        assert len(notes) == 3
        # every reminder references a specific recording and names it
        assert all(n.recording_id is not None for n in notes)
        messages = " | ".join(n.message for n in notes)
        assert "Recording 1" in messages
        assert "Recording 2" in messages
        assert "Recording 3" in messages

    def test_reminder_dedup_is_per_recording(self, db, assessment, teacher):
        self._expiring(db, assessment, 1, settings.RECORDING_REMINDER_LEAD_DAYS - 1)
        assert retention_service.create_deletion_reminders(db) == 1
        assert retention_service.create_deletion_reminders(db) == 0


# ── Auto-purge (G2-141) ──────────────────────────────────────────────────────

class TestAutoPurge:
    def _recording_with_file(self, db, assessment, teacher, tmp_path):
        settings.RECORDING_DIR = str(tmp_path)
        rec = recording_service.append_recording(
            db, assessment=assessment, teacher=teacher, audio_bytes=b"audio-bytes"
        )
        record = db.query(FileRecord).filter(FileRecord.id == rec.file_id).first()
        return rec, record

    def test_expired_recording_is_purged(self, db, assessment, teacher, tmp_path):
        rec, record = self._recording_with_file(db, assessment, teacher, tmp_path)
        path = record.path
        assert os.path.exists(path)

        # force the retention date into the past (no extension)
        record.delete_after = datetime.utcnow() - timedelta(days=1)
        db.commit()

        purged = retention_service.purge_expired_recordings(db)
        assert purged == 1

        db.refresh(rec)
        db.refresh(record)
        assert not os.path.exists(path)        # audio removed from disk
        assert rec.deleted_at is not None       # metadata row kept, marked deleted
        assert record.deleted_at is not None
        # audit event recorded with the system reason
        ev = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "recording.auto_deleted")
            .first()
        )
        assert ev is not None
        assert ev.details_json["reason"] == "retention expired, no action taken"

    def test_extended_recording_is_not_purged(self, db, assessment, teacher, tmp_path):
        rec, record = self._recording_with_file(db, assessment, teacher, tmp_path)
        path = record.path

        # simulate an active extension: future delete_after
        record.delete_after = datetime.utcnow() + timedelta(days=30)
        db.commit()

        purged = retention_service.purge_expired_recordings(db)
        assert purged == 0
        assert os.path.exists(path)             # file untouched
        db.refresh(rec)
        assert rec.deleted_at is None
