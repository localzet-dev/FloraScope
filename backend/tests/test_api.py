import os
from pathlib import Path

os.environ["FLORASCOPE_DATA_DIR"] = "/tmp/florascope-api-test/data"
os.environ["FLORASCOPE_ARTIFACTS_DIR"] = "/tmp/florascope-api-test/artifacts"
os.environ["FLORASCOPE_DB_PATH"] = "/tmp/florascope-api-test/data/test.db"

from fastapi.testclient import TestClient

from florascope_api.main import app


def test_health_and_field_crud() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/health").status_code == 200

    geometry = {
        "type": "Polygon",
        "coordinates": [[[39.0, 45.0], [39.005, 45.0], [39.005, 45.005], [39.0, 45.005], [39.0, 45.0]]],
    }
    created = client.post("/api/v1/fields", json={"name": "API field", "geometry": geometry})
    assert created.status_code == 201
    field_id = created.json()["id"]
    assert client.get("/api/v1/fields").status_code == 200
    assert client.put(
        f"/api/v1/fields/{field_id}",
        json={"name": "renamed", "geometry": geometry},
    ).status_code == 200
    assert client.delete(f"/api/v1/fields/{field_id}").status_code == 200


def test_invalid_upload_preserves_previous_dataset():
    from florascope_api.container import container
    root = container().settings.data_dir / 'input'
    path = root / 'train_dataset.csv'
    path.write_text('previous content', encoding='utf-8')
    client = TestClient(app)
    response = client.post('/api/v1/benchmark/files/train', files={'file': ('train.csv', b'invalid\n1\n', 'text/csv')})
    assert response.status_code == 400
    assert path.read_text() == 'previous content'
    assert not list(root.glob('tmp*.csv'))


def test_recent_jobs_restore_status_and_field_after_page_reload():
    from florascope_api.container import container
    jobs = container().jobs
    job = jobs.create("live", {"field_id": "restore-test-field"})
    try:
        jobs.update(job["id"], state="running", progress=34, message="Получаем данные")
        response = TestClient(app).get("/api/v1/jobs")
        assert response.status_code == 200
        restored = next(item for item in response.json() if item["id"] == job["id"])
        assert restored["state"] == "running"
        assert restored["progress"] == 34
        events = TestClient(app).get(f"/api/v1/jobs/{job['id']}/events")
        assert events.status_code == 200
        assert events.json()[-1]["message"] == "Получаем данные"
        assert TestClient(app).get("/api/v1/jobs/nonexistent/events").status_code == 404
        assert restored["payload"]["field_id"] == "restore-test-field"
        jobs.update(job["id"], state="completed", progress=100, result_ref="analysis-example")
        finished = TestClient(app).get(f"/api/v1/jobs/{job['id']}").json()
        assert finished["result_ref"] == "analysis-example"
    finally:
        with container().database.connect() as connection:
            connection.execute("DELETE FROM jobs WHERE id=?", (job["id"],))
