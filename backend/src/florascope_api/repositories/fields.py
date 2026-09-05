from __future__ import annotations

import json
from pyproj import Geod
from shapely.geometry import shape
from uuid import uuid4

from ..database import Database, utcnow


class FieldRepository:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.geod = Geod(ellps="WGS84")

    def list(self) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM fields ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row(row) for row in rows]

    def get(self, field_id: str) -> dict | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM fields WHERE id=?",
                (field_id,),
            ).fetchone()
        return self._row(row) if row else None

    def save(self, name: str, geometry: dict, field_id: str | None = None) -> dict:
        geom = shape(geometry)
        if geom.geom_type not in {"Polygon", "MultiPolygon"} or geom.is_empty or not geom.is_valid:
            raise ValueError("Нужен валидный GeoJSON Polygon/MultiPolygon")
        minx, miny, maxx, maxy = geom.bounds
        if minx < -180 or maxx > 180 or miny < -90 or maxy > 90:
            raise ValueError("Ожидаются координаты WGS84")

        area_m2, _ = self.geod.geometry_area_perimeter(geom)
        area_ha = abs(float(area_m2)) / 10000.0
        if area_ha <= 0 or area_ha > 100_000:
            raise ValueError("Площадь полигона вне разумного диапазона")

        now = utcnow()
        field_id = field_id or f"field-{uuid4().hex[:10]}"
        payload = json.dumps(geometry, separators=(",", ":"))
        with self.database.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM fields WHERE id=?",
                (field_id,),
            ).fetchone()
            if exists:
                connection.execute(
                    "UPDATE fields SET name=?,geometry_json=?,area_ha=?,updated_at=? WHERE id=?",
                    (name.strip(), payload, area_ha, now, field_id),
                )
            else:
                connection.execute(
                    "INSERT INTO fields(id,name,geometry_json,area_ha,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (field_id, name.strip(), payload, area_ha, now, now),
                )
        result = self.get(field_id)
        assert result is not None
        return result

    def delete(self, field_id: str) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM fields WHERE id=?", (field_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _row(row) -> dict:
        result = dict(row)
        result["geometry"] = json.loads(result.pop("geometry_json"))
        return result
