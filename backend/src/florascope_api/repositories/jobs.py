from __future__ import annotations

import json
from uuid import uuid4

from ..database import Database, utcnow


class JobRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, kind: str, payload: dict) -> dict:
        job_id = f"job-{uuid4().hex[:10]}"
        now = utcnow()
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO jobs(id,kind,state,progress,stage,message,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (job_id, kind, "queued", 0, "QUEUED", "В очереди", json.dumps(payload), now, now),
            )
        return self.get(job_id)  # type: ignore[return-value]

    def list_recent(self) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT 50").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def get(self, job_id: str) -> dict | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def update(self, job_id: str, **changes) -> None:
        current = self.get(job_id)
        if current is None:
            raise KeyError(job_id)
        state = changes.get("state", current["state"])
        progress = int(changes.get("progress", current["progress"]))
        stage = changes.get("stage", current["stage"])
        message = changes.get("message", current["message"])
        result_ref = changes.get("result_ref", current.get("result_ref"))
        error = changes.get("error")
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE jobs SET state=?,progress=?,stage=?,message=?,result_ref=?,error=?,updated_at=? WHERE id=?",
                (state, max(0, min(100, progress)), stage, message, result_ref, error, utcnow(), job_id),
            )

    def fail_interrupted(self) -> None:
        # Отдельного durable worker у нас нет. После рестарта честнее пометить старый
        # running job как прерванный, чем показывать вечные 67%.
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE jobs SET state='failed',stage='INTERRUPTED',message='Backend restarted; запустите задачу ещё раз',updated_at=? WHERE state IN ('running','queued')",
                (utcnow(),),
            )
