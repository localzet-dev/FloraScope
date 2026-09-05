from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .repositories.analyses import AnalysisRepository
from .repositories.fields import FieldRepository
from .repositories.jobs import JobRepository
from .services.competition import CompetitionService
from .services.live import LiveService


class JobManager:
    def __init__(
        self,
        *,
        jobs: JobRepository,
        fields: FieldRepository,
        analyses: AnalysisRepository,
        competition: CompetitionService,
        live: LiveService,
    ) -> None:
        self.jobs = jobs
        self.fields = fields
        self.analyses = analyses
        self.competition = competition
        self.live = live
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="florascope-job")

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)

    def submit_competition(self, train: Path, test: Path, fast: bool) -> dict:
        job = self.jobs.create(
            "competition",
            {"train": str(train), "test": str(test), "fast": fast},
        )
        self.executor.submit(self._run_competition, job["id"], train, test, fast)
        return job

    def submit_live(self, field_id: str, payload: dict) -> dict:
        field = self.fields.get(field_id)
        if field is None:
            raise ValueError("Полигон не найден")
        serializable = {
            **payload,
            "date_from": str(payload["date_from"]),
            "date_to": str(payload["date_to"]),
        }
        job = self.jobs.create("live", serializable)
        self.executor.submit(self._run_live, job["id"], field, payload)
        return job

    def _progress(self, job_id: str):
        def callback(percent: int, stage: str, message: str) -> None:
            self.jobs.update(
                job_id,
                state="running",
                progress=percent,
                stage=stage,
                message=message,
            )

        return callback

    def _run_competition(self, job_id: str, train: Path, test: Path, fast: bool) -> None:
        try:
            self.jobs.update(job_id, state="running", progress=1, stage="STARTING", message="Стартуем")
            report = self.competition.run(
                train=train,
                test=test,
                fast=fast,
                progress=self._progress(job_id),
            )
            self.jobs.update(
                job_id,
                state="completed",
                progress=100,
                stage="DONE",
                message=f"submission готов: {report['inference']['submission_rows']} строк",
                result_ref="competition",
            )
        except Exception as exc:
            self.jobs.update(
                job_id,
                state="failed",
                stage="FAILED",
                message=str(exc),
                error=traceback.format_exc(),
            )

    def _run_live(self, job_id: str, field: dict, payload: dict) -> None:
        try:
            self.jobs.update(job_id, state="running", progress=1, stage="STARTING", message="Стартуем")
            result = self.live.run(field, payload, self._progress(job_id))
            result_path = (
                self.live.analyzer.data_dir / "live" / result["id"] / "result.json"
            )
            self.analyses.save(result["id"], field["id"], result["title"], str(result_path))
            self.jobs.update(
                job_id,
                state="completed",
                progress=100,
                stage="DONE",
                message="live-анализ готов",
                result_ref=result["id"],
            )
        except Exception as exc:
            self.jobs.update(
                job_id,
                state="failed",
                stage="FAILED",
                message=str(exc),
                error=traceback.format_exc(),
            )
