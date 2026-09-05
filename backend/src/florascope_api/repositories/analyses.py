from __future__ import annotations

from ..database import Database, utcnow


class AnalysisRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(self, analysis_id: str, field_id: str, title: str, result_path: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO analyses(id,field_id,title,result_path,created_at) VALUES(?,?,?,?,?)",
                (analysis_id, field_id, title, result_path, utcnow()),
            )

    def list(self) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM analyses ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, analysis_id: str) -> dict | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM analyses WHERE id=?",
                (analysis_id,),
            ).fetchone()
        return dict(row) if row else None
