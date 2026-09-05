from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.data_dir = Path(os.getenv("FLORASCOPE_DATA_DIR", "./data")).resolve()
        self.artifacts_dir = Path(os.getenv("FLORASCOPE_ARTIFACTS_DIR", "./artifacts")).resolve()
        self.db_path = Path(
            os.getenv("FLORASCOPE_DB_PATH", str(self.data_dir / "florascope.db"))
        ).resolve()
        self.earth_search_url = os.getenv(
            "FLORASCOPE_EARTH_SEARCH_URL",
            "https://earth-search.aws.element84.com/v1",
        )
        self.open_meteo_url = os.getenv(
            "FLORASCOPE_OPEN_METEO_URL",
            "https://archive-api.open-meteo.com/v1/archive",
        )
        self.overpass_url = os.getenv(
            "FLORASCOPE_OVERPASS_URL",
            "https://overpass-api.de/api/interpreter",
        )
        self.analysis_resolution_m = float(
            os.getenv("FLORASCOPE_ANALYSIS_RESOLUTION_M", "20")
        )
        self.max_analysis_cells = int(
            os.getenv("FLORASCOPE_MAX_ANALYSIS_CELLS", "300000")
        )
        self.scene_workers = max(
            1, min(int(os.getenv("FLORASCOPE_SCENE_WORKERS", "3")), 4)
        )
        self.allowed_origins = [
            value.strip()
            for value in os.getenv(
                "FLORASCOPE_ALLOWED_ORIGINS",
                "http://localhost:5173,http://localhost:8080",
            ).split(",")
            if value.strip()
        ]

        for path in (
                self.data_dir,
                self.data_dir / "input",
                self.data_dir / "output",
                self.data_dir / "live",
                self.artifacts_dir,
                self.db_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
