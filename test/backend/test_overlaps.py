"""G2-122 – G2-129 overlap API tests."""

import json

import pytest

PROJECT = "proj-1"
GROUP = "group-1"


@pytest.fixture
def platform_store(tmp_path, monkeypatch):
    import app.api.v1.endpoints.dev_platform as dev_platform
    import app.api.v1.endpoints.overlaps as overlaps_api
    import app.api.v1.platform as platform_api
    import app.audit as audit_mod
    import app.services.overlap_service as overlap_svc
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
    for mod in (store_mod, platform_api, dev_platform, audit_mod, overlaps_api):
        monkeypatch.setattr(mod, "store", fresh)
    monkeypatch.setattr(overlap_svc, "store", fresh)
    return fresh


class TestOverlapDetection:
    def test_detect_within_group(self, client, platform_store):
        client.post(f"/api/v1/projects/{PROJECT}/groups/{GROUP}/ensure")
        res = client.post(
            f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps/detect"
        )
        assert res.status_code == 200
        body = res.json()
        assert body["confirmed_count"] + body["possible_count"] >= 1
        assert body["scanned_students"] >= 2

    def test_list_confirmed_and_possible_separate(self, client, platform_store):
        client.post(f"/api/v1/projects/{PROJECT}/groups/{GROUP}/ensure")
        client.post(f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps/detect")

        confirmed = client.get(
            f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps",
            params={"status": "confirmed", "sort": "similarity", "order": "desc"},
        )
        possible = client.get(
            f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps",
            params={"status": "possible"},
        )
        assert confirmed.status_code == 200
        assert possible.status_code == 200
        for item in confirmed.json()["items"]:
            assert item["status"] == "confirmed"
        for item in possible.json()["items"]:
            assert item["status"] == "possible"
        assert "similarity_percent" in (confirmed.json()["items"][0] if confirmed.json()["items"] else {})

    def test_detail_side_by_side(self, client, platform_store):
        client.post(f"/api/v1/projects/{PROJECT}/groups/{GROUP}/ensure")
        detect = client.post(
            f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps/detect"
        )
        overlap_id = detect.json()["items"][0]["id"]
        detail = client.get(
            f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps/{overlap_id}"
        )
        assert detail.status_code == 200
        body = detail.json()
        assert body["passage_a"]
        assert body["passage_b"]
        assert body["student_a_name"]
        assert body["student_b_name"]

    def test_sort_by_similarity(self, client, platform_store):
        client.post(f"/api/v1/projects/{PROJECT}/groups/{GROUP}/ensure")
        client.post(f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps/detect")
        res = client.get(
            f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps",
            params={"sort": "similarity", "order": "desc"},
        )
        scores = [i["similarity"] for i in res.json()["items"]]
        assert scores == sorted(scores, reverse=True)

    def test_cross_group_detect(self, client, platform_store):
        """G2-123: overlaps between group-1 and group-2."""
        for gid in ("group-1", "group-2"):
            client.post(f"/api/v1/projects/{PROJECT}/groups/{gid}/ensure")
        res = client.post(f"/api/v1/projects/{PROJECT}/overlaps/cross-group/detect")
        assert res.status_code == 200
        body = res.json()
        cross = [i for i in body["items"] if i["scope"] == "cross_group"]
        assert cross, "expected at least one cross-group hit from demo fixtures"
        assert body["cross_group_count"] >= 1

    def test_detect_all_project(self, client, platform_store):
        for gid in ("group-1", "group-2"):
            client.post(f"/api/v1/projects/{PROJECT}/groups/{gid}/ensure")
        res = client.post(f"/api/v1/projects/{PROJECT}/overlaps/detect-all")
        assert res.status_code == 200
        body = res.json()
        assert body["within_group_count"] >= 1
        assert body["cross_group_count"] >= 1

    def test_confirmed_and_possible_routes(self, client, platform_store):
        client.post(f"/api/v1/projects/{PROJECT}/groups/{GROUP}/ensure")
        client.post(f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps/detect")

        confirmed = client.get(
            f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps/confirmed"
        )
        possible = client.get(
            f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps/possible"
        )
        assert confirmed.status_code == 200
        assert possible.status_code == 200
        for item in confirmed.json()["items"]:
            assert item["status"] == "confirmed"
        for item in possible.json()["items"]:
            assert item["status"] == "possible"

    def test_export_zip(self, client, platform_store):
        client.post(f"/api/v1/projects/{PROJECT}/groups/{GROUP}/ensure")
        client.post(f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps/detect")
        res = client.get(
            f"/api/v1/projects/{PROJECT}/groups/{GROUP}/overlaps/export/zip"
        )
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/zip"
        assert len(res.content) > 100
