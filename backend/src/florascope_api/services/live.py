from __future__ import annotations

from florascope_core.eo import LiveAnalyzer
from pathlib import Path


class LiveService:
    def __init__(
        self,
        *,
        data_dir: Path,
        earth_search_url: str,
        weather_url: str,
        resolution_m: float,
        max_cells: int,
        scene_workers: int,
    ) -> None:
        self.analyzer = LiveAnalyzer(
            earth_search_url=earth_search_url,
            weather_url=weather_url,
            data_dir=data_dir,
            resolution_m=resolution_m,
            max_cells=max_cells,
            scene_workers=scene_workers,
        )

    def run(self, field: dict, payload: dict, progress) -> dict:
        return self.analyzer.run(
            field,
            date_from=payload["date_from"],
            date_to=payload["date_to"],
            history_years=int(payload["history_years"]),
            max_cloud_cover=float(payload["max_cloud_cover"]),
            progress=progress,
        )
