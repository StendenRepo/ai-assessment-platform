"""Tests for per-event-type notification preferences (G2-220)."""
import uuid
from datetime import datetime

import pytest

from app.core.security import create_access_token
from app.models.audit_event import AuditEvent
from app.models.enums import NotificationType
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.services import notification_preference_service, notification_service


def _auth(teacher):
    return {"Authorization": f"Bearer {create_access_token(subject=str(teacher.id))}"}


@pytest.fixture
def other_teacher(db):
    from app.core.security import hash_password
    from app.models.teacher import Teacher

    t = Teacher(
        id=uuid.uuid4(),
        name="Other Teacher",
        email="other@test.com",
        password_hash=hash_password("password123"),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _note(db, teacher, ntype):
    n = Notification(
        id=uuid.uuid4(),
        teacher_id=teacher.id,
        type=ntype,
        message="event",
        created_at=datetime.utcnow(),
    )
    db.add(n)
    db.commit()
    return n


class TestPreferenceService:
    def test_defaults_to_enabled_when_no_rows(self, db, teacher):
        prefs = notification_preference_service.get_effective_preferences(
            db, teacher_id=teacher.id
        )
        assert set(prefs) == set(NotificationType)
        assert all(prefs.values())
        assert (
            notification_preference_service.disabled_types(db, teacher_id=teacher.id)
            == set()
        )

    def test_set_preference_persists_and_audits_in_same_transaction(self, db, teacher):
        pref = notification_preference_service.set_preference(
            db,
            teacher=teacher,
            notification_type=NotificationType.ai_processing_complete,
            enabled=False,
        )
        assert pref.enabled is False

        rows = (
            db.query(NotificationPreference)
            .filter(NotificationPreference.teacher_id == teacher.id)
            .all()
        )
        assert len(rows) == 1

        # NFR-02: the write produced an audit entry, committed together with it.
        event = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "notification_preference.updated")
            .first()
        )
        assert event is not None
        assert event.teacher_id == teacher.id
        assert event.details_json["notification_type"] == "ai_processing_complete"
        assert event.details_json["enabled"] is False

    def test_set_preference_upserts_single_row(self, db, teacher):
        notification_preference_service.set_preference(
            db,
            teacher=teacher,
            notification_type=NotificationType.deletion_reminder,
            enabled=False,
        )
        notification_preference_service.set_preference(
            db,
            teacher=teacher,
            notification_type=NotificationType.deletion_reminder,
            enabled=True,
        )
        rows = (
            db.query(NotificationPreference)
            .filter(
                NotificationPreference.teacher_id == teacher.id,
                NotificationPreference.notification_type
                == NotificationType.deletion_reminder,
            )
            .all()
        )
        assert len(rows) == 1
        assert rows[0].enabled is True
        # Each change is independently audited.
        events = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "notification_preference.updated")
            .all()
        )
        assert len(events) == 2

    def test_disabled_types_reports_only_disabled(self, db, teacher):
        notification_preference_service.set_preference(
            db,
            teacher=teacher,
            notification_type=NotificationType.ai_processing_failed,
            enabled=False,
        )
        assert notification_preference_service.disabled_types(
            db, teacher_id=teacher.id
        ) == {NotificationType.ai_processing_failed}


class TestServerSideFiltering:
    def test_list_hides_disabled_type(self, db, teacher):
        _note(db, teacher, NotificationType.ai_processing_complete)
        _note(db, teacher, NotificationType.deletion_reminder)
        notification_preference_service.set_preference(
            db,
            teacher=teacher,
            notification_type=NotificationType.ai_processing_complete,
            enabled=False,
        )
        items = notification_service.list_for_teacher(db, teacher_id=teacher.id)
        types = {i.type for i in items}
        assert NotificationType.ai_processing_complete not in types
        assert NotificationType.deletion_reminder in types

    def test_reenabling_restores_existing_notifications(self, db, teacher):
        _note(db, teacher, NotificationType.ai_processing_complete)
        notification_preference_service.set_preference(
            db,
            teacher=teacher,
            notification_type=NotificationType.ai_processing_complete,
            enabled=False,
        )
        assert notification_service.list_for_teacher(db, teacher_id=teacher.id) == []
        notification_preference_service.set_preference(
            db,
            teacher=teacher,
            notification_type=NotificationType.ai_processing_complete,
            enabled=True,
        )
        items = notification_service.list_for_teacher(db, teacher_id=teacher.id)
        assert len(items) == 1

    def test_preferences_are_per_teacher(self, db, teacher, other_teacher):
        _note(db, teacher, NotificationType.ai_processing_complete)
        _note(db, other_teacher, NotificationType.ai_processing_complete)
        # other_teacher disables; teacher must be unaffected.
        notification_preference_service.set_preference(
            db,
            teacher=other_teacher,
            notification_type=NotificationType.ai_processing_complete,
            enabled=False,
        )
        assert len(notification_service.list_for_teacher(db, teacher_id=teacher.id)) == 1
        assert (
            notification_service.list_for_teacher(db, teacher_id=other_teacher.id) == []
        )


class TestPreferenceEndpoints:
    def test_get_returns_all_types_default_enabled(self, client, teacher):
        res = client.get(
            "/api/v1/notification-preferences", headers=_auth(teacher)
        )
        assert res.status_code == 200
        data = res.json()
        assert {d["notification_type"] for d in data} == {
            t.value for t in NotificationType
        }
        assert all(d["enabled"] for d in data)

    def test_put_toggles_and_audits(self, client, db, teacher):
        res = client.put(
            "/api/v1/notification-preferences/ai_processing_failed",
            json={"enabled": False},
            headers=_auth(teacher),
        )
        assert res.status_code == 200
        assert res.json() == {
            "notification_type": "ai_processing_failed",
            "enabled": False,
        }
        event = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "notification_preference.updated")
            .first()
        )
        assert event is not None
        assert event.details_json["enabled"] is False

    def test_get_reflects_a_stored_override(self, client, teacher):
        client.put(
            "/api/v1/notification-preferences/deletion_reminder",
            json={"enabled": False},
            headers=_auth(teacher),
        )
        res = client.get(
            "/api/v1/notification-preferences", headers=_auth(teacher)
        )
        prefs = {d["notification_type"]: d["enabled"] for d in res.json()}
        assert prefs["deletion_reminder"] is False
        assert prefs["ai_processing_complete"] is True

    def test_requires_authentication(self, client):
        res = client.put(
            "/api/v1/notification-preferences/ai_processing_failed",
            json={"enabled": False},
        )
        assert res.status_code in (401, 403)

    def test_invalid_type_is_rejected(self, client, teacher):
        res = client.put(
            "/api/v1/notification-preferences/not_a_real_type",
            json={"enabled": True},
            headers=_auth(teacher),
        )
        assert res.status_code == 422
