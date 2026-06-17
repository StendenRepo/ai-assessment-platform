LOGIN = "/api/v1/auth/login"
PIN = "/api/v1/auth/pin"
CREDS = {"email": "teacher@test.com", "password": "password123"}


def _token(client):
    return client.post(LOGIN, json=CREDS).json()["access_token"]


def _auth(client):
    return {"Authorization": f"Bearer {_token(client)}"}


class TestPinLogin:
    def test_login_without_pin_issues_token(self, client, teacher):
        res = client.post(LOGIN, json=CREDS)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["access_token"]
        assert body["pin_required"] is False

    def test_set_pin_requires_correct_password(self, client, teacher):
        res = client.post(
            PIN, json={"password": "wrong", "pin": "1234"}, headers=_auth(client)
        )
        assert res.status_code == 401

    def test_invalid_pin_format_rejected(self, client, teacher):
        res = client.post(
            PIN, json={"password": "password123", "pin": "12"}, headers=_auth(client)
        )
        assert res.status_code == 422

    def test_set_pin_then_login_requires_it(self, client, teacher):
        headers = _auth(client)
        res = client.post(
            PIN, json={"password": "password123", "pin": "1234"}, headers=headers
        )
        assert res.status_code == 200, res.text
        assert res.json()["has_pin"] is True

        prompted = client.post(LOGIN, json=CREDS)
        assert prompted.status_code == 200
        assert prompted.json()["pin_required"] is True
        assert prompted.json()["access_token"] is None

        wrong = client.post(LOGIN, json={**CREDS, "pin": "9999"})
        assert wrong.status_code == 401

        ok = client.post(LOGIN, json={**CREDS, "pin": "1234"})
        assert ok.status_code == 200
        assert ok.json()["access_token"]

    def test_remove_pin_restores_normal_login(self, client, teacher):
        headers = _auth(client)
        client.post(
            PIN, json={"password": "password123", "pin": "4321"}, headers=headers
        )

        removed = client.request(
            "DELETE", PIN, json={"password": "password123"}, headers=headers
        )
        assert removed.status_code == 200, removed.text
        assert removed.json()["has_pin"] is False

        res = client.post(LOGIN, json=CREDS)
        assert res.status_code == 200
        assert res.json()["access_token"]
        assert res.json()["pin_required"] is False
