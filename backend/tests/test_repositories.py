from pathlib import Path

from florascope_api.database import Database
from florascope_api.repositories.fields import FieldRepository
from florascope_api.repositories.jobs import JobRepository


def test_field_crud_and_persistent_job(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.db")
    fields = FieldRepository(database)
    jobs = JobRepository(database)
    geometry = {
        "type": "Polygon",
        "coordinates": [[[39.0, 45.0], [39.01, 45.0], [39.01, 45.01], [39.0, 45.01], [39.0, 45.0]]],
    }

    field = fields.save("Поле", geometry)
    assert field["area_ha"] > 0
    updated = fields.save("Поле 2", geometry, field_id=field["id"])
    assert updated["name"] == "Поле 2"

    job = jobs.create("competition", {"fast": True})
    jobs.update(job["id"], state="running", progress=42, stage="TRAINING", message="ok")
    assert jobs.get(job["id"])["progress"] == 42
    jobs.fail_interrupted()
    assert jobs.get(job["id"])["state"] == "failed"
    assert fields.delete(field["id"])


def test_restart_marks_queued_and_running_jobs_interrupted(tmp_path):
    from florascope_api.database import Database
    from florascope_api.repositories.jobs import JobRepository
    repo = JobRepository(Database(tmp_path / 'jobs.db'))
    queued = repo.create('live', {})
    running = repo.create('live', {})
    repo.update(running['id'], state='running')
    repo.fail_interrupted()
    assert repo.get(queued['id'])['state'] == 'failed'
    assert repo.get(running['id'])['state'] == 'failed'
