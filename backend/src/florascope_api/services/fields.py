from __future__ import annotations

import httpx
from shapely.geometry import Polygon, mapping

from ..repositories.fields import FieldRepository


class FieldService:
    def __init__(self, repository: FieldRepository, overpass_url: str) -> None:
        self.repository = repository
        self.overpass_url = overpass_url

    def discover(self, bbox: tuple[float, float, float, float], limit: int) -> list[dict]:
        west, south, east, north = bbox
        if west >= east or south >= north:
            raise ValueError("Некорректный bbox")
        if (east - west) * (north - south) > 1.0:
            raise ValueError("Для поиска контуров приблизьте карту")

        query = (
            '[out:json][timeout:20];'
            f'way["landuse"~"^(farmland|orchard|vineyard|meadow)$"]({south},{west},{north},{east});'
            "out geom tags;"
        )
        with httpx.Client(timeout=30.0) as client:
            response = client.post(self.overpass_url, content=query.encode("utf-8"))
            response.raise_for_status()
            payload = response.json()

        result: list[dict] = []
        for element in payload.get("elements", []):
            coordinates = [
                (float(point["lon"]), float(point["lat"]))
                for point in element.get("geometry", [])
                if "lon" in point and "lat" in point
            ]
            if len(coordinates) < 4:
                continue
            if coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])
            polygon = Polygon(coordinates)
            if polygon.is_empty or not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.is_empty or polygon.geom_type != "Polygon":
                continue
            tags = element.get("tags") or {}
            result.append(
                {
                    "source": "openstreetmap",
                    "source_id": str(element.get("id")),
                    "name": tags.get("name") or f"OSM {tags.get('landuse', 'field')} {element.get('id')}",
                    "landuse": tags.get("landuse"),
                    "geometry": mapping(polygon),
                }
            )
            if len(result) >= limit:
                break
        return result
