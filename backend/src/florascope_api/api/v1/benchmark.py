from __future__ import annotations

import json
import numpy as np
import pandas as pd
import tempfile
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from florascope_core.inspect import inspect_dataset
from florascope_core.submission import validate_submission
from pathlib import Path

from ...container import Container, container
from ...schemas import CompetitionPayload
from ...services.competition import test_path as _test_path

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.post("/files/{kind}")
async def upload_dataset(
    kind: str,
    file: UploadFile = File(...),
    state: Container = Depends(container),
) -> dict:
    if kind not in {"train", "test"}:
        raise HTTPException(404, "kind должен быть train/test")
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Нужен CSV")

    destination = state.settings.data_dir / "input" / (
        "train_dataset.csv" if kind == "train" else "private_features.csv"
    )
    # Невалидная загрузка не должна уничтожить предыдущий рабочий датасет.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".csv", delete=False) as target:
            temporary = Path(target.name)
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 500 * 1024 * 1024:
                    raise HTTPException(413, "CSV больше 500 MB")
                target.write(chunk)
        try:
            audit = inspect_dataset(temporary)
        except Exception as exc:
            raise HTTPException(400, f"Не смогли прочитать датасет: {exc}") from exc
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"stored": destination.name, "audit": audit}


@router.post("/run", status_code=202)
def run_benchmark(
    payload: CompetitionPayload,
    state: Container = Depends(container),
) -> dict:
    train = state.settings.data_dir / "input" / "train_dataset.csv"
    test = _test_path(state.settings.data_dir / "input")
    if not train.exists() or test is None:
        raise HTTPException(400, "Сначала положите/загрузите train и test/private_features")
    return state.job_manager.submit_competition(train, test, payload.fast)


@router.get("/report")
def report(state: Container = Depends(container)) -> dict:
    path = state.settings.data_dir / "output" / "report.json"
    if not path.exists():
        raise HTTPException(404, "report.json ещё нет")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/submission")
def submission(state: Container = Depends(container)) -> FileResponse:
    path = state.settings.data_dir / "output" / "submission.csv"
    if not path.exists():
        raise HTTPException(404, "submission.csv ещё нет")
    return FileResponse(path, media_type="text/csv", filename="submission.csv")


@router.get("/validate")
def validate(state: Container = Depends(container)) -> dict:
    test = _test_path(state.settings.data_dir / "input")
    submission_path = state.settings.data_dir / "output" / "submission.csv"
    if test is None or not submission_path.exists():
        raise HTTPException(404, "Нет test/submission")
    return validate_submission(test, submission_path)


@router.get("/polygons")
def polygons(state: Container = Depends(container)) -> list[str]:
    path = state.settings.data_dir / "output" / "analysis_points.csv"
    if not path.exists():
        return []
    frame = pd.read_csv(path, usecols=["anon_polygon_id"])
    return sorted(frame["anon_polygon_id"].astype(str).unique().tolist())


@router.get("/series/{polygon_id}")
def series(polygon_id: str, state: Container = Depends(container)) -> list[dict]:
    path = state.settings.data_dir / "output" / "analysis_points.csv"
    if not path.exists():
        raise HTTPException(404, "analysis_points.csv ещё нет")
    frame = pd.read_csv(path)
    frame = frame.loc[frame["anon_polygon_id"].astype(str) == polygon_id].sort_values("date")
    columns = [
        "date",
        "primary_ndvi",
        "primary_ndvi_pred",
        "primary_ndvi_filled",
        "climatology_calc",
        "ndvi_zscore_calc",
        "status_calc",
        "water_zscore",
        "precip_zscore",
        "temp_zscore",
    ]
    return _records(frame[[column for column in columns if column in frame]])


@router.get("/events")
def events(state: Container = Depends(container)) -> list[dict]:
    path = state.settings.data_dir / "output" / "events.csv"
    if not path.exists():
        return []
    return _records(pd.read_csv(path))


def _records(frame: pd.DataFrame) -> list[dict]:
    result: list[dict] = []
    for row in frame.to_dict("records"):
        clean = {}
        for key, value in row.items():
            if value is None or (isinstance(value, float) and not np.isfinite(value)):
                clean[key] = None
            elif isinstance(value, np.generic):
                clean[key] = value.item()
            else:
                clean[key] = value
        result.append(clean)
    return result
