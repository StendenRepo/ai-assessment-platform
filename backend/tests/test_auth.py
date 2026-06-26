import uuid

from app.models.audit_event import AuditEvent

LOGIN_URL = "/api/v1/auth/login"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"


class TestLogin:
    def test_valid_credentials_return_token(self, client, teacher):
        res = client.post(LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"})
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_wrong_password_returns_401(self, client, teacher):
        res = client.post(LOGIN_URL, json={"email": "teacher@test.com", "password": "wrongpassword"})
        assert res.status_code == 401

    def test_unknown_email_returns_401(self, client):
        res = client.post(LOGIN_URL, json={"email": "nobody@test.com", "password": "password123"})
        assert res.status_code == 401

    def test_teacher_without_password_hash_returns_401(self, client, db):
        from app.models.teacher import Teacher

        t = Teacher(id=uuid.uuid4(), name="No Hash", email="nohash@test.com", password_hash=None)
        db.add(t)
        db.commit()

        res = client.post(LOGIN_URL, json={"email": "nohash@test.com", "password": "anything"})
        assert res.status_code == 401

        db.delete(t)
        db.commit()

    def test_missing_password_field_returns_422(self, client):
        res = client.post(LOGIN_URL, json={"email": "teacher@test.com"})
        assert res.status_code == 422

    def test_missing_email_field_returns_422(self, client):
        res = client.post(LOGIN_URL, json={"password": "password123"})
        assert res.status_code == 422

    def test_invalid_email_format_returns_422(self, client):
        res = client.post(LOGIN_URL, json={"email": "notanemail", "password": "password123"})
        assert res.status_code == 422

    def test_successful_login_updates_last_login(self, client, teacher, db):
        assert teacher.last_login is None
        client.post(LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"})
        db.refresh(teacher)
        assert teacher.last_login is not None


class TestLoginAudit:
    def test_successful_login_creates_audit_event(self, client, teacher, db):
        client.post(LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"})
        events = db.query(AuditEvent).filter(AuditEvent.action == "auth.login").all()
        assert len(events) == 1
        event = events[0]
        assert str(event.teacher_id) == str(teacher.id)
        assert event.details_json["email"] == "teacher@test.com"
        assert event.details_json["role"] == "teacher"
        assert "password" not in event.details_json

    def test_successful_login_does_not_log_sensitive_fields(self, client, teacher, db):
        client.post(LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"})
        event = db.query(AuditEvent).filter(AuditEvent.action == "auth.login").first()
        assert event is not None
        for forbidden in ("password", "pin", "access_token", "token"):
            assert forbidden not in event.details_json

    def test_wrong_password_creates_login_failed_audit_event(self, client, teacher, db):
        client.post(LOGIN_URL, json={"email": "teacher@test.com", "password": "wrong"})
        events = db.query(AuditEvent).filter(AuditEvent.action == "auth.login_failed").all()
        assert len(events) == 1
        event = events[0]
        assert event.details_json["email"] == "teacher@test.com"
        assert event.details_json["reason"] == "Invalid password"
        assert "password" not in event.details_json

    def test_unknown_email_creates_login_failed_audit_event(self, client, db):
        client.post(LOGIN_URL, json={"email": "ghost@test.com", "password": "password123"})
        events = db.query(AuditEvent).filter(AuditEvent.action == "auth.login_failed").all()
        assert len(events) == 1
        event = events[0]
        assert event.details_json["email"] == "ghost@test.com"
        assert event.details_json["reason"] == "Unknown user"
        assert event.teacher_id is None

    def test_login_failed_does_not_log_sensitive_fields(self, client, teacher, db):
        client.post(LOGIN_URL, json={"email": "teacher@test.com", "password": "bad"})
        event = db.query(AuditEvent).filter(AuditEvent.action == "auth.login_failed").first()
        assert event is not None
        for forbidden in ("password", "pin", "access_token", "token"):
            assert forbidden not in event.details_json

    def test_successful_login_does_not_create_login_failed_event(self, client, teacher, db):
        client.post(LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"})
        failed = db.query(AuditEvent).filter(AuditEvent.action == "auth.login_failed").all()
        assert len(failed) == 0


class TestLogoutAudit:
    def _get_token(self, client):
        res = client.post(LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"})
        return res.json()["access_token"]

    def test_logout_creates_audit_event(self, client, teacher, db):
        token = self._get_token(client)
        res = client.post(LOGOUT_URL, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 204
        events = db.query(AuditEvent).filter(AuditEvent.action == "auth.logout").all()
        assert len(events) == 1
        event = events[0]
        assert str(event.teacher_id) == str(teacher.id)
        assert event.details_json["email"] == "teacher@test.com"

    def test_logout_requires_authentication(self, client, teacher, db):
        res = client.post(LOGOUT_URL)
        assert res.status_code == 401
        events = db.query(AuditEvent).filter(AuditEvent.action == "auth.logout").all()
        assert len(events) == 0


class TestMe:
    def _login(self, client):
        res = client.post(LOGIN_URL, json={"email": "teacher@test.com", "password": "password123"})
        return res.json()["access_token"]

    def test_no_token_returns_401(self, client):
        res = client.get(ME_URL)
        assert res.status_code == 401

    def test_invalid_token_returns_401(self, client):
        res = client.get(ME_URL, headers={"Authorization": "Bearer thisisnotavalidtoken"})
        assert res.status_code == 401

    def test_valid_token_returns_profile(self, client, teacher):
        token = self._login(client)
        res = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert body["email"] == "teacher@test.com"
        assert body["name"] == "Test Teacher"
        assert "id" in body
