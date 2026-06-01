import uuid

LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"


class TestLogin:
    def test_valid_credentials_return_token(self, client, teacher):
        res = client.post(
            LOGIN_URL,
            json={"email": "teacher@test.com", "password": "password123"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["token_type"] == "bearer"
        assert "access_token" in body

    def test_wrong_password_returns_401(self, client, teacher):
        res = client.post(
            LOGIN_URL,
            json={"email": "teacher@test.com", "password": "wrongpassword"},
        )
        assert res.status_code == 401

    def test_unknown_email_returns_401(self, client):
        res = client.post(
            LOGIN_URL,
            json={"email": "nobody@test.com", "password": "password123"},
        )
        assert res.status_code == 401

    def test_teacher_without_password_hash_returns_401(self, client, db):
        from app.models.teacher import Teacher

        t = Teacher(
            id=uuid.uuid4(),
            name="No Hash",
            email="nohash@test.com",
            password_hash=None,
        )
        db.add(t)
        db.commit()
        res = client.post(
            LOGIN_URL,
            json={"email": "nohash@test.com", "password": "anything"},
        )
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
        res = client.post(
            LOGIN_URL,
            json={"email": "notanemail", "password": "password123"},
        )
        assert res.status_code == 422

    def test_successful_login_updates_last_login(self, client, teacher, db):
        assert teacher.last_login is None
        client.post(
            LOGIN_URL,
            json={"email": "teacher@test.com", "password": "password123"},
        )
        db.refresh(teacher)
        assert teacher.last_login is not None


class TestMe:
    def _token(self, client):
        res = client.post(
            LOGIN_URL,
            json={"email": "teacher@test.com", "password": "password123"},
        )
        return res.json()["access_token"]

    def test_no_token_returns_401(self, client):
        assert client.get(ME_URL).status_code == 401

    def test_invalid_token_returns_401(self, client):
        res = client.get(
            ME_URL, headers={"Authorization": "Bearer invalid"}
        )
        assert res.status_code == 401

    def test_valid_token_returns_profile(self, client, teacher):
        token = self._token(client)
        res = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert body["email"] == "teacher@test.com"
        assert body["name"] == "Test Teacher"
