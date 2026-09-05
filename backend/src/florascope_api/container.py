from __future__ import annotations

from functools import lru_cache

from .config import settings
from .database import Database
from .jobs import JobManager
from .repositories.analyses import AnalysisRepository
from .repositories.fields import FieldRepository
from .repositories.jobs import JobRepository
from .services.competition import CompetitionService
from .services.fields import FieldService
from .services.live import LiveService


class Container:
    def __init__(self) -> None:
        cfg = settings()
        self.settings = cfg
        self.database = Database(cfg.db_path)
        self.fields = FieldRepository(self.database)
        self.jobs = JobRepository(self.database)
        self.analyses = AnalysisRepository(self.database)
        self.field_service = FieldService(self.fields, cfg.overpass_url)
        self.competition = CompetitionService(
            data_dir=cfg.data_dir,
            artifacts_dir=cfg.artifacts_dir,
        )
        self.live = LiveService(
            data_dir=cfg.data_dir,
            earth_search_url=cfg.earth_search_url,
            weather_url=cfg.open_meteo_url,
            resolution_m=cfg.analysis_resolution_m,
            max_cells=cfg.max_analysis_cells,
        )
        self.job_manager = JobManager(
            jobs=self.jobs,
            fields=self.fields,
            analyses=self.analyses,
            competition=self.competition,
            live=self.live,
        )
        self.jobs.fail_interrupted()


@lru_cache(maxsize=1)
def container() -> Container:
    return Container()
