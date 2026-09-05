from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from shapely.geometry import shape
from uuid import uuid4

from .landsat import LandsatProvider
from .models import Observation, SceneRef
from .sentinel2 import Sentinel2Provider
from .spatial import analyze_spatial
from .temporal import analyze_temporal, merge_same_day, same_day
from .weather import WeatherProvider


class LiveAnalyzer:
    def __init__(
        self,
        *,
        earth_search_url: str,
        weather_url: str,
        data_dir: Path,
        resolution_m: float = 20.0,
        max_cells: int = 300_000,
    ) -> None:
        self.sentinel = Sentinel2Provider(earth_search_url)
        self.landsat = LandsatProvider(earth_search_url)
        self.weather = WeatherProvider(weather_url)
        self.data_dir = data_dir
        self.resolution_m = resolution_m
        self.max_cells = max_cells

    def run(
        self,
        field: dict,
        *,
        date_from: date,
        date_to: date,
        history_years: int = 3,
        max_cloud_cover: float = 35.0,
        progress=None,
    ) -> dict:
        if date_from.year != date_to.year:
            raise ValueError("Live-анализ сейчас ожидает один сезон внутри календарного года")

        analysis_id = f"live-{uuid4().hex[:10]}"
        root = self.data_dir / "live" / analysis_id
        layers_dir = root / "layers"
        layers_dir.mkdir(parents=True, exist_ok=True)

        geometry = field["geometry"]
        polygon = shape(geometry)
        bbox = tuple(float(value) for value in polygon.bounds)
        center = polygon.centroid

        observations: list[Observation] = []
        sentinel_scenes: dict[str, SceneRef] = {}
        source_info = {
            "sentinel-2": {"candidate_scenes": 0, "usable": 0, "errors": []},
            "landsat": {"candidate_scenes": 0, "usable": 0, "errors": []},
            "era5": {"available": False, "errors": []},
        }

        landsat_access_denied = False
        years = range(date_from.year - history_years, date_to.year + 1)
        for index, year in enumerate(years, start=1):
            season_from = same_day(date_from, year)
            season_to = same_day(date_to, year)
            _progress(progress, 4 + int((index - 1) * 46 / len(years)), "DISCOVERY", f"Ищем снимки за {year}")

            sentinel = self._safe_search(
                "sentinel-2",
                lambda: self.sentinel.search(
                    bbox=bbox,
                    date_from=season_from,
                    date_to=season_to,
                    max_cloud_cover=max_cloud_cover,
                ),
                source_info,
            )
            source_info["sentinel-2"].setdefault("notes", []).extend(self.sentinel.search_notes)
            source_info["sentinel-2"]["candidate_scenes"] += len(sentinel)
            for scene_index, scene in enumerate(sentinel, start=1):
                percent = 4 + int(((index - 1) + .7 * scene_index / len(sentinel)) * 46 / len(years))
                _progress(progress, percent, "PROCESSING", f"Sentinel-2: {scene_index}/{len(sentinel)} сцен за {year}")
                sentinel_scenes[scene.id] = scene
                try:
                    grid = self.sentinel.grid(scene, bbox, self.resolution_m)
                    if grid.cells > self.max_cells:
                        raise ValueError(
                            f"Полигон даёт {grid.cells:,} ячеек; лимит {self.max_cells:,}. "
                            "Для интерактивного режима уменьшите AOI."
                        )
                    observation = self.sentinel.read(scene, geometry, grid, keep_rasters=False)
                    if observation.valid_fraction >= 0.10 and "ndvi" in observation.indices:
                        observations.append(observation)
                        source_info["sentinel-2"]["usable"] += 1
                except Exception as exc:
                    source_info["sentinel-2"]["errors"].append(f"{scene.id}: {exc}")

            landsat = self._safe_search(
                "landsat",
                lambda: self.landsat.search(
                    bbox=bbox,
                    date_from=season_from,
                    date_to=season_to,
                    max_cloud_cover=max_cloud_cover,
                ),
                source_info,
            )
            source_info["landsat"]["candidate_scenes"] += len(landsat)
            for scene_index, scene in enumerate(landsat, start=1):
                if landsat_access_denied:
                    break
                percent = 4 + int(((index - 1) + .7 + .3 * scene_index / len(landsat)) * 46 / len(years))
                _progress(progress, percent, "PROCESSING", f"Landsat: {scene_index}/{len(landsat)} сцен за {year}")
                try:
                    observation = self.landsat.read(scene, geometry, max_cells=self.max_cells)
                    if observation.valid_fraction >= 0.10 and "ndvi" in observation.indices:
                        observations.append(observation)
                        source_info["landsat"]["usable"] += 1
                except Exception as exc:
                    # Landsat COG иногда упирается в requester-pays. Это не причина
                    # валить весь анализ: Sentinel + ERA5 остаются рабочим путём.
                    source_info["landsat"]["errors"].append(f"{scene.id}: {exc}")
                    # Повторять запрещённый доступ для каждого COG бессмысленно;
                    # от сетевого timeout этот случай отличаем, чтобы сохранить retry других сцен.
                    landsat_access_denied = any(token in str(exc).lower() for token in
                                                ("403", "accessdenied", "requester pays", "requester-pays"))

        merged = merge_same_day(observations)
        current = [
            observation
            for observation in merged
            if date_from <= date.fromisoformat(observation.date) <= date_to
        ]
        history = [
            observation
            for observation in merged
            if date.fromisoformat(observation.date) < date_from
        ]
        # Manifest сохраняется и при неполном acquisition: можно проверить,
        # какие сцены реально прочитаны и почему конкретный источник отпал.
        manifest = {
            "field": field,
            "period": {"from": str(date_from), "to": str(date_to), "history_years": history_years},
            "resolution_m": self.resolution_m,
            "max_cloud_cover": max_cloud_cover,
            "sources": source_info,
            "observations": [asdict(item) for item in observations],
            "sentinel_scenes": [{**asdict(scene), "acquired_at": scene.acquired_at.isoformat()} for scene in
                                sentinel_scenes.values()],
        }
        (root / "acquisition.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        if len(current) < 2 or len(history) < 6:
            raise ValueError(
                "После quality mask мало наблюдений. Нужно минимум 2 точки текущего сезона "
                f"и 6 исторических; получено {len(current)} / {len(history)}. "
                + " ".join(f"{source}: {'; '.join(info['errors'][:2])}" for source, info in source_info.items() if
                           info['errors'])
            )

        _progress(progress, 55, "WEATHER", "Подтягиваем ERA5")
        weather: dict[str, dict] = {}
        try:
            weather = self.weather.fetch(
                latitude=float(center.y),
                longitude=float(center.x),
                date_from=min(date.fromisoformat(item.date) for item in merged),
                date_to=max(date.fromisoformat(item.date) for item in merged),
            )
            source_info["era5"]["available"] = bool(weather)
        except Exception as exc:
            source_info["era5"]["errors"].append(str(exc))

        (root / "weather.json").write_text(json.dumps(weather, ensure_ascii=False, indent=2), encoding="utf-8")

        _progress(progress, 65, "TEMPORAL", "Собираем ожидаемую и текущую траектории")
        temporal = analyze_temporal(current, history, weather, date_from.year)

        _progress(progress, 80, "SPATIAL", "Проверяем пространственное отклонение")
        spatial_events: list[dict] = []
        layers: list[dict] = []
        spatial_error = None
        try:
            spatial_events, layers = analyze_spatial(
                self.sentinel,
                current,
                history,
                sentinel_scenes,
                geometry,
                bbox,
                layers_dir,
                resolution_m=self.resolution_m,
            )
        except Exception as exc:
            spatial_error = str(exc)

        for event in temporal["events"]:
            matching = [item for item in spatial_events if event["start"] <= item["date"] <= event["end"]]
            if matching:
                event.setdefault("evidence", {})["spatial_area_ha"] = sum(item["area_ha"] for item in matching)

        if spatial_error:
            source_info["sentinel-2"]["errors"].append(f"spatial: {spatial_error}")

        result = {
            "id": analysis_id,
            "title": f"{field['name']} · vegetation intelligence",
            "field": field,
            "center": [float(center.x), float(center.y)],
            "period": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
                "history_years": history_years,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": source_info,
            "quality": {
                "observations": len(merged),
                "current_observations": len(current),
                "historical_observations": len(history),
                "weather_available": bool(weather),
            },
            "state": temporal["state"],
            "series": temporal["series"],
            "events": temporal["events"],
            "spatial_events": spatial_events,
            "layers": layers,
        }
        (root / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _progress(progress, 100, "DONE", "Анализ готов")
        return result

    def _safe_search(self, source: str, callback, source_info: dict) -> list[SceneRef]:
        try:
            return callback()
        except Exception as exc:
            source_info[source]["errors"].append(f"search: {exc}")
            return []


def _progress(callback, percent: int, stage: str, message: str) -> None:
    if callback:
        callback(percent, stage, message)
