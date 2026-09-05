from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from florascope_core.eo import render_tile
from pathlib import Path

from ...container import Container, container
from ...schemas import AnalysisPayload

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.get("")
def list_analyses(state: Container = Depends(container)) -> list[dict]:
    return state.analyses.list()


@router.post("", status_code=202)
def run_analysis(payload: AnalysisPayload, state: Container = Depends(container)) -> dict:
    if state.fields.get(payload.field_id) is None:
        raise HTTPException(404, "Полигон не найден")
    try:
        return state.job_manager.submit_live(
            payload.field_id,
            payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, state: Container = Depends(container)) -> dict:
    row = state.analyses.get(analysis_id)
    if row is None:
        raise HTTPException(404, "Анализ не найден")
    path = Path(row["result_path"])
    if not path.exists():
        raise HTTPException(410, "Файл результата потерян")
    result = json.loads(path.read_text(encoding="utf-8"))
    for layer in result.get("layers", []):
        layer["tile_url"] = f"/api/v1/analyses/{analysis_id}/tiles/{layer['key']}/{{z}}/{{x}}/{{y}}.png"
    return result


@router.get("/{analysis_id}/tiles/{layer}/{z}/{x}/{y}.png")
def tile(
    analysis_id: str,
    layer: str,
    z: int,
    x: int,
    y: int,
    state: Container = Depends(container),
) -> Response:
    if layer not in {"ndvi", "zscore", "quality"}:
        raise HTTPException(404, "Слой не найден")
    path = state.settings.data_dir / "live" / analysis_id / "layers" / f"{layer}.tif"
    if not path.exists():
        raise HTTPException(404, "Слой не найден")
    return Response(
        render_tile(path, z, x, y, layer),
        media_type="image/png",
        headers={"Cache-Control": "public,max-age=3600"},
    )
